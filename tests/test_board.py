"""Platform step 9 (platform-plan.md §6): the waitlist board. One card per person, changed on screen instead of in
the book: Edit card, Still interested, Take off (a reason from a short list), + Add (phone checked first), a
history, and the switch to retire the book. Every change is a desk entry: undoable, matched again at once."""
import html
from datetime import date, datetime

import pytest

from conftest import SAMPLE
from kettle import store
from test_offers import send
from test_privacy_and_unseen import HEALTH_WORDS
from test_sync import waitlist_plus
from test_webapp import call, multipart, upload
from webapp.app import Platform


@pytest.fixture
def app(tmp_path):
    platform = Platform(tmp_path / "data" / "kettle.db", tmp_path / "out", today=lambda: date(2026, 10, 21),
                        now=lambda: datetime(2026, 10, 21, 9, 0))
    upload(platform, **SAMPLE)
    return platform


def act(app, do, **form):
    return send(app, "POST", "/board", {"do": do, **form})


def person(app, line):
    return next(p for p in store.latest_run(store.connect(app.db_path))["people"] if line in p["lines"])


def names_on(app, appointment):
    return [r["line"] for r in store.latest_run(store.connect(app.db_path))["rows"][appointment] if r["rank"] > 0]


AMANDA_CARD = {"line": "26", "who": "only", "only": ["Josée Landry", "Rachel Thibodeau"], "length": ["60"], "notice": "2"}


# ---------- the board ----------

def test_the_board_shows_each_person_as_a_card_without_any_health_detail(app):
    page = html.unescape(send(app, "GET", "/board")[2])
    assert "active (30)" in page and "held (0)" in page and "out of date (15)" in page and "all (45)" in page
    amanda = page[page.index("id='p-26'"):page.index("</section>", page.index("id='p-26'"))]
    assert "Amanda Bourgeois" in amanda and "Josée or Rachel" in amanda and "60 min" in amanda and "lines 26, 42" in amanda
    sarah = page[page.index("id='p-10'"):page.index("</section>", page.index("id='p-10'"))]
    assert "Amira or Kelsey" in sarah  # the routing shows as therapists, never as the reason
    assert "pregnan" not in page.lower() and "prenatal" not in page.lower() and HEALTH_WORDS.search(page) is None


def test_the_board_can_be_filtered_and_searched(app):
    assert "Gisele Maillet" in send(app, "GET", "/board?show=stale")[2]
    assert "Gisele Maillet" not in send(app, "GET", "/board")[2]
    found = send(app, "GET", "/board?show=all&q=0125")[2]
    assert "Amanda Bourgeois" in found and "Pauline Bastarache" not in found
    assert "Amanda Bourgeois" in send(app, "GET", "/board?show=all&q=amanda")[2]


# ---------- changing a card ----------

def test_edit_card_saves_the_card_and_the_names_change_at_once(app):
    form = html.unescape(send(app, "GET", "/board/card?line=26")[2])
    assert "Card: Amanda Bourgeois" in form
    assert form.count("<label>Therapist</label>") == 1 and form.count("name=who value=any") == 1  # each field once
    assert 42 in names_on(app, "A-24010")  # O01, Josée: Amanda is #1
    status, headers, _ = act(app, "card", **{**AMANDA_CARD, "only": ["Rachel Thibodeau"]})
    assert status.startswith("303") and dict(headers)["Location"] == "/board?show=all#p-26"
    amanda = person(app, 26)
    assert amanda["therapists_allowed"] == ["Rachel Thibodeau"] and amanda["lines"] == [26, 42, store.DESK_LINE_START]
    assert amanda["first_asked"] == "2026-09-11"  # her place in the queue is kept
    assert 42 not in names_on(app, "A-24010")


def test_an_unchanged_card_saves_nothing(app):
    assert "Nothing changed" in act(app, "card", **AMANDA_CARD)[2]
    assert not store.active_decisions(store.connect(app.db_path))


