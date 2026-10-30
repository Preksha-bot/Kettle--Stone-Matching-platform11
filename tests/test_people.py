"""Priority 1: grouping lines into people, merging, and out-of-date checks (A1, A2, B3, B6, B7)."""
import csv
from datetime import date, datetime, time

from conftest import KEY, SAMPLE, make_people
from kettle.adapters.csv_in import Booking
from kettle.pipeline import run


def key_line_verdicts():
    with open(KEY, encoding="utf-8") as f:
        return {int(r["id"][1:]): r["answer"] for r in csv.DictReader(f) if r["id"].startswith("W")}


def test_all_60_line_verdicts_match_tanya(sample):
    assert sample["verdicts"] == key_line_verdicts()


def test_stale_reasons_are_the_right_kind(sample):
    reasons = {p.active_line: p.reasons[0] for p in sample["people"] if p.status == "stale"}
    assert "booked since" in reasons[31] and "Robert Gaudet" in reasons[21]
    assert reasons[50] == "number not in service" and reasons[23] == "moved away"
    assert "Sep 30" in reasons[11] and "over 60 days" in reasons[1]


def test_marcel_booked_before_his_line_stays_active(sample):
    marcel = next(p for p in sample["people"] if p.active_line == 18)
    assert marcel.status == "active"


def test_newer_line_overrides_only_what_it_mentions(sample):
    by_line = {p.active_line: p for p in sample["people"]}
    tina = by_line[43]
    assert tina.therapists == {"Kelsey Babineau", "Amira Haddad"} and tina.latest_end == time(14, 30)
    mireille = by_line[60]
    assert mireille.days_excluded == {"Thu"} and mireille.start_before == time(12, 0) and mireille.contact == "text only"
    carole = by_line[48]
    assert carole.therapists == {"Josée Landry", "Rachel Thibodeau"} and carole.lengths == {60}
    luc = by_line[53]
    assert luc.available_from == date(2026, 10, 10) and luc.days_excluded == {"Sat"}


def test_first_asked_is_the_earliest_line(sample):
    pauline = next(p for p in sample["people"] if p.active_line == 51)
    assert pauline.first_asked == date(2026, 7, 14)


def test_same_phone_and_compatible_names_merge(config):
    people = make_people([("Oct 1", "Lynn Savoie", "506-555-0105", "J only - 45"),
                          ("Oct 5", "Lynn S.", "same #", "again - 45 or 60")], config)
    assert len(people) == 1 and people[0].status == "active" and people[0].lengths == {45, 60}


def test_same_phone_different_name_is_held_for_review(config):
    people = make_people([("Oct 1", "Lynn Savoie", "506-555-0105", "any - 60"),
                          ("Oct 5", "Paul Savoie", "506-555-0105", "any - 60")], config)
    assert len(people) == 2 and all(p.status == "review" for p in people)


def test_same_name_different_phone_is_held_for_review(config):
    people = make_people([("Oct 1", "Lynn Savoie", "506-555-0105", "any - 60"),
                          ("Oct 5", "Lynn S.", "506-555-0999", "any - 60")], config)
    assert len(people) == 2 and all(p.status == "review" for p in people)


def test_shared_first_name_only_is_not_flagged(config):
    people = make_people([("Oct 1", "Amanda Bourgeois", "506-555-0125", "any - 60"),
                          ("Oct 5", "Amanda Cyr", "506-555-0999", "any - 60")], config)
    assert all(p.status == "active" for p in people)


def test_unresolved_same_number_is_held_for_review(config):
    people = make_people([("Oct 1", "Kim Belliveau", "506-555-0112", "any - 60"),
                          ("Oct 5", "Greg W.", "same #", "any - 60")], config)
    greg = next(p for p in people if p.name == "Greg W.")
    assert greg.status == "review"


def test_regular_wanting_an_extra_who_books_is_held_not_dropped(config):
    booking = Booking("A-1", date(2026, 10, 20), time(9), time(10), 60, "Marc Cormier", "K-1", "Marcel Bujold",
                      datetime(2026, 10, 10, 9, 0), "Completed", None, "")
    people = make_people([("Sep 2", "Marcel Bujold", "506-555-0117",
                           "Marc's reg, wants an extra - Marc only - AM")], config, [booking])
    assert people[0].status == "review"


def test_run_date_oct_30_makes_late_august_lines_stale(tmp_path):
    result = run(SAMPLE["waitlist"], SAMPLE["appointments"], SAMPLE["openings"], date(2026, 10, 30), tmp_path)
    status = {p.active_line: p.status for p in result["people"]}
    assert status[10] == "stale" and status[12] == "stale" and status[14] == "stale"  # Aug 24, 26, 29
    assert status[18] == "active"  # Sep 2: 58 days, still in
