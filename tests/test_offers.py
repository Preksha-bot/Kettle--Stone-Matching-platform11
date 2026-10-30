"""Platform step 5 (platform-plan.md §10): the offer loop on the openings screen. Hold the slot in Kneadly
before the first call, one live offer at a time, no / no answer brings the next name, yes goes through the
booking card, and the daily check lists what still has to be finished in Kneadly."""
import io
import re
import sqlite3
from datetime import date, datetime
from urllib.parse import urlencode
from wsgiref.util import setup_testing_defaults

import pytest

from conftest import SAMPLE
from kettle import store
from test_webapp import upload
from webapp.app import Platform

O05 = "A-24065"   # Wed Sep 23 11:45 · Rachel · names: Pauline (51), Carole (48), Amanda (42)
O01 = "A-24010"   # Mon Sep 21 12:30 · Josée · Amanda (42) is #1
TANYA_O05 = {33, 42, 48, 49, 51, 55, 60}


@pytest.fixture
def app(tmp_path):
    clock = {"now": datetime(2026, 10, 21, 9, 0)}  # the run date; never earlier than the book's newest line
    platform = Platform(tmp_path / "data" / "kettle.db", tmp_path / "out", today=lambda: date(2026, 10, 21),
                        now=lambda: clock["now"])
    platform.clock = clock
    upload(platform, **SAMPLE)
    return platform


def send(app, method, path, form=None, desk="Tanya"):
    body = urlencode(form or {}, doseq=True).encode()
    environ = {}
    setup_testing_defaults(environ)
    environ.update({"REQUEST_METHOD": method, "PATH_INFO": path.partition("?")[0],
                    "QUERY_STRING": path.partition("?")[2], "HTTP_HOST": "localhost:8000",
                    "CONTENT_TYPE": "application/x-www-form-urlencoded", "CONTENT_LENGTH": str(len(body)),
                    "wsgi.input": io.BytesIO(body)})
    if desk:
        environ["HTTP_COOKIE"] = f"kettle_desk={desk}"
    seen = {}

    def start_response(status, headers):
        seen["status"], seen["headers"] = status, headers
    out = b"".join(app(environ, start_response)).decode("utf-8")
    return seen["status"], seen["headers"], out


def step(app, do, opening=O05, **form):
    return send(app, "POST", "/opening", {"opening": opening, "do": do, **form})


def card(app, opening=O05):
    page = send(app, "GET", "/")[2]
    start = page.index(f"id='o-{opening}'")
    return page[start:page.index("</section>", start)]


def names_on(app, opening):
    con = store.connect(app.db_path)
    return [r["line"] for r in store.latest_run(con)["rows"][opening] if r["rank"] > 0]


def live_offer(app, opening=O05):
    return store.desk_state(store.connect(app.db_path))[opening]["live"]


def held_and_offered(app, line):
    step(app, "hold", checked="yes")
    step(app, "offer", line=line)
    return live_offer(app)


def book(app, offer, **form):
    return step(app, "book", offer=offer["id"], **{"length": "60", "how": "booked now", "checked": "yes", **form})


# ---------- who's at the desk ----------

def test_who_is_at_the_desk_is_remembered_by_the_browser(app):
    status, headers, _ = send(app, "POST", "/desk", {"name": "Tanya"}, desk=None)
    assert status.startswith("303") and ("Set-Cookie", "kettle_desk=Tanya; Path=/; SameSite=Strict; HttpOnly") in headers
    assert "At the desk: <b>Tanya</b>" in send(app, "GET", "/")[2]
    assert "Who's at the desk?" in send(app, "GET", "/", desk=None)[2]
    status, _, page = send(app, "POST", "/opening", {"opening": O05, "do": "hold", "checked": "yes"}, desk=None)
    assert status.startswith("400") and "at the desk first" in page


# ---------- hold, then one offer at a time ----------

def test_no_offer_before_the_slot_is_held_in_kneadly(app):
    assert "Hold placed" in card(app) and "value='offer'" not in card(app)
    assert "Place the hold" in step(app, "offer", line=51)[2]
    assert "block the time there first" in step(app, "hold")[2]  # the tick is required
    step(app, "hold", checked="yes")
    held = card(app)
    assert "Held in Kneadly since 09:00" in held and held.count("value='offer'") == 3


def test_only_one_live_offer_per_opening(app):
    held_and_offered(app, 51)
    assert "Offering to Pauline Bastarache · Tanya · 0 min" in card(app)
    status, _, page = step(app, "offer", line=48)
    assert status.startswith("400") or status.startswith("409")
    con = store.connect(app.db_path)
    with pytest.raises(store.LiveOfferError):  # the database itself refuses a second live offer
        store.start_offer(con, O05, 48, "Carole Mazerolle", None, "Bethany", datetime(2026, 10, 21, 9, 1))


def test_a_no_brings_the_next_name_and_is_never_offered_that_opening_again(app):
    offer = held_and_offered(app, 51)
    step(app, "answer", offer=offer["id"], answer="no")
    lines = names_on(app, O05)
    assert 51 not in lines and len(lines) == 3 and set(lines) <= TANYA_O05
    assert "Already offered: <b>Pauline Bastarache</b> (said no 09:00)" in card(app)
    assert 51 in names_on(app, "A-24163")  # O12: a no counts for O05 only
    con = store.connect(app.db_path)
    assert store.declined_lines(con) == {O05: {51}}


def test_the_offer_shows_the_minutes_and_after_20_says_move_on(app):
    held_and_offered(app, 51)
    app.clock["now"] = datetime(2026, 10, 21, 9, 21)
    shown = card(app)
    assert "(21 min)" in shown and "20 minutes: if there" in shown
    assert "Offers waiting more than 20 minutes" in send(app, "GET", "/check")[2]