def test_a_newer_line_in_the_book_still_overrides_the_card(app, tmp_path):
    act(app, "card", **{**AMANDA_CARD, "only": ["Rachel Thibodeau"]})
    upload(app, waitlist=waitlist_plus(tmp_path, ("10/22", "Amanda B.", "506-555-0125", "Josee only")))
    assert person(app, 26)["therapists_allowed"] == ["Josée Landry"]


def test_still_interested_resets_the_60_day_clock(app):
    assert person(app, 1)["status"] == "stale"  # Gisele Maillet: no contact since Jul 06
    act(app, "still", line="1")
    gisele = person(app, 1)
    assert gisele["status"] == "active" and gisele["last_contact"] == "2026-10-21" and gisele["first_asked"] == "2026-07-06"


def test_take_off_asks_for_a_reason_from_the_list(app):
    act(app, "takeoff", line="26", reason="moved")
    assert person(app, 26)["status"] == "stale" and "moved away" in person(app, 26)["reasons"]
    assert "couldn" in html.unescape(act(app, "takeoff", line="39", reason="she was rude")[2])
    assert person(app, 39)["status"] == "active"


# ---------- adding someone ----------

def test_add_checks_the_phone_first_then_adds_a_card(app):
    page = html.unescape(act(app, "add", name="Lisa Comeau", phone="(506) 555-0125", who="any", length=["60"])[2])
    assert "Already on the waitlist with that number: Amanda Bourgeois" in page
    assert "10-digit" in html.unescape(act(app, "add", name="Lisa Comeau", phone="555-01", who="any")[2])
    status, headers, _ = act(app, "add", name="Paul Arsenault", phone="506 555 0190", who="any", length=["60"],
                             day=["Mon", "Wed"])
    assert status.startswith("303") and dict(headers)["Location"] == f"/board?show=all#p-{store.DESK_LINE_START}"
    paul = person(app, store.DESK_LINE_START)
    assert (paul["status"], paul["phone"], paul["days"], paul["first_asked"]) == ("active", "5065550190", ["Mon", "Wed"],
                                                                                    "2026-10-21")


# ---------- history, undo, and the record ----------

def test_the_history_shows_book_lines_without_their_notes_and_every_change(app):
    act(app, "card", **{**AMANDA_CARD, "only": ["Rachel Thibodeau"], "notice": "3"})
    page = html.unescape(send(app, "GET", "/board/history?line=26")[2])
    assert "card changed (therapists, notice)" in page and "line 26" in page and "line 42" in page
    assert "R/J" not in page and "ins ok" not in page  # the notes themselves are never kept
    decision = store.active_decisions(store.connect(app.db_path))[0]
    send(app, "POST", "/review/undo", {"id": decision["id"]})
    assert person(app, 26)["therapists_allowed"] == ["Josée Landry", "Rachel Thibodeau"]


def test_retiring_the_book_refuses_book_uploads_until_switched_back(app, tmp_path):
    assert "agreement" in act(app, "mode", on="yes")[2]
    act(app, "mode", on="yes", agreed="yes")
    assert "Board only" in send(app, "GET", "/board")[2]
    body, ctype = multipart(waitlist=SAMPLE["waitlist"])
    assert "kept on the board now" in call(app, "POST", "/upload/check", body, ctype)[2]
    body, ctype = multipart(openings=SAMPLE["openings"])
    assert call(app, "POST", "/upload/check", body, ctype)[0].startswith("200")  # openings still come in
    act(app, "mode", on="no")
    body, ctype = multipart(waitlist=SAMPLE["waitlist"])
    assert call(app, "POST", "/upload/check", body, ctype)[0].startswith("200")


def test_the_desk_has_to_say_who_they_are(app):
    assert "Edit card" not in send(app, "GET", "/board", desk=None)[2]
    page = send(app, "POST", "/board", {"do": "still", "line": "26"}, desk=None)[2]
    assert "at the desk first" in page and not store.active_decisions(store.connect(app.db_path))


def test_the_board_is_refused_while_paused(app):
    con = store.connect(app.db_path)
    with con:
        store.set_paused(con, True, "Marc", datetime(2026, 10, 21, 8, 0))
    assert act(app, "still", line="26")[0].startswith("409")
