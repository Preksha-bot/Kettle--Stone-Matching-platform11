"""Platform step 7 (platform-plan.md §9.4, technical plan §11.5): the morning call list. Today's (still to come)
and tomorrow's bookings that weren't confirmed in the last upload; one tap per call; "Cancelled" goes through
the inbox as a morning call, and under 24 h before the start the names appear right under the booking."""
import sqlite3
from datetime import datetime

import pytest

from conftest import SAMPLE
from kettle import store
from test_offers import send
from test_sync import read_rows, write_rows
from test_webapp import upload
from webapp.app import Platform

DAVE_1400 = "A-99101"    # Thu Oct 22 14:00 · Dave · not confirmed
KELSEY_1100 = "A-99102"  # Thu Oct 22 11:00 · confirmed by text
RACHEL_FRI = "A-99103"   # Fri Oct 23 10:00 · not confirmed
MARC_0700 = "A-99104"    # Thu Oct 22 07:00 · not confirmed, but already started at 08:00
JOSEE_1600 = "A-99105"   # Thu Oct 22 16:00 · booked the same day (n/a)
AMIRA_SAT = "A-99106"    # Sat Oct 24 10:00 · not confirmed, but not today or tomorrow


@pytest.fixture
def app(tmp_path):
    clock = {"now": datetime(2026, 10, 22, 8, 0)}
    platform = Platform(tmp_path / "data" / "kettle.db", tmp_path / "out", today=lambda: clock["now"].date(),
                        now=lambda: clock["now"])
    platform.clock = clock
    upload(platform, **SAMPLE)
    base = read_rows(SAMPLE["appointments"])[0]
    rows = [dict(base, appointment_id=a, date=d, start=s, end=e, length_min="60", therapist=t, client_name=c,
                 client_id="K-9" + a[-3:], booked_at="2026-10-10 10:00", status="Booked", confirmation=conf,
                 cancelled_at="", cancel_via="", rebooked_into="")
            for a, d, s, e, t, c, conf in (
                (DAVE_1400, "2026-10-22", "14:00", "15:00", "Dave Melanson", "Rita Comeau", "none"),
                (KELSEY_1100, "2026-10-22", "11:00", "12:00", "Kelsey Babineau", "Marc Gallant", "text C"),
                (RACHEL_FRI, "2026-10-23", "10:00", "11:00", "Rachel Thibodeau", "Lucie Arsenault", "none"),
                (MARC_0700, "2026-10-22", "07:00", "08:00", "Marc Cormier", "Paul Leger", "none"),
                (JOSEE_1600, "2026-10-22", "16:00", "17:00", "Josée Landry", "Anne Roy", "n/a (same day)"),
                (AMIRA_SAT, "2026-10-24", "10:00", "11:00", "Amira Haddad", "Eve Cyr", "none"))]
    upload(platform, "2026-10-22", appointments=write_rows(tmp_path / "upcoming.csv", rows))
    return platform


def tap(app, appointment, do, **form):
    return send(app, "POST", "/calls", {"appointment": appointment, "do": do, **form})


def page(app, path="/calls"):
    return send(app, "GET", path)[2]


def section(text, title, end_titles=("<h2>", "<details>", "</main>")):
    start = text.index(title)
    ends = [text.find(e, start + len(title)) for e in end_titles]
    return text[start:min(e for e in ends if e != -1)]


# ---------- who is on the list ----------

def test_only_unconfirmed_bookings_today_still_to_come_and_tomorrow(app):
    calls = page(app)
    assert "To call (2)" in calls
    assert DAVE_1400 in calls and RACHEL_FRI in calls and "R. Comeau" in calls and "Rita" not in calls
    for left_out in (KELSEY_1100, MARC_0700, JOSEE_1600, AMIRA_SAT):  # text C · started · same day · Saturday
        assert left_out not in calls, left_out
    assert calls.index(DAVE_1400) < calls.index(RACHEL_FRI)  # soonest first


def test_another_day_can_be_looked_at(app):
    calls = page(app, "/calls?from=2026-10-16")  # the sample's Friday and Saturday
    assert "To call (" in calls and "Morning calls" in calls
    con = store.connect(app.db_path)
    expected = [b["appointment_id"] for b in store.call_list(con, [datetime(2026, 10, 16).date(), datetime(2026, 10, 17).date()])]
    assert expected and all(a in calls for a in expected)


# ---------- the taps ----------