# ---------- yes, the booking card, the refill ----------

def test_a_yes_goes_through_the_booking_card_before_anything_is_saved(app):
    offer = held_and_offered(app, 42)
    page = step(app, "answer", offer=offer["id"], answer="yes")[2]
    assert "Confirm the refill" in page and "rebooked into A-24065" in page
    assert live_offer(app) is not None  # nothing saved yet
    status, _, page = book(app, offer, checked="")
    assert status.startswith("400") and "our hold is still there first" in page
    assert book(app, offer, length="90")[0].startswith("400")  # a length that doesn't fit the opening
    assert book(app, offer, how="book at check-in")[0].startswith("303")
    assert "Filled: Amanda Bourgeois" in card(app)


def test_whoever_said_yes_is_off_the_list_everywhere(app):
    assert 42 in names_on(app, O01)
    book(app, held_and_offered(app, 42))
    assert 42 not in names_on(app, O01)
    amanda = next(p for p in store.latest_run(store.connect(app.db_path))["people"] if 42 in p["lines"])
    assert amanda["status"] == "stale" and "booked from the waitlist into O05 Wed Sep 23 11:45 on Oct 21" in amanda["reasons"]


def test_undoing_a_yes_puts_everything_back(app):
    offer = held_and_offered(app, 42)
    book(app, offer)
    rebooking = store.active_rebookings(store.connect(app.db_path))[0]
    step(app, "undo_yes", rebooking=rebooking["id"])
    assert live_offer(app)["id"] == offer["id"] and "Offering to Amanda Bourgeois" in card(app)
    assert 42 in names_on(app, O01)


def test_refills_not_in_kneadly_are_in_the_daily_check_and_the_csv(app):
    book(app, held_and_offered(app, 42), how="book at check-in")
    page = send(app, "GET", "/check")[2]
    assert "Refills not in Kneadly yet" in page and "Amanda Bourgeois" in page
    assert "Daily check:</b> 1 thing to finish" in send(app, "GET", "/")[2]
    csv_text = send(app, "GET", "/files/rebookings.csv")[2]
    assert "O05 Wed Sep 23 11:45,A-24065,Amanda Bourgeois,506-555-0125,42,60,book at check-in,no" in csv_text
    rebooking = store.active_rebookings(store.connect(app.db_path))[0]
    step(app, "in_kneadly", rebooking=rebooking["id"], kneadly_id="A-31002")
    assert "Nothing to finish" in send(app, "GET", "/check")[2]
    assert "yes,A-31002" in send(app, "GET", "/files/rebookings.csv")[2]


# ---------- other ways an opening closes ----------

def test_filled_another_way_withdraws_the_offer_and_can_be_reopened(app):
    offer = held_and_offered(app, 51)
    step(app, "taken", how="a client called in")
    assert "Taken: a client called in" in card(app)
    assert store.get_offer(store.connect(app.db_path), offer["id"])["outcome"] == "withdrawn"
    assert store.declined_lines(store.connect(app.db_path)) == {}  # a withdrawn offer isn't a no
    step(app, "reopen")
    assert "Hold placed" in card(app)


def test_already_taken_before_the_hold(app):
    step(app, "taken", how="booked online")
    assert "Taken: booked online" in card(app)


def test_releasing_needs_the_block_removed_first(app):
    step(app, "hold", checked="yes")
    assert "Remove the block in Kneadly first" in step(app, "release")[2]
    step(app, "release", checked="yes")
    assert "Released: nobody left" in card(app)


def test_the_daily_check_lists_slots_still_blocked_after_their_start(app):
    app.clock["now"] = datetime(2026, 9, 23, 9, 0)  # before O05's 11:45 start
    step(app, "hold", checked="yes")
    assert "Nothing to finish" in send(app, "GET", "/check")[2]
    app.clock["now"] = datetime(2026, 9, 23, 12, 0)
    page = send(app, "GET", "/check")[2]
    assert "Slots still blocked after their start time" in page and "O05 · Wed Sep 23 11:45" in page
    step(app, "release", how="passed", checked="yes")
    assert "Released: the start time passed" in card(app)
    assert "Nothing to finish" in send(app, "GET", "/check")[2]


# ---------- the record ----------

def test_offers_are_refused_while_paused(app):
    con = store.connect(app.db_path)
    with con:
        store.set_paused(con, True, "Marc", datetime(2026, 9, 23, 8, 0))
    assert step(app, "hold", checked="yes")[0].startswith("409")


def test_desk_names_are_on_the_screen_but_never_in_a_file(app):
    """Shown next to an offer so two people don't call about one slot; kept out of every output file."""
    send(app, "POST", "/opening", {"opening": O05, "do": "hold", "checked": "yes"}, desk="Zelda%20Quist")
    send(app, "POST", "/opening", {"opening": O05, "do": "offer", "line": 51}, desk="Zelda%20Quist")
    assert "Offering to Pauline Bastarache · Zelda Quist" in send(app, "GET", "/", desk="Zelda%20Quist")[2]
    live = live_offer(app)
    send(app, "POST", "/opening", {"opening": O05, "do": "answer", "offer": live["id"], "answer": "no"},
         desk="Zelda%20Quist")
    files = [f.read_text(encoding="utf-8") for f in app.out_dir.rglob("*") if f.is_file()]
    files.append(send(app, "GET", "/files/rebookings.csv")[2])
    assert files and not any("Zelda" in text for text in files)
