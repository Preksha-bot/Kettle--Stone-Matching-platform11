"""Platform step 3 (platform-plan.md §7.4): the review queue. Every kind of held person can be released by a
person's decision on the screen, each decision is saved with who made it (never shown), can be undone, and
the openings are matched again straight after. Nothing is released by itself."""
import json
import sqlite3
from datetime import date
from urllib.parse import urlencode

import pytest

from conftest import SAMPLE
from kettle import store
from kettle.adapters.csv_in import InputError
from kettle.adapters.upload import sync
from test_privacy_and_unseen import HEALTH_WORDS
from test_sync import read_rows, waitlist_plus, write_rows
from test_webapp import call, upload
from webapp import pages
from webapp.app import Platform

TODAY = date(2026, 10, 21)
FORM = "application/x-www-form-urlencoded"
GILLES = ("10/20", "Gilles Probe", "506-555-0199", "any - 1hr - AM - shingles")  # an unknown word: held
ROBERT = ("10/20", "Robert Smith", "506-555-0125", "any - 60")                 # Amanda's phone: identity check


@pytest.fixture
def app(tmp_path):
    """The sample plus one person of each kind held for review: Gilles (line 61, a word that can't be read),
    Amanda (26, 42) and Robert (62) sharing a phone, and Marcel (18), a regular who booked since his line."""
    platform = Platform(tmp_path / "data" / "kettle.db", tmp_path / "out", today=lambda: TODAY)
    rows = read_rows(SAMPLE["appointments"])
    extra = dict(rows[0], appointment_id="A-99001", date="2026-10-20", start="10:00", end="11:00", length_min="60",
                 therapist="Marc Cormier", client_id="K-9999", client_name="Marcel Bujold",
                 booked_at="2026-10-01 09:00", status="Completed", cancelled_at="", cancel_via="", rebooked_into="")
    upload(platform, waitlist=waitlist_plus(tmp_path, GILLES, ROBERT),
           appointments=write_rows(tmp_path / "a.csv", rows + [extra]), openings=SAMPLE["openings"])
    return platform


def decide(app, choice, checked_by="Tanya", **fields):
    status, headers, page = call(app, "POST", "/review/decide",
                                 urlencode({"choice": choice, "checked_by": checked_by, **fields}, doseq=True).encode(), FORM)
    return status, headers, page


def people(app):
    con = sqlite3.connect(app.db_path)
    return {json.loads(r[0])["lines"][0]: json.loads(r[0]) for r in con.execute("SELECT record FROM people")}


def last_decision_id(app):
    return sqlite3.connect(app.db_path).execute("SELECT MAX(id) FROM desk_decisions").fetchone()[0]


def undo(app, decision_id):
    return call(app, "POST", "/review/undo", f"id={decision_id}".encode(), FORM)


# ---------- the screen ----------

def test_the_review_screen_lists_each_held_person_with_the_decisions_that_fit(app):
    page = call(app, "GET", "/review")[2]
    assert "Needs review (4)" in page
    for name in ("Gilles Probe", "Amanda Bourgeois", "Robert Smith", "Marcel Bujold"):
        assert name in page
    assert "Line 62 and this person:" in page  # Amanda's card: one question about line 62, not one per line of hers
    assert page.count("value='same person|62|") == 1 and "value='different people|62|26'" in page
    assert "Line 42 and this person:" in page  # Robert's card
    assert "/review/fill?line=61" in page and "value='still wants it|18|'" in page
    assert "one word (see the book)" in page and "shingles" not in page
    assert HEALTH_WORDS.search(page) is None
    assert "Needs review (4)" in call(app, "GET", "/")[2]  # the count is in the menu on every screen


def test_nothing_is_released_by_itself(app):
    """No 'release all': each held person needs their own decision."""
    page = call(app, "GET", "/review")[2]
    assert "release all" not in page.lower()
    assert sum(1 for p in people(app).values() if p["status"] == "review") == 4


# ---------- identity ----------

