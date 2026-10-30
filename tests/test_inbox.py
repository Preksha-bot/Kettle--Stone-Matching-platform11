"""Platform step 6 (platform-plan.md §9.4): the cancellation inbox. The desk enters a cancellation from the
day's bookings (or by its Kneadly number); under 24 h before the start it becomes an opening with names straight
away, counting its notice from now; one appointment is one row however many ways it's heard; no reason is kept."""
import sqlite3
from datetime import date, datetime

import pytest

from conftest import SAMPLE
from kettle import store
from test_offers import send
from test_sync import read_rows, write_rows
from test_webapp import upload
from webapp.app import Platform

DAVE_1400 = "A-99101"    # Thu Oct 22 14:00 · Dave · 60 · Rita Comeau
KELSEY_1100 = "A-99102"  # Thu Oct 22 11:00 · Kelsey · 90 · Marc Gallant
RACHEL_FRI = "A-99103"   # Fri Oct 23 10:00 · Rachel · 60 · Lucie Arsenault


@pytest.fixture
def app(tmp_path):
    """The sample, then an appointments file with the next bookings (the stand-in for the API's 'today and
    tomorrow'). The clock: Thu Oct 22, 09:00."""
    clock = {"now": datetime(2026, 10, 22, 9, 0)}
    platform = Platform(tmp_path / "data" / "kettle.db", tmp_path / "out", today=lambda: clock["now"].date(),
                        now=lambda: clock["now"])
    platform.clock = clock
    upload(platform, **SAMPLE)
    base = read_rows(SAMPLE["appointments"])[0]
    upcoming = [dict(base, appointment_id=a, date=d, start=s, end=e, length_min=n, therapist=t, client_name=c,
                     client_id="K-9" + a[-3:], booked_at="2026-10-10 10:00", status="Booked", cancelled_at="",
                     cancel_via="", rebooked_into="")
                for a, d, s, e, n, t, c in ((DAVE_1400, "2026-10-22", "14:00", "15:00", "60", "Dave Melanson", "Rita Comeau"),
                                            (KELSEY_1100, "2026-10-22", "11:00", "12:30", "90", "Kelsey Babineau", "Marc Gallant"),
                                            (RACHEL_FRI, "2026-10-23", "10:00", "11:00", "60", "Rachel Thibodeau", "Lucie Arsenault"))]
    upload(platform, "2026-10-22", appointments=write_rows(tmp_path / "upcoming.csv", upcoming))
    return platform


def cancel(app, appointment, when="2026-10-22T06:31", via="voicemail (overnight)", **form):
    return send(app, "POST", "/inbox/cancel", {"appointment": appointment, "heard_via": via, "cancelled_at": when, **form})


def manual(app, **form):
    fields = {"manual": "yes", "appointment": "A-99200", "date": "2026-10-22", "start": "16:00",
              "therapist": "Rachel Thibodeau", "length": "60", "heard_via": "phone", "cancelled_at": "2026-10-22T08:50"}
    return send(app, "POST", "/inbox/cancel", {**fields, **form})


def run(app):
    return store.latest_run(store.connect(app.db_path))


def card(app, appointment):
    page = send(app, "GET", "/")[2]
    start = page.index(f"id='o-{appointment}'")
    return page[start:page.index("</section>", start)]


# ---------- entering a cancellation ----------

def test_the_days_bookings_are_listed_to_enter_a_cancellation_from(app):
    page = send(app, "GET", "/inbox")[2]
    assert "Say who" not in page  # the desk name (cookie) is known here too
    assert "Say who" in send(app, "GET", "/inbox", desk=None)[2]
    assert "R. Comeau" in page and "M. Gallant" in page and "Rita" not in page  # initial and last name only
    assert f"/inbox/cancel?appointment={DAVE_1400}" in page and "L. Arsenault" not in page
    assert "L. Arsenault" in send(app, "GET", "/inbox?day=2026-10-23")[2]
    form = send(app, "GET", f"/inbox/cancel?appointment={DAVE_1400}")[2]
    assert "Thu Oct 22 14:00 · Dave Melanson · 60 min" in form and "<textarea" not in form  # no reason asked for


def test_a_late_cancellation_becomes_an_opening_with_names_at_once(app):
    status, headers, _ = cancel(app, DAVE_1400)
    assert status.startswith("303") and dict(headers)["Location"] == f"/#o-{DAVE_1400}"
    view = run(app)
    assert view["run"]["run_date"] == "2026-10-22"
    assert [r for r in view["rows"][DAVE_1400] if r["rank"] > 0]  # names straight away
    shown = card(app, DAVE_1400)
    assert "D01 · cancelled 06:31 · heard via voicemail (overnight)" in shown
    assert "5 h notice" in shown and "Hold placed" in shown  # 14:00 - now (09:00), not from the voicemail
    con = store.connect(app.db_path)
    assert store.booking(con, DAVE_1400)["status"] == "Late cancel"
    assert [tuple(r) for r in con.execute("SELECT old_status, new_status FROM booking_events WHERE appointment_id = ?",
                                          (DAVE_1400,))] == [("Booked", "Late cancel")]
    page = send(app, "GET", "/")[2]
    assert page.index(f"id='o-{DAVE_1400}'") < page.index("id='o-A-24010'")  # coming up before the past ones


