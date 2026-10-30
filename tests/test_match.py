"""Priority 2: the matcher, rule by rule, then the golden test on all 44 sample openings."""
import copy
from datetime import date, datetime, time

import pytest

from conftest import KEY, make_people
from kettle.adapters.csv_in import Opening
from kettle.core.match import ORDERS, match_all, match_opening, why_not
from score import read_key


def opening(day, start, therapist, length=60, notice=5.0, cancelled=None, kind="late cancel"):
    d = date.fromisoformat(day)
    s = time.fromisoformat(start)
    cancelled = cancelled or datetime.combine(d, s)
    return Opening("T1", "A-T1", d, s, length, therapist, kind, cancelled, notice)


def person(config, notes, added="Oct 1"):
    return make_people([(added, "Test Person", "506-555-0001", notes)], config)[0]


def fits(config, notes, o):
    p = person(config, notes)
    return why_not(p, o, config.therapist_by_name(o.therapist), config) is None


# ---------- one rule at a time ----------

def test_pregnancy_overrides_any(config):
    for t, ok in [("Amira Haddad", True), ("Kelsey Babineau", True), ("Rachel Thibodeau", False),
                  ("Josée Landry", False), ("Dave Melanson", False)]:
        assert fits(config, "pregnant - any - 60", opening("2026-10-14", "11:00", t)) is ok


def test_female_only(config):
    assert fits(config, "female only - 60", opening("2026-10-14", "11:00", "Rachel Thibodeau"))
    assert not fits(config, "female only - 60", opening("2026-10-13", "11:00", "Dave Melanson"))


def test_shorter_request_fits_longer_opening_not_the_reverse(config):
    assert fits(config, "any - 60", opening("2026-10-13", "11:00", "Kelsey Babineau", length=90))
    assert not fits(config, "any - 90", opening("2026-10-13", "11:00", "Kelsey Babineau", length=60))
    assert not fits(config, "any - 45", opening("2026-10-13", "11:00", "Kelsey Babineau", length=30))


def test_mornings_mean_starting_before_noon(config):
    assert fits(config, "any - AM", opening("2026-10-14", "11:45", "Rachel Thibodeau"))
    assert not fits(config, "any - AM", opening("2026-10-14", "12:00", "Rachel Thibodeau"))


def test_done_by_uses_the_visit_length(config):
    assert fits(config, "any - 1hr - done by 2:30", opening("2026-10-14", "13:30", "Rachel Thibodeau"))
    assert not fits(config, "any - 1hr - done by 2:30", opening("2026-10-14", "13:45", "Rachel Thibodeau"))


def test_lunch_person_fits_half_hour_inside_a_longer_opening(config):
    notes = "any - 30 or 45 - on his lunch 12-1 only - 30 min notice ok"
    assert fits(config, notes, opening("2026-10-14", "12:30", "Rachel Thibodeau", length=60))
    assert not fits(config, notes, opening("2026-10-14", "11:30", "Rachel Thibodeau"))
    assert not fits(config, notes, opening("2026-10-17", "12:00", "Amira Haddad"))  # Saturday


def test_notice_default_two_hours(config):
    assert not fits(config, "any - 60", opening("2026-10-14", "11:00", "Rachel Thibodeau", notice=1.9))
    assert fits(config, "any - 60", opening("2026-10-14", "11:00", "Rachel Thibodeau", notice=2.0))
    assert fits(config, "any - 60 - can come in 30 min", opening("2026-10-14", "11:00", "Rachel Thibodeau", notice=1.2))


def test_day_before_means_cancelled_on_an_earlier_day(config):
    notes = "Rachel - 60 - next day only"
    same_day = opening("2026-10-14", "11:00", "Rachel Thibodeau", notice=8, cancelled=datetime(2026, 10, 14, 3, 0))
    night_before = opening("2026-10-14", "11:00", "Rachel Thibodeau", notice=12, cancelled=datetime(2026, 10, 13, 23, 0))
    assert not fits(config, notes, same_day) and fits(config, notes, night_before)


def test_available_from(config):
    notes = "any - 1hr - away hunting til Oct 9"
    assert not fits(config, notes, opening("2026-10-09", "11:00", "Rachel Thibodeau"))
    assert fits(config, notes, opening("2026-10-14", "11:00", "Rachel Thibodeau"))


def test_no_show_is_never_offered(config):
    p = person(config, "any - 60 - can come in 30 min")
    r = match_opening(opening("2026-10-14", "11:00", "Rachel Thibodeau", notice=0, kind="no-show"), [p], [], config)
    assert r.picks == []


def test_reasons_shown_at_the_desk_never_name_the_health_rule(config):
    p = person(config, "pregnant, 2nd tri - any - 60")
    reason = why_not(p, opening("2026-10-14", "11:00", "Rachel Thibodeau"), config.therapist_by_name("Rachel"), config)
    assert "pregnan" not in reason and "prenatal" not in reason


# ---------- the sample, end to end ----------

def test_golden_every_opening_matches_and_no_wrong_names(sample):
    key, _ = read_key(KEY)
    for r in sample["results"]:
        shown = {p.person.active_line for p in r.picks}
        truth = key[r.opening.opening_id]
        assert len(shown) <= 3
        assert shown <= truth, f"{r.opening.opening_id}: {shown - truth} not on Tanya's list"
        assert bool(shown) == bool(truth), f"{r.opening.opening_id}: shown {shown}, Tanya {truth}"


def test_full_fit_list_equals_tanyas_full_list(sample):
    """Stronger than the demo rule: with no 3-name cap, the set of people who fit is exactly Tanya's list."""
    key, _ = read_key(KEY)
    config = copy.copy(sample["config"])
    config.max_names = 99
    for r in match_all([x.opening for x in sample["results"]], sample["people"], [], config):
        assert {p.person.active_line for p in r.picks} == key[r.opening.opening_id], r.opening.opening_id


def test_all_eight_no_shows_get_nobody(sample):
    no_shows = [r for r in sample["results"] if r.opening.is_no_show]
    assert len(no_shows) == 8 and all(not r.picks for r in no_shows)


@pytest.mark.parametrize("order", ORDERS)
def test_every_order_offers_people_from_the_same_fit_list(sample, order):
    key, _ = read_key(KEY)
    for r in match_all([x.opening for x in sample["results"]], sample["people"], [], sample["config"], order):
        assert {p.person.active_line for p in r.picks} <= key[r.opening.opening_id]


def test_declined_people_are_skipped_on_rerun(sample):
    o1 = next(r.opening for r in sample["results"] if r.opening.opening_id == "O01")
    first = match_opening(o1, sample["people"], [], sample["config"])
    said_no = {p.person.active_line for p in first.picks}
    second = match_opening(o1, sample["people"], [], sample["config"], declined=said_no)
    assert said_no.isdisjoint({p.person.active_line for p in second.picks})
    assert [p.person.active_line for p in second.picks] == [57]  # the 4th person on Tanya's list