def test_different_people_releases_both(app):
    status, headers, _ = decide(app, "different people|62|42")
    assert status.startswith("303") and headers["Location"] == "/review?done=1"
    p = people(app)
    assert p[26]["status"] == "active" and p[26]["lines"] == [26, 42]
    assert p[62]["status"] == "active" and p[62]["lines"] == [62]
    assert "Needs review (2)" in call(app, "GET", "/review")[2]


def test_same_person_merges_them_and_undo_holds_them_again(app):
    decide(app, "same person|62|42")
    merged = people(app)[26]
    assert merged["lines"] == [26, 42, 62] and merged["status"] == "active"
    assert undo(app, last_decision_id(app))[0].startswith("303")
    p = people(app)
    assert p[26]["status"] == "review" and p[62]["status"] == "review"
    assert "undone" in call(app, "GET", "/review")[2]


def test_leaving_a_line_out(app):
    decide(app, "ignore|62|")
    p = people(app)
    assert 62 not in {line for rec in p.values() for line in rec["lines"]}
    assert p[26]["status"] == "active"
    verdicts = (app.out_dir / "line-verdicts.csv").read_text(encoding="utf-8")
    assert "W62,ignored" in verdicts


def test_same_person_with_a_line_typed_in(app, tmp_path):
    """'same #' with no earlier line of that name: the desk types the other line's number."""
    book = waitlist_plus(tmp_path, GILLES, ROBERT, ("10/21", "Yvette Zed", "same #", "60 ok"))
    upload(app, waitlist=book)
    assert "same person|63|?" in call(app, "GET", "/review")[2]
    _, _, page = decide(app, "same person|63|?", other_63="")
    assert "Give the number of the other line" in page
    decide(app, "same person|63|?", other_63="61")
    assert people(app)[61]["lines"] == [61, 63]


# ---------- filling in what they can take ----------

def test_filling_in_the_card_starts_them_over_and_keeps_their_place(app):
    form = call(app, "GET", "/review/fill?line=61")[2]
    assert "Fill in: Gilles Probe" in form
    assert form.count("<label>Therapist</label>") == 1 and form.count("name=who value=any") == 1  # each field once
    decide(app, "start over|61|", who="only", only=["Rachel Thibodeau"], length=["45", "60"], day=["Mon", "Wed"],
           before="12:00", notice="1")
    g = people(app)[61]
    assert g["status"] == "active" and g["lines"] == [61, store.DESK_LINE_START]
    assert g["therapists_allowed"] == ["Rachel Thibodeau"] and g["lengths"] == [45, 60]
    assert g["days"] == ["Mon", "Wed"] and g["start_before"] == "12:00" and g["notice_hours"] == 1.0
    assert g["first_asked"] == "2026-10-20"  # their place in the queue


def test_the_card_starts_from_what_could_be_read_including_the_prenatal_routing(app):
    form = call(app, "GET", "/review/fill?line=10")[2]  # Sarah Collette: pregnant, female, 60, weekdays
    assert "name=needs value='prenatal-trained' checked" in form and "name=female value='yes' checked" in form
    assert "Prenatal-trained therapists only (desk only" in form  # the rule's chip, from the settings
    assert "name=length value='60' checked" in form and "name=day value='Sat' checked" not in form
    assert "pregnant" not in form.lower()


def test_a_card_that_cant_be_saved_says_why_and_saves_nothing(app):
    status, _, page = decide(app, "start over|61|", who="only")
    assert status.startswith("400") and "Tick at least one therapist" in page and "Fill in: Gilles Probe" in page
    _, _, page = decide(app, "start over|61|", available_from="2026-11-05", available_until="2026-11-01")
    assert "after &#x27;Available until&#x27;" in page
    assert last_decision_id(app) is None


