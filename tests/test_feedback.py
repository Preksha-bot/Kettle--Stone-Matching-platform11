"""Platform step 10 (platform-plan.md §11): the feedback loop. A weekly offer limit per person (anti-pestering), a
reason when someone says no, "no, keep me on" counting as contact, three no's in a row flagged on the card, and
Marc's numbers. An opening's own outcome never picks the names for that opening."""
import html
import json
import shutil
from datetime import date, datetime, timedelta

import pytest

from conftest import SAMPLE
from kettle import feedback, store
from kettle.config import DEFAULT_CONFIG
from test_offers import send
from test_settings import check, settings_of
from test_webapp import upload
from webapp.app import Platform

O05, O12, O23 = "A-24065", "A-24163", "A-24320"  # Pauline Bastarache (line 51) is shown on all three


def make_app(tmp_path, limit=0):
    config = tmp_path / "clinic.json"
    raw = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    raw["defaults"]["max_offers_per_week"] = limit
    config.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    clock = {"now": datetime(2026, 10, 21, 9, 0)}
    platform = Platform(tmp_path / "data" / "kettle.db", tmp_path / "out", config_path=config,
                        today=lambda: clock["now"].date(), now=lambda: clock["now"])
    platform.clock = clock
    upload(platform, **SAMPLE)
    return platform


@pytest.fixture
def app(tmp_path):
    return make_app(tmp_path)


def step(app, opening, do, **form):
    return send(app, "POST", "/opening", {"opening": opening, "do": do, **form})


def offer(app, opening, line=51):
    step(app, opening, "hold", checked="yes")
    step(app, opening, "offer", line=line)
    return store.desk_state(store.connect(app.db_path))[opening]["live"]


def answer(app, opening, live, answer="no", why=""):
    return step(app, opening, "answer", offer=live["id"], answer=answer, why=why)


def names_on(app, appointment):
    return [r["line"] for r in store.latest_run(store.connect(app.db_path))["rows"][appointment] if r["rank"] > 0]


def person(app, line):
    return next(p for p in store.latest_run(store.connect(app.db_path))["people"] if line in p["lines"])


# ---------- anti-pestering ----------

def test_with_no_limit_nobody_rests(app):
    answer(app, O12, offer(app, O12))
    offer(app, O05)
    assert 51 in names_on(app, O23) and "Resting this week" not in send(app, "GET", "/")[2]


def test_at_the_weekly_limit_a_person_rests_everywhere_but_their_live_offer(tmp_path):
    app = make_app(tmp_path, limit=2)
    assert 51 in names_on(app, O23)
    answer(app, O12, offer(app, O12))      # offer 1: no
    app.clock["now"] = datetime(2026, 10, 21, 9, 5)
    offer(app, O05)                         # offer 2: live, the limit is reached
    assert 51 not in names_on(app, O23)     # someone else who fits is shown instead
    assert 51 in names_on(app, O05)         # still on the opening she's being offered right now
    page = html.unescape(send(app, "GET", "/")[2])
    assert "Resting this week" in page and "Pauline Bastarache</b> until Wed Oct 28" in page
    assert "resting until Wed Oct 28 (2 offers this week)" in html.unescape(send(app, "GET", "/board")[2])
    con = store.connect(app.db_path)
    people = store.latest_run(con)["people"]
    assert feedback.resting(con, people, 2, datetime(2026, 10, 28, 9, 1)) == {}  # a week later she's back


# ---------- what people say ----------

def test_the_reason_for_a_no_is_kept_and_counted(app):
    answer(app, O05, offer(app, O05), why="the time")
    con = store.connect(app.db_path)
    assert con.execute("SELECT outcome, reason FROM offers").fetchone()[:] == ("no", "the time")
    page = html.unescape(send(app, "GET", "/report?since=2026-09-01&until=2026-10-31")[2])
    assert "<td>the time</td><td>1</td>" in page
    answer(app, O12, offer(app, O12), why="she was rude")  # not on the list: no free text is ever kept
    assert [tuple(r) for r in con.execute("SELECT reason FROM offers ORDER BY id")] == [("the time",), (None,)]


def test_no_keep_me_on_counts_as_contact(app):
    assert person(app, 51)["last_contact"] == "2026-10-08"
    answer(app, O05, offer(app, O05), "no, keep me on")
    pauline = person(app, 51)
    assert pauline["last_contact"] == "2026-10-21" and pauline["status"] == "active"
    assert 51 not in names_on(app, O05)  # still a no for this opening


def test_three_nos_in_a_row_ask_if_still_interested(app):
    for opening in (O05, O12, O23):
        answer(app, opening, offer(app, opening))
    assert "said no 3 times in a row: ask if still interested" in html.unescape(send(app, "GET", "/board")[2])


def test_a_possible_wrong_offer_is_listed(app):
    answer(app, O05, offer(app, O05), why=feedback.MISTAKE)
    page = html.unescape(send(app, "GET", "/report?since=2026-09-01&until=2026-10-31")[2])
    section = page[page.index("Possible wrong offers"):]
    assert "O05 2026-09-23 11:45" in section and "Pauline Bastarache (line 51)" in section


# ---------- Marc's numbers ----------

def test_the_report_counts_refills_by_how_they_happened(app):
    live = offer(app, O05)
    answer(app, O05, live, "yes")
    step(app, O05, "book", offer=live["id"], length="60", how="booked now", checked="yes")
    step(app, O12, "taken", how="a client called in")
    page = html.unescape(send(app, "GET", "/report?since=2026-09-21&until=2026-10-17")[2])
    assert "Late openings:</b> 36" in page and "No-shows</b> (never offered): 8" in page
    assert "<td>refilled from the waitlist</td><td>1</td>" in page
    assert "<td>filled another way: a client called in</td><td>1</td>" in page
    assert "Time from hearing to filled:</b> " in page and "median of 1" in page
    # the booking export's own refills (Sep 21 - Oct 17): 5 phoned, 4 the desk called, 3 online
    for line in ("<td>the client phoned</td><td>5</td>", "<td>the desk called</td><td>4</td>",
                 "<td>booked online</td><td>3</td>"):
        assert line in page, line


def test_outcomes_csv_lists_each_offer_and_its_answer(app):
    answer(app, O05, offer(app, O05), why="the day")
    text = send(app, "GET", "/files/outcomes.csv")[2]
    assert "O05,A-24065,2026-09-23,11:45,Rachel Thibodeau,60,12.4,W51 no (the day),,held" in text
    assert "Tanya" not in text  # no desk names in a file


# ---------- the setting ----------

def test_the_limit_is_a_setting_on_the_settings_screen(app):
    assert "Offers per person per week" in send(app, "GET", "/settings")[2]
    page = html.unescape(check(app, max_offers_per_week="2")[2])
    assert "Offers per person per week (0 = no limit): 0 → 2" in page
    assert "must be a whole number, 0 or more" in html.unescape(check(app, max_offers_per_week="lots")[2])