def test_confirmed_moves_the_booking_to_done_and_can_be_undone(app):
    status, headers, _ = tap(app, DAVE_1400, "confirmed")
    assert status.startswith("303") and dict(headers)["Location"] == f"/calls#c-{DAVE_1400}"
    calls = page(app)
    assert "To call (1)" in calls and "Confirmed (1)" in calls and "confirmed 08:00" in calls
    tap(app, DAVE_1400, "undo")
    assert "To call (2)" in page(app)


def test_voicemail_moves_to_try_again_with_a_dot_per_call(app):
    tap(app, DAVE_1400, "voicemail")
    app.clock["now"] = datetime(2026, 10, 22, 8, 40)
    tap(app, DAVE_1400, "voicemail")
    again = section(page(app), "Try again (voicemail left) (1)")
    assert DAVE_1400 in again and "voicemail 08:00 08:40 ●●" in again
    tap(app, DAVE_1400, "confirmed")
    assert "Try again" not in page(app)


def test_cancelled_today_brings_the_names_right_under_the_booking(app):
    tap(app, DAVE_1400, "cancelled")
    cancelled = section(page(app), "Cancelled (1)")
    assert DAVE_1400 in cancelled and "D01" in cancelled and "6 h notice left" in cancelled
    assert "hold and offer on the Openings page" in cancelled and f"/#o-{DAVE_1400}" in cancelled
    con = store.connect(app.db_path)
    names = [r for r in store.latest_run(con)["rows"][DAVE_1400] if r["rank"] > 0]
    assert names and all(n["person"] in cancelled for n in names)
    assert "{'" not in cancelled and "'rank'" not in cancelled  # rendered as names, not as raw data
    assert store.heard_already(con, DAVE_1400)["heard_via"] == "morning call"
    assert store.booking(con, DAVE_1400)["status"] == "Late cancel"
    assert "Hold placed" in page(app, "/")  # the opening is on the Openings page, ready for the hold


def test_cancelled_for_tomorrow_morning_is_not_a_late_cancellation(app):
    tap(app, RACHEL_FRI, "cancelled")  # Fri 10:00 at Thu 08:00: 26 hours ahead
    cancelled = section(page(app), "Cancelled (1)")
    assert RACHEL_FRI in cancelled and "not a late cancellation" in cancelled
    con = store.connect(app.db_path)
    assert con.execute("SELECT COUNT(*) FROM openings WHERE appointment_id = ?", (RACHEL_FRI,)).fetchone()[0] == 0


def test_a_cancellation_already_in_the_inbox_makes_no_second_opening(app):
    send(app, "POST", "/inbox/cancel", {"appointment": DAVE_1400, "heard_via": "voicemail (overnight)",
                                        "cancelled_at": "2026-10-22T06:31"})
    tap(app, DAVE_1400, "cancelled")
    con = store.connect(app.db_path)
    assert con.execute("SELECT COUNT(*) FROM openings WHERE source = 'desk'").fetchone()[0] == 1
    assert store.heard_already(con, DAVE_1400)["heard_via"] == "voicemail (overnight)"  # first heard, kept
    assert "D01" in section(page(app), "Cancelled (1)")


def test_a_cancellation_cant_be_undone_here(app):
    tap(app, DAVE_1400, "cancelled")
    tap(app, DAVE_1400, "undo")
    assert "Cancelled (1)" in page(app)


def test_a_visit_that_has_started_cant_be_cancelled(app):
    app.clock["now"] = datetime(2026, 10, 22, 14, 10)
    assert "already started" in tap(app, DAVE_1400, "cancelled")[2]
    assert store.heard_already(store.connect(app.db_path), DAVE_1400) is None


# ---------- the record ----------

def test_the_desk_has_to_say_who_they_are(app):
    assert "Say who" in send(app, "GET", "/calls", desk=None)[2]
    text = send(app, "POST", "/calls", {"appointment": DAVE_1400, "do": "confirmed"}, desk=None)[2]
    assert "at the desk first" in text
    assert not sqlite3.connect(app.db_path).execute("SELECT COUNT(*) FROM calls").fetchone()[0]


def test_calls_are_refused_while_paused(app):
    con = store.connect(app.db_path)
    with con:
        store.set_paused(con, True, "Marc", datetime(2026, 10, 22, 7, 0))
    assert tap(app, DAVE_1400, "confirmed")[0].startswith("409")