def test_notice_is_counted_from_now_so_names_change_as_the_start_gets_closer(app):
    cancel(app, DAVE_1400)
    at_nine = [r["line"] for r in run(app)["rows"][DAVE_1400] if r["rank"] > 0]
    app.clock["now"] = datetime(2026, 10, 22, 13, 0)
    send(app, "POST", "/inbox/rematch")
    assert "1 h notice" in card(app, DAVE_1400)
    at_one = [r["line"] for r in run(app)["rows"][DAVE_1400] if r["rank"] > 0]
    assert at_one != at_nine
    people = {line: p for p in run(app)["people"] for line in p["lines"]}
    assert all(people[line]["notice_hours"] <= 1 for line in at_one)


def test_a_cancellation_a_day_or_more_ahead_is_only_recorded(app):
    page = cancel(app, RACHEL_FRI, when="2026-10-22T08:55")[2]  # Fri 10:00, 25 h ahead
    assert "isn&#x27;t a late cancellation" in page and "Kneadly&#x27;s online page offers it" in page
    con = store.connect(app.db_path)
    assert store.heard_already(con, RACHEL_FRI)["opening_id"] is None
    assert con.execute("SELECT COUNT(*) FROM openings WHERE appointment_id = ?", (RACHEL_FRI,)).fetchone()[0] == 0
    assert store.booking(con, RACHEL_FRI)["status"] == "Cancelled"
    assert "not late: Kneadly" in send(app, "GET", "/inbox")[2]


def test_one_appointment_is_one_row_however_many_ways_it_is_heard(app):
    cancel(app, DAVE_1400)
    page = cancel(app, DAVE_1400, when="2026-10-22T07:10", via="online (Kneadly)")[2]
    assert "Already in the inbox: heard via voicemail (overnight)" in page
    page = cancel(app, "A-24010", when="2026-09-21T09:00")[2]  # O01 from the sample file
    assert "Already in the inbox" in page
    con = store.connect(app.db_path)
    assert con.execute("SELECT COUNT(*) FROM openings WHERE source = 'desk'").fetchone()[0] == 1


def test_times_that_cant_be_right_are_refused(app):
    status, _, page = cancel(app, DAVE_1400, when="2026-10-22T14:05")
    assert status.startswith("400") and ("later than now" in page or "no-show" in page)
    app.clock["now"] = datetime(2026, 10, 22, 15, 0)
    assert "no-show" in cancel(app, DAVE_1400, when="2026-10-22T14:30")[2]
    assert "how it came in" in cancel(app, DAVE_1400, via="carrier pigeon")[2]
    assert store.heard_already(store.connect(app.db_path), DAVE_1400) is None


def test_a_booking_after_the_last_upload_can_be_entered_by_its_number(app):
    status, headers, _ = manual(app)
    assert status.startswith("303")
    o = store.load_openings(store.connect(app.db_path), ["A-99200"])[0]
    assert (o.opening_id, o.therapist, o.start.strftime("%H:%M"), o.length_min) == ("D01", "Rachel Thibodeau", "16:00", 60)
    for bad, problem in (({"appointment": "A 99 / x"}, "appointment number"), ({"therapist": "Sophie Martin"}, "from the lists"),
                         ({"appointment": "A-99201", "start": ""}, "start time")):
        page = manual(app, **bad)[2]
        assert problem in page, problem


# ---------- the inbox list, and the rest of the record ----------

def test_the_inbox_shows_each_cancellation_with_its_status(app):
    cancel(app, DAVE_1400)
    send(app, "POST", "/opening", {"opening": DAVE_1400, "do": "hold", "checked": "yes"})
    page = send(app, "GET", "/inbox")[2]
    coming = page[page.index("Coming up"):page.index("Earlier (")]
    assert "D01" in coming and "held in Kneadly" in coming and "06:31 · voicemail (overnight)" in coming
    assert "Earlier (44)" in page  # the sample's openings, all in the past


def test_the_desk_has_to_say_who_they_are(app):
    page = send(app, "POST", "/inbox/cancel", {"appointment": DAVE_1400, "heard_via": "phone",
                                                "cancelled_at": "2026-10-22T08:00"}, desk=None)[2]
    assert "at the desk first" in page


def test_the_inbox_is_refused_while_paused(app):
    con = store.connect(app.db_path)
    with con:
        store.set_paused(con, True, "Marc", datetime(2026, 10, 22, 8, 0))
    assert cancel(app, DAVE_1400)[0].startswith("409")


def test_no_reason_is_kept(app):
    cancel(app, DAVE_1400)
    columns = {r[1] for r in sqlite3.connect(app.db_path).execute("PRAGMA table_info(cancellations)")}
    assert columns == {"appointment_id", "date", "start", "therapist", "length_min", "cancelled_at", "heard_via",
                       "late", "recorded_at", "recorded_by"}
