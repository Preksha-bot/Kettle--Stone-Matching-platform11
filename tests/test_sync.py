"""Platform step 1 (platform-plan.md §4, §5, §14): the database seeded with the sample, files synced into it,
and matching from it. The first sync must give the same files as run.py; later uploads add to the history."""
import csv
import json
import re
import sqlite3
from dataclasses import fields
from datetime import date, datetime

import pytest

from conftest import SAMPLE, SAMPLE_RUN_DATE
from kettle import store
from kettle.adapters.csv_in import InputError, read_waitlist
from kettle.adapters.upload import history_gaps, line_ranges, sync
from kettle.core.parse_notes import LineSpec, NoteParser
from kettle.pipeline import run
from test_privacy_and_unseen import HEALTH_WORDS

NOW = datetime(2026, 10, 30, 9, 0)
OCT_30 = date(2026, 10, 30)
SAME_FILES = ["matches.csv", "matches.txt", "line-verdicts.csv", "core/people.json", "core/openings.csv"]


def seed(tmp_path, run_date=SAMPLE_RUN_DATE, out="seed-out", **files):
    """The first sync: the sample files (or the ones given) into a new database."""
    files = {**SAMPLE, **files}
    db = tmp_path / "kettle.db"
    result = sync(db, run_date, files["waitlist"], files["appointments"], files["openings"], tmp_path / out, now=NOW)
    return db, result


