"""Releasing held people (plan §7.3): "start over" lines for notes that can't be read, and reviewed.csv for
phone/name mix-ups. Both only ever release someone the desk has checked; anything doubtful stays held."""
from datetime import date

import pytest

from conftest import SAMPLE, SAMPLE_RUN_DATE, make_people
from kettle.adapters.csv_in import InputError, ReviewRow, read_reviewed
from kettle.core.people import build_reviewed, line_verdicts
from kettle.pipeline import run
from run import main

UNREADABLE = ("Oct 1", "Ann Doiron", "506-555-0901", "any - 60 - only on alternate blue moons")


def decisions(*rows, lines=range(1, 10)):
    """rows: (line, decision, other_line) as the desk would write them."""
    return build_reviewed([ReviewRow(n, *r) for n, r in enumerate(rows, 2)], set(lines))


# ---------- "start over" lines ----------

def test_start_over_is_read_and_the_rest_of_the_line_still_parses(parser):
    s = parser.parse("start over - Rachel only - 60", SAMPLE_RUN_DATE)
    assert s.start_over and s.therapists == {"Rachel Thibodeau"} and s.lengths == {60}
    assert not s.unparsed and not s.needs_check
    assert parser.parse("new: any - 45", SAMPLE_RUN_DATE).start_over


def test_new_client_is_not_start_over(parser):
    s = parser.parse("NEW client (intake form) - any - Fri only after 3", SAMPLE_RUN_DATE)
    assert s.new_client and not s.start_over


def test_bare_start_over_is_held_not_read_as_anyone_any_time(parser):
    assert parser.parse("start over", SAMPLE_RUN_DATE).needs_check


def test_start_over_only_counts_at_the_start(parser):
    assert parser.parse("Rachel - start over", SAMPLE_RUN_DATE).unparsed


def test_a_plain_newer_line_does_not_release_an_unreadable_older_line(config):
    people = make_people([UNREADABLE, ("Oct 20", "Ann D.", "same #", "called again - any - 60 - Mon")], config)
    assert len(people) == 1 and people[0].status == "review"


def test_start_over_releases_them_and_keeps_their_place_in_the_queue(config):
    people = make_people([UNREADABLE, ("Oct 20", "Ann D.", "same #", "start over - any - 60 - Mon")], config)
    ann = people[0]
    assert ann.status == "active" and ann.days == {"Mon"}
    assert ann.first_asked == date(2026, 10, 1)


def test_start_over_drops_what_the_older_lines_said(config):
    rows = [("Oct 1", "Ann Doiron", "506-555-0901", "J only - not Mon - 45"),
            ("Oct 20", "Ann Doiron", "506-555-0901", "start over - Rachel - 60")]
    ann = make_people(rows, config)[0]
    assert ann.therapists == {"Rachel Thibodeau"} and ann.days_excluded == set() and ann.lengths == {60}


# ---------- reviewed.csv: the desk's decisions on identity mix-ups ----------

SAME_NAME_NEW_PHONE = [("Oct 1", "Lynn Savoie", "506-555-0105", "any - 60"),
                       ("Oct 10", "Lynn S.", "506-555-0199", "J only - 45")]
SHARED_PHONE = [("Oct 1", "Lynn Savoie", "506-555-0105", "any - 60"),
                ("Oct 10", "Kayla Savoie", "506-555-0105", "Kelsey - 60")]


def test_same_person_merges_and_uses_the_newest_number(config):
    reviewed, warnings = decisions((2, "same person", 1))
    people = make_people(SAME_NAME_NEW_PHONE, config, reviewed=reviewed)
    assert not warnings and len(people) == 1
    lynn = people[0]
    assert lynn.status == "active" and lynn.phone == "5065550199" and lynn.therapists == {"Josée Landry"}


@pytest.mark.parametrize("rows", [SAME_NAME_NEW_PHONE, SHARED_PHONE])
def test_different_people_are_both_released(config, rows):
    reviewed, _ = decisions((2, "Different people", 1))
    people = make_people(rows, config, reviewed=reviewed)
    assert len(people) == 2 and all(p.status == "active" for p in people)