def test_a_later_line_in_the_book_still_overrides_the_card(app, tmp_path):
    decide(app, "start over|61|", who="only", only=["Rachel Thibodeau"])
    book = waitlist_plus(tmp_path, GILLES, ROBERT, ("10/22", "Gilles Probe", "506-555-0199", "Josee only"))
    upload(app, waitlist=book)
    g = people(app)[61]
    assert g["lines"] == [61, store.DESK_LINE_START, 63] and g["therapists_allowed"] == ["Josée Landry"]


# ---------- regulars, taking off, changed lines ----------

def test_a_regular_who_still_wants_an_extra_visit(app):
    decide(app, "still wants it|18|")
    m = people(app)[18]
    assert m["status"] == "active" and m["last_contact"] == TODAY.isoformat()
    assert m["first_asked"] == "2026-09-02"


def test_taking_someone_off_the_list(app):
    decide(app, "take off|61|")
    g = people(app)[61]
    assert g["status"] == "stale" and "asked to come off the list" in g["reasons"]


def test_keeping_a_changed_lines_new_text_and_undoing_it(app, tmp_path):
    rows = read_rows(waitlist_plus(tmp_path, GILLES, ROBERT))
    rows[38]["notes"] = "any - 60 - mornings"
    upload(app, waitlist=write_rows(tmp_path / "changed.csv", rows))
    assert people(app)[39]["status"] == "review"
    assert "value='keep new text|39|'" in call(app, "GET", "/review")[2]
    decide(app, "keep new text|39|")
    assert people(app)[39]["status"] == "active" and people(app)[39]["start_before"] == "12:00"
    undo(app, last_decision_id(app))
    assert people(app)[39]["status"] == "review"


# ---------- the record ----------

def test_a_decision_needs_a_name_which_is_never_shown(app):
    status, _, page = decide(app, "take off|61|", checked_by=" ")
    assert status.startswith("400") and "Write your name" in page
    decide(app, "take off|61|", checked_by="Zelda Quist")
    assert sqlite3.connect(app.db_path).execute("SELECT checked_by FROM desk_decisions").fetchone()[0] == "Zelda Quist"
    pages_seen = [call(app, "GET", p)[2] for p in ("/", "/review", "/log", "/review/fill?line=61")]
    files = [f.read_text(encoding="utf-8") for f in app.out_dir.rglob("*") if f.is_file()]
    assert not any("Zelda" in text for text in pages_seen + files)


def test_each_decision_matches_the_last_runs_openings_again(app):
    decide(app, "different people|62|42")
    view = store.latest_run(store.connect(app.db_path))
    assert len(view["openings"]) == 44 and view["run"]["run_date"] == "2026-10-21"
    assert view["summary"]["note"] == "desk decision: different people, line 62 and line 42"
    assert "desk decision: different people" in call(app, "GET", "/log")[2]


def test_unclear_decisions_are_refused(app):
    for choice in ("explode|61|", "take off|999|", "same person|62|62", "nothing"):
        status, _, page = decide(app, choice)
        assert status.startswith("400"), choice
    assert last_decision_id(app) is None
    assert call(app, "POST", "/review/undo", b"id=77", FORM)[0].startswith("303")  # nothing to undo: no change
    assert call(app, "POST", "/review/decide", b"choice=take+off%7C61%7C&checked_by=T", FORM,
                origin="http://evil.example")[0].startswith("403")


def test_book_lines_cant_use_the_desks_line_numbers(tmp_path):
    rows = read_rows(SAMPLE["waitlist"])
    rows.append(dict(rows[-1], line=str(store.DESK_LINE_START)))
    with pytest.raises(InputError, match="kept for entries made on the review screen"):
        sync(tmp_path / "k.db", TODAY, write_rows(tmp_path / "w.csv", rows), SAMPLE["appointments"], SAMPLE["openings"],
             tmp_path / "o")


def test_the_drift_alarm_shows_when_more_than_1_in_10_are_held():
    def crowd(held, total):
        return [{"status": "review" if i < held else "active"} for i in range(total)]
    assert pages.drift_box(crowd(1, 10)) == ""
    assert "2 of 10 people are held" in pages.drift_box(crowd(2, 10))
