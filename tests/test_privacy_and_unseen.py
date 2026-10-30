"""Privacy of every output file, and shorthand the sample never used (guards against tuning to 60 lines)."""
import re
from datetime import date, time

import pytest

from conftest import SAMPLE
from kettle.pipeline import run

HEALTH_WORDS = re.compile(r"sciatica|knee|replacement|pregnant|\btri\b|fibro|pressure|\bmva\b|claim|\btmj\b"
                          r"|migraine|concussion|cancer|hamstring|hockey|rotator|shoulder|post-op|low back|\bhip\b"
                          r"|\bwks\b|survivor|no deep|light only|ins pays", re.I)


def test_no_health_detail_in_any_output_file(sample):
    files = [f for f in sample["out"].rglob("*") if f.is_file()]
    assert len(files) >= 6
    for f in files:
        text = f.read_text(encoding="utf-8")
        hit = HEALTH_WORDS.search(text)
        assert hit is None, f"{f.name} contains '{hit.group(0)}'"


def test_input_files_are_never_changed(tmp_path):
    before = {k: open(v, "rb").read() for k, v in SAMPLE.items()}
    run(SAMPLE["waitlist"], SAMPLE["appointments"], SAMPLE["openings"], date(2026, 10, 21), tmp_path)
    assert before == {k: open(v, "rb").read() for k, v in SAMPLE.items()}


def test_missing_column_stops_with_a_clear_message(tmp_path):
    from kettle.adapters.csv_in import InputError
    bad = tmp_path / "waitlist.csv"
    bad.write_text("line,added,name,notes\n1,Oct 1,A B,any\n", encoding="utf-8")
    with pytest.raises(InputError, match="phone"):
        run(str(bad), SAMPLE["appointments"], SAMPLE["openings"], date(2026, 10, 21), tmp_path / "o")


# Lines written fresh, in the clinic's style but with phrasing the sample never used.
UNSEEN = [
    ("K only - 45 - Thurs/Fri - after 2 - can come in 1 hr",
     dict(therapists={"Kelsey Babineau"}, lengths={45}, days={"Thu", "Fri"}, earliest_start=time(14), notice=1.0)),
    ("anyone but Marc or Dave - 90 - wkdays - needs 3 hrs",
     dict(excluded={"Marc Cormier", "Dave Melanson"}, lengths={90}, days={"Mon", "Tue", "Wed", "Thu", "Fri"}, notice=3.0)),
    ("Rachel or Kelsey - 30 - evenings - text only",
     dict(therapists={"Rachel Thibodeau", "Kelsey Babineau"}, lengths={30}, earliest_start=time(18), contact="text only")),
    ("female - 1.5 hrs - Sat only - day before",
     dict(female_only=True, lengths={90}, days={"Sat"}, day_before=True)),
    ("Amira - 60 - not before 11 - here til Nov 15",
     dict(therapists={"Amira Haddad"}, earliest_start=time(11), available_until=date(2026, 11, 15))),
    ("J/R - 45 - not Wed or Fri - mornings",
     dict(therapists={"Josée Landry", "Rachel Thibodeau"}, lengths={45}, days_excluded={"Wed", "Fri"}, start_before=time(12))),
    ("K or A - 60 - can come quick",
     dict(therapists={"Kelsey Babineau", "Amira Haddad"}, lengths={60}, notice=0.5)),
    ("any - 60 - mornings - moved to Dieppe", dict(gone="moved to dieppe")),
]


@pytest.mark.parametrize("notes,expected", UNSEEN)
def test_unseen_shorthand(parser, notes, expected):
    spec = parser.parse(notes, date(2026, 10, 30))
    assert spec.unparsed == []
    for field, value in expected.items():
        assert getattr(spec, field) == value, field


@pytest.mark.parametrize("notes", ["any - 60 - every other week maybe", "Bethany's friend - any", "X only - 60"])
def test_unreadable_lines_are_held_back(parser, notes):
    assert parser.parse(notes, date(2026, 10, 30)).unparsed
