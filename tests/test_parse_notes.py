"""Priority 1: the notebook shorthand parser (plan §5.3, rules B4–B13)."""
import re
from datetime import date, time

import pytest

from conftest import SAMPLE_RUN_DATE, SAMPLE
from kettle.adapters.csv_in import read_waitlist

ALL = {"Marc Cormier", "Dave Melanson", "Josée Landry", "Amira Haddad", "Kelsey Babineau", "Rachel Thibodeau"}
WEEKDAYS = {"Mon", "Tue", "Wed", "Thu", "Fri"}


def parse(parser, notes, run_date=SAMPLE_RUN_DATE):
    spec = parser.parse(notes, run_date)
    assert spec.unparsed == [], f"unexpected unparsed text: {spec.unparsed}"
    assert spec.needs_check == [], f"unexpectedly held: {spec.needs_check}"
    return spec


def test_josee_only_with_health_detail(parser):
    s = parse(parser, "J only - knee replacement June - 45")
    assert s.therapists == {"Josée Landry"} and s.lengths == {45}
    assert s.had_health_detail and not s.prenatal


def test_anyone_but_dave_not_monday_mornings(parser):
    s = parse(parser, "AB Dave - not Mon - 1hr - AM")
    assert s.therapists is None and s.excluded == {"Dave Melanson"}
    assert s.days_excluded == {"Mon"} and s.lengths == {60} and s.start_before == time(12, 0)


def test_lunch_window_is_weekdays_twelve_to_one(parser):
    s = parse(parser, "any - 30 or 45 - on his lunch 12-1 only - 30 min notice ok, works at the bank across the st")
    assert s.therapists == ALL and s.lengths == {30, 45} and s.days == WEEKDAYS
    assert (s.earliest_start, s.latest_end, s.notice) == (time(12, 0), time(13, 0), 0.5)


def test_pregnancy_becomes_routing_flag_and_pref_is_not_a_filter(parser):
    s = parse(parser, "pregnant 30 wks - Amira pref - needs 2-3 hrs")
    assert s.prenatal and s.pref == {"Amira Haddad"} and s.therapists is None
    assert s.notice == 3  # a range takes the upper end


@pytest.mark.parametrize("notes", ["Rachel - 60 - next day only (shift work)", "Rachel - 60 - day before"])
def test_day_before(parser, notes):
    assert parse(parser, notes).day_before is True


def test_availability_dates(parser):
    assert parse(parser, "any - 1hr - away hunting til Oct 9").available_from == date(2026, 10, 10)
    assert parse(parser, "any - 60 - only til end of Sept then back to Ont").available_until == date(2026, 9, 30)
    assert parse(parser, "wants one before wedding Oct 3 - any female - 90").available_until == date(2026, 10, 2)
    assert parse(parser, "any - after 4 - here til Oct 10 (contract at the hospital)").available_until == date(2026, 10, 10)


def test_future_note_date_keeps_this_year(parser):
    s = parse(parser, "Amira - 60 - here til Nov 15", run_date=date(2026, 10, 30))
    assert s.available_until == date(2026, 11, 15)


@pytest.mark.parametrize("notes,reason", [
    ("tried 2x, # not in service??", "service"), ("any - 60 - Sat only. moved to Hfx?? Kelsey says", "moved"),
    ("Amira - TMJ - 45. called 10/9, going to someone in Dieppe now, take off", "take off"),
])
def test_gone_signals(parser, notes, reason):
    assert reason in parse(parser, notes).gone


def test_insurance_conditional_length_is_ignored(parser):
    s = parse(parser, "can do 90 if ins ok's it. still R/J")
    assert s.therapists == {"Rachel Thibodeau", "Josée Landry"} and s.lengths is None


def test_time_words(parser):
    assert parse(parser, "Dave or Jos - afternoons - can come in 2 hrs").earliest_start == time(12, 0)
    assert parse(parser, "called - has to be done by 2:30 (school pickup)").latest_end == time(14, 30)
    assert parse(parser, "Rachel only - evenings after 6 - 1hr").earliest_start == time(18, 0)
    assert parse(parser, "not Thurs, anyone but Dave - 1hr - after 3:30 (work)").earliest_start == time(15, 30)
    assert parse(parser, "migraines - Amira only - 45 - not before 10").earliest_start == time(10, 0)