def test_same_person_settles_an_unresolved_same_number(config):
    rows = [("Oct 1", "Kim Belliveau", "506-555-0112", "any - 60"),
            ("Oct 5", "Greg Mazerolle", "same #", "Dave - 60")]
    assert make_people(rows, config)[1].status == "review"
    reviewed, _ = decisions((2, "same person", 1))
    people = make_people(rows, config, reviewed=reviewed)
    assert len(people) == 1 and people[0].status == "active" and people[0].phone == "5065550112"


def test_ignored_line_is_left_out(config):
    reviewed, _ = decisions((2, "ignore", None))
    people = make_people(SAME_NAME_NEW_PHONE, config, reviewed=reviewed)
    assert len(people) == 1 and people[0].status == "active" and people[0].line_ids == [1]
    assert line_verdicts(people, reviewed.ignore) == {1: "active", 2: "ignored"}


@pytest.mark.parametrize("rows,message", [
    ([(2, "same person", 1), (1, "different people", 2)], "marked both"),
    ([(2, "maybe", 1)], "isn't one of"),
    ([(2, "same person", None)], "needs the other line"),
    ([(2, "same person", 99)], "line 99 isn't on the waitlist"),
])
def test_doubtful_rows_are_skipped_and_the_lines_stay_held(config, rows, message):
    reviewed, warnings = decisions(*rows)
    assert any(message in w for w in warnings)
    assert all(p.status == "review" for p in make_people(SAME_NAME_NEW_PHONE, config, reviewed=reviewed))


# ---------- the file and the run ----------

def test_reviewed_file_reading(tmp_path):
    path = tmp_path / "reviewed.csv"
    path.write_text("line,decision,other_line,checked_by\n", encoding="utf-8")
    assert read_reviewed(path) == ([], [])
    path.write_text("line,decision,other_line,checked_by\nW42,same person,W26,Tanya\nforty,ignore,,\n\n",
                    encoding="utf-8")
    rows, warnings = read_reviewed(path)
    assert [(r.row, r.line, r.decision, r.other_line) for r in rows] == [(2, 42, "same person", 26)]
    assert "row 3" in warnings[0]
    path.write_text("line,choice\n", encoding="utf-8")
    with pytest.raises(InputError, match="missing column"):
        read_reviewed(path)


def test_blank_reviewed_file_changes_nothing(tmp_path, sample):
    blank = tmp_path / "reviewed.csv"
    blank.write_text("line,decision,other_line,checked_by\n", encoding="utf-8")
    result = run(SAMPLE["waitlist"], SAMPLE["appointments"], SAMPLE["openings"], SAMPLE_RUN_DATE, tmp_path / "o",
                 reviewed=blank)
    picks = lambda res: [[p.person.active_line for p in r.picks] for r in res["results"]]
    assert picks(result) == picks(sample) and result["verdicts"] == sample["verdicts"]
    assert "DESK DECISIONS (reviewed.csv):\n  none" in (tmp_path / "o" / "preprocess-report.txt").read_text("utf-8")
    assert "not used on this run" in (sample["out"] / "preprocess-report.txt").read_text("utf-8")


def test_ignore_on_the_sample_leaves_that_line_out_and_never_echoes_notes(tmp_path):
    path = tmp_path / "reviewed.csv"
    path.write_text("line,decision,other_line,checked_by\n39,ignore,,Tanya: knee note\n", encoding="utf-8")
    result = run(SAMPLE["waitlist"], SAMPLE["appointments"], SAMPLE["openings"], SAMPLE_RUN_DATE, tmp_path / "o",
                 reviewed=path)
    assert result["verdicts"][39] == "ignored"
    assert all(39 not in [p.person.active_line for p in r.picks] for r in result["results"])
    report = (tmp_path / "o" / "preprocess-report.txt").read_text("utf-8")
    assert "line 39: ignored" in report and "knee" not in report


def test_missing_reviewed_file_stops_the_run(tmp_path):
    assert main(["--reviewed", str(tmp_path / "nope.csv"), "--out", str(tmp_path / "o")]) == 1