def write_rows(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return str(path)


def read_rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def waitlist_plus(tmp_path, *extra, change=None):
    """A copy of the sample waitlist with lines added at the end, and optionally one line's notes changed."""
    rows = read_rows(SAMPLE["waitlist"])
    if change:
        line, notes = change
        rows[line - 1]["notes"] = notes
    for i, (added, name, phone, notes) in enumerate(extra, len(rows) + 1):
        rows.append({"line": str(i), "added": added, "name": name, "phone": phone, "notes": notes})
    return write_rows(tmp_path / "waitlist-new.csv", rows)


def appointments_where(tmp_path, name, keep):
    return write_rows(tmp_path / name, [r for r in read_rows(SAMPLE["appointments"]) if keep(r)])


def without_inputs_block(text):
    return re.sub(r"Inputs \(read only, never changed\):\n(?:  .*\n)*", "", text)


# ---------- the first sync = the current script ----------

def test_first_sync_gives_the_same_files_as_run_py(tmp_path, sample):
    seed(tmp_path)
    for name in SAME_FILES:
        assert (tmp_path / "seed-out" / name).read_bytes() == (sample["out"] / name).read_bytes(), name
    ours = (tmp_path / "seed-out" / "preprocess-report.txt").read_text(encoding="utf-8")
    script = (sample["out"] / "preprocess-report.txt").read_text(encoding="utf-8")
    assert without_inputs_block(ours) == without_inputs_block(script)


def test_matching_again_from_the_database_alone_gives_the_same_names(tmp_path, sample):
    db, _ = seed(tmp_path)
    sync(db, SAMPLE_RUN_DATE, out_dir=tmp_path / "again", now=NOW)
    assert (tmp_path / "again" / "matches.csv").read_bytes() == (sample["out"] / "matches.csv").read_bytes()


def test_every_line_spec_survives_the_database(config):
    """What's read from each note comes back from the database unchanged, except what is never kept."""
    parser = NoteParser(config)
    for line in read_waitlist(SAMPLE["waitlist"], SAMPLE_RUN_DATE):
        spec = parser.parse(line.notes, SAMPLE_RUN_DATE)
        back = store.spec_from_json(store.spec_to_json(spec))
        for f in fields(LineSpec):
            if f.name == "had_health_detail":
                assert back.had_health_detail is False
            elif f.name == "gone":
                assert bool(back.gone) == bool(spec.gone)
            else:
                assert getattr(back, f.name) == getattr(spec, f.name), (line.line, f.name)


def test_the_first_sync_needs_the_waitlist(tmp_path):
    with pytest.raises(InputError, match="first sync needs the waitlist"):
        sync(tmp_path / "k.db", SAMPLE_RUN_DATE, appointments=SAMPLE["appointments"], out_dir=tmp_path / "o")


# ---------- later uploads add to the database ----------

def test_booking_history_is_kept_across_uploads(tmp_path):
    """The sample export in two parts gives the same names as the whole export. A 2-day file on its own
    can't see who booked earlier, so the database keeps every booking ever synced (plan §4.3)."""
    early = appointments_where(tmp_path, "early.csv", lambda r: r["date"] < "2026-10-16")
    last_two_days = appointments_where(tmp_path, "two-days.csv", lambda r: r["date"] >= "2026-10-16")
    db, _ = seed(tmp_path, appointments=early)
    result = sync(db, OCT_30, appointments=last_two_days, out_dir=tmp_path / "later", now=NOW)
    run(SAMPLE["waitlist"], SAMPLE["appointments"], SAMPLE["openings"], OCT_30, tmp_path / "whole")
    assert (tmp_path / "later" / "matches.csv").read_bytes() == (tmp_path / "whole" / "matches.csv").read_bytes()
    got_in = [21, 25, 31, 35]  # Bob Gaudet, Steph Poirier, Claudette Richard, Jen LeBlanc: booked before Oct 16
    assert all(result["verdicts"][line] == "stale" for line in got_in)

    alone = run(SAMPLE["waitlist"], last_two_days, SAMPLE["openings"], OCT_30, tmp_path / "alone")
    assert all(alone["verdicts"][line] != "stale" for line in got_in)


def test_a_gap_between_uploads_is_named(tmp_path):
    early = appointments_where(tmp_path, "early.csv", lambda r: r["date"] <= "2026-10-10")
    last_two_days = appointments_where(tmp_path, "two-days.csv", lambda r: r["date"] >= "2026-10-16")
    db, first = seed(tmp_path, appointments=early)
    assert first["gaps"] == []
    result = sync(db, OCT_30, appointments=last_two_days, out_dir=tmp_path / "later", now=NOW)
    # Sun Oct 11 isn't a gap: the clinic has no Sunday bookings
    assert result["gaps"] == [(date(2026, 10, 12), date(2026, 10, 15))]
    for name in ("sync-log.txt", "preprocess-report.txt"):
        assert "no booking data for visits on Oct 12 to Oct 15" in (tmp_path / "later" / name).read_text(encoding="utf-8")


def test_history_gaps_ignore_overlaps_and_closed_days():
    mon_to_sat = {0, 1, 2, 3, 4, 5}
    d = lambda day: date(2026, 10, day)  # noqa: E731
    assert history_gaps([(d(1), d(10)), (d(5), d(17))], mon_to_sat) == []
    assert history_gaps([(d(12), d(17)), (d(1), d(10))], mon_to_sat) == []  # Oct 11 is a Sunday
    assert history_gaps([(d(1), d(10)), (d(20), d(21))], mon_to_sat) == [(d(12), d(19))]


def test_same_files_twice_changes_nothing(tmp_path):
    db, _ = seed(tmp_path)
    again = sync(db, SAMPLE_RUN_DATE, SAMPLE["waitlist"], SAMPLE["appointments"], SAMPLE["openings"],
                 tmp_path / "again", now=NOW)
    s = again["summary"]
    assert s["waitlist"]["new"] == [] and s["waitlist"]["changed"] == [] and s["waitlist"]["unchanged"] == 60
    assert (s["appointments"]["new"], s["appointments"]["status_changes"]) == (0, 0)
    assert s["openings"]["new"] == 0
    con = sqlite3.connect(db)
    assert [con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("waitlist_lines", "bookings", "openings")] \
        == [60, 595, 44]
    assert (tmp_path / "again" / "matches.csv").read_bytes() == (tmp_path / "seed-out" / "matches.csv").read_bytes()


def test_new_lines_are_added_and_merged_into_the_same_person(tmp_path):
    db, _ = seed(tmp_path)
    book = waitlist_plus(tmp_path, ("10/20", "Amanda B.", "506-555-0125", "called again, still R/J"),
                         ("10/20", "Paul Arsenault", "506-555-0190", "any - 60 - after 4"))
    result = sync(db, SAMPLE_RUN_DATE, waitlist=book, out_dir=tmp_path / "o", now=NOW)
    assert result["summary"]["waitlist"]["new"] == [61, 62]
    amanda = next(p for p in result["people"] if 42 in p.line_ids)
    assert amanda.line_ids == [26, 42, 61] and amanda.status == "active"
    paul = next(p for p in result["people"] if 62 in p.line_ids)
    assert paul.line_ids == [62] and paul.status == "active"


def test_a_changed_old_line_holds_that_person_until_checked(tmp_path):
    db, _ = seed(tmp_path)
    book = waitlist_plus(tmp_path, change=(39, "any - 60 - mornings"))
    result = sync(db, SAMPLE_RUN_DATE, waitlist=book, out_dir=tmp_path / "o", now=NOW)
    assert result["summary"]["waitlist"]["changed"] == [39]
    joel = next(p for p in result["people"] if 39 in p.line_ids)
    assert joel.status == "review" and "line 39: changed since it was first saved, check the notebook" in joel.reasons
    assert any("line(s) 39 changed" in w for w in result["warnings"])
    later = sync(db, SAMPLE_RUN_DATE, out_dir=tmp_path / "later", now=NOW)  # still held on the next run
    assert next(p for p in later["people"] if 39 in p.line_ids).status == "review"


def test_a_status_change_becomes_a_booking_event(tmp_path):
    db, _ = seed(tmp_path)
    rows = read_rows(SAMPLE["appointments"])
    target = next(r for r in rows if r["status"] == "Completed")
    target.update(status="Late cancel", cancelled_at=f"{target['date']} 07:30", cancel_via="text reply")
    result = sync(db, SAMPLE_RUN_DATE, appointments=write_rows(tmp_path / "a.csv", rows), out_dir=tmp_path / "o",
                  now=NOW)
    assert result["summary"]["appointments"]["status_changes"] == 1
    con = sqlite3.connect(db)
    assert con.execute("SELECT appointment_id, old_status, new_status FROM booking_events").fetchall() == \
        [(target["appointment_id"], "Completed", "Late cancel")]
    assert con.execute("SELECT cancel_via FROM bookings WHERE appointment_id = ?",
                       (target["appointment_id"],)).fetchone()[0] == "text reply"


def test_the_same_cancellation_in_two_files_is_one_opening(tmp_path):
    db, _ = seed(tmp_path)
    rows = read_rows(SAMPLE["openings"])[:3]
    for r in rows:
        r["opening_id"] = "N" + r["opening_id"][1:]  # a new file numbers its openings again
    result = sync(db, SAMPLE_RUN_DATE, openings=write_rows(tmp_path / "o.csv", rows), out_dir=tmp_path / "o", now=NOW)
    assert result["summary"]["openings"] == {"rows": 3, "new": 0}
    assert [r.opening.opening_id for r in result["results"]] == ["N01", "N02", "N03"]
    assert sqlite3.connect(db).execute("SELECT COUNT(*) FROM openings").fetchone()[0] == 44


def test_a_file_that_cant_be_read_saves_nothing(tmp_path):
    db, _ = seed(tmp_path)
    bad = tmp_path / "bad.csv"
    bad.write_text("appointment_id,date\nA-1,2026-10-29\n", encoding="utf-8")
    with pytest.raises(InputError, match="missing column"):
        sync(db, OCT_30, waitlist=waitlist_plus(tmp_path, ("10/29", "New Person", "506-555-0191", "any")),
             appointments=str(bad), out_dir=tmp_path / "o", now=NOW)
    con = sqlite3.connect(db)
    assert con.execute("SELECT COUNT(*) FROM imports").fetchone()[0] == 1
    assert con.execute("SELECT COUNT(*) FROM waitlist_lines").fetchone()[0] == 60


def test_input_files_are_never_changed_by_a_sync(tmp_path):
    before = {k: open(v, "rb").read() for k, v in SAMPLE.items()}
    seed(tmp_path)
    assert before == {k: open(v, "rb").read() for k, v in SAMPLE.items()}


# ---------- privacy ----------

def test_the_database_keeps_no_note_text_and_no_unread_word(tmp_path):
    """An unknown word may be a health detail ("shingles" isn't in the health word list): the person is held,
    but the word is never stored or printed. The note text isn't stored at all (plan §4.4, risk D2)."""
    book = waitlist_plus(tmp_path, ("10/20", "Gilles Probe", "506-555-0199", "any - 1hr - AM - shingles"))
    db, result = seed(tmp_path, waitlist=book)
    held = next(p for p in result["people"] if 61 in p.line_ids)
    assert held.status == "review" and f"line 61: can't read '{store.UNREAD_WORD}'" in held.reasons

    raw = db.read_bytes().decode("utf-8", errors="ignore")
    for phrase in ("shingles", "works at the bank", "drives in from Shediac", "Kelsey says"):
        assert phrase.lower() not in raw.lower(), phrase
    assert HEALTH_WORDS.search(raw) is None, HEALTH_WORDS.search(raw)
    con = sqlite3.connect(db)
    assert "notes" not in [r[1] for r in con.execute("PRAGMA table_info(waitlist_lines)")]

    for f in (tmp_path / "seed-out").rglob("*"):
        if f.is_file():
            text = f.read_text(encoding="utf-8")
            assert "shingles" not in text and HEALTH_WORDS.search(text) is None, f.name


def test_gone_notes_keep_only_the_reason(config):
    spec = NoteParser(config).parse("moved to Hfx?? Kelsey says", SAMPLE_RUN_DATE)
    stored = json.loads(store.spec_to_json(spec))
    assert stored["gone"] == "moved"


def test_line_ranges():
    assert line_ranges([3, 7, 8, 9]) == "3, 7-9"
    assert line_ranges([]) == "none"