def test_new_client_friday_after_three(parser):
    s = parse(parser, "NEW client (intake form) - any - Fri only after 3")
    assert s.new_client and s.days == {"Fri"} and s.earliest_start == time(15, 0)


def test_unknown_shorthand_is_flagged_not_guessed(parser):
    s = parser.parse("any - 60 - only on alternate blue moons", SAMPLE_RUN_DATE)
    assert s.unparsed


def test_every_sample_line_parses_completely(parser):
    for line in read_waitlist(SAMPLE["waitlist"], SAMPLE_RUN_DATE):
        spec = parser.parse(line.notes, SAMPLE_RUN_DATE)
        assert spec.unparsed == [] and spec.needs_check == [], f"line {line.line}: {spec.unparsed} {spec.needs_check}"


# ---------- a health detail next to scheduling words (Oct 30 review, plan §15 #7) ----------

def test_schedule_words_beside_a_health_detail_are_kept(parser):
    s = parse(parser, "sore neck, Rachel only - 60")
    assert s.therapists == {"Rachel Thibodeau"} and s.lengths == {60} and s.had_health_detail


def test_schedule_words_in_brackets_are_read(parser):
    s = parse(parser, "Josée only (bad back, after 3) - 60")
    assert s.therapists == {"Josée Landry"} and s.earliest_start == time(15, 0) and s.had_health_detail
    assert parse(parser, "Kelsey - 60 (Tues only)").days == {"Tue"}


@pytest.mark.parametrize("notes", ["sore neck Rachel only - 60", "Josée - 60 - post-op, mornings only til physio done",
                                   "sore neck, hockey tues - 60"])
def test_health_detail_mixed_with_scheduling_words_is_held_without_quoting(parser, notes):
    s = parser.parse(notes, SAMPLE_RUN_DATE)
    assert s.needs_check and s.unparsed == []
    assert not re.search(r"sore|neck|post-op|physio|hockey", " ".join(s.needs_check))


# ---------- 12 phrasings not in the sample, tried Oct 30 (plan §15 #6) ----------

@pytest.mark.parametrize("notes,expected", [
    ("Wednesdays after 2, 45 min", {"days": {"Wed"}, "earliest_start": time(14, 0), "lengths": {45}}),
    ("Rachel - mornings, can come in 45 min", {"therapists": {"Rachel Thibodeau"}, "start_before": time(12, 0), "notice": 0.75}),
    ("sore neck, Rachel only - 60", {"therapists": {"Rachel Thibodeau"}, "lengths": {60}}),
    ("Josée only (bad back) - Sat", {"therapists": {"Josée Landry"}, "days": {"Sat"}}),
    ("knee surgery Oct 2 - J only - 60", {"therapists": {"Josée Landry"}, "lengths": {60}}),
    ("Marc pls - 1hr - Tue", {"therapists": {"Marc Cormier"}, "lengths": {60}, "days": {"Tue"}}),
])
def test_new_combinations_of_known_words_are_read(parser, notes, expected):
    s = parse(parser, notes, date(2026, 10, 30))
    assert {k: getattr(s, k) for k in expected} == expected


@pytest.mark.parametrize("notes", [
    "Kels only - 1.5 hr - Tues or Thurs",  # until 'kels' is added to Kelsey's short forms
    "anyone - weekends", "Amira or Kelsey - before noon - 60", "eves only - 90min", "Dave or Sophie - 60",
    "any - 60 - not Tues/Thurs - needs 1 day notice",
])
def test_new_words_are_held_not_guessed(parser, notes):
    assert parser.parse(notes, date(2026, 10, 30)).unparsed


HEALTH_WORDS = re.compile(r"sciatica|knee|replacement|pregnant|\btri\b|fibro|pressure|\bmva\b|claim|\btmj\b"
                          r"|migraine|concussion|cancer|hamstring|hockey|rotator|shoulder|post-op|low back|\bhip\b|\bwks\b")


def test_parsed_lines_keep_no_health_text(parser):
    for line in read_waitlist(SAMPLE["waitlist"], SAMPLE_RUN_DATE):
        assert not HEALTH_WORDS.search(repr(parser.parse(line.notes, SAMPLE_RUN_DATE)).lower()), line.line
