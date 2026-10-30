"""Priority 1: phones, dates and names from the notebook (plan §9, discrepancies A1–A6)."""
from datetime import date

import pytest

from kettle.core.normalise import (is_same_number_marker, names_compatible, names_match_strictly,
                                   normalise_phone, parse_added_date)

RUN = date(2026, 10, 21)


@pytest.mark.parametrize("raw", ["506-555-0101", "506 555 0101", "(506) 555-0101", "5065550101",
                                 "(506)555-0101", "1-506-555-0101"])
def test_phone_formats_become_ten_digits(raw):
    assert normalise_phone(raw) == "5065550101"


@pytest.mark.parametrize("raw", ["555-0101", "", "call his son"])
def test_unreadable_phone_is_none(raw):
    assert normalise_phone(raw) is None


@pytest.mark.parametrize("raw,expected", [("same #", True), ("same number", True), ("Same #", True),
                                          ("506-555-0101", False)])
def test_same_number_marker(raw, expected):
    assert is_same_number_marker(raw) is expected


@pytest.mark.parametrize("raw,expected", [
    ("Jul 6", date(2026, 7, 6)), ("7/14", date(2026, 7, 14)), ("Sept 1", date(2026, 9, 1)),
    ("10/19", date(2026, 10, 19)), ("Oct 13", date(2026, 10, 13)), ("Aug 22", date(2026, 8, 22)),
])
def test_added_dates(raw, expected):
    assert parse_added_date(raw, RUN) == expected


def test_added_date_without_year_never_lands_in_the_future():
    assert parse_added_date("Dec 5", date(2027, 1, 10)) == date(2026, 12, 5)


def test_unreadable_date_is_none():
    assert parse_added_date("last week", RUN) is None


@pytest.mark.parametrize("a,b", [
    ("Lynn Savoie", "Lynn S."), ("Amanda Bourgeois", "Amanda B."), ("Tina Saulnier", "Tina S"),
    ("Jen LeBlanc", "Jennifer Leblanc"), ("Normand Vienneau", "Normand V"), ("Claudette Richard", "Claudette R"),
    ("Joel Bertin", "Joël Bertin"),
])
def test_same_person_names(a, b, config):
    assert names_compatible(a, b, config.nicknames)


@pytest.mark.parametrize("a,b", [("Lynn Savoie", "Lynn Smith"), ("Kim Belliveau", "Karen Belliveau"),
                                 ("Amanda B.", "Amanda Cyr")])
def test_different_people_names(a, b, config):
    assert not names_compatible(a, b, config.nicknames)


@pytest.mark.parametrize("waitlist,export", [
    ("Bob Gaudet", "Robert Gaudet"), ("Mel Arsenault", "Melanie Arsenault"),
    ("Jen LeBlanc", "Jennifer Leblanc"), ("Steph Poirier", "Stephanie Poirier"), ("Joel Bertin", "Joël Bertin"),
])
def test_waitlist_names_match_booking_export(waitlist, export, config):
    assert names_match_strictly(waitlist, export, config.nicknames)


def test_initial_only_never_matches_booking_export(config):
    # "Lynn S." could be anyone; matching it to a booking would wrongly mark someone stale
    assert not names_match_strictly("Lynn S.", "Lynn Savoie", config.nicknames)
