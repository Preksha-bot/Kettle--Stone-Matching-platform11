"""End to end: CSV files -> core data -> matches -> output files. Used by run.py and the tests."""
from pathlib import Path

from kettle.adapters.csv_in import (check_openings_against_export, read_appointments, read_openings, read_reviewed,
                                    read_waitlist)
from kettle.config import load_config, DEFAULT_CONFIG
from kettle.core.match import match_all
from kettle.core.parse_notes import NoteParser
from kettle.core.people import build_people, build_reviewed, line_verdicts
from kettle.output import report


def run(waitlist, appointments, openings, run_date, out_dir="out", order=None, declined=None,
        config_path=DEFAULT_CONFIG, reviewed=None):
    """`reviewed`: the desk's decisions file (reviewed.csv) or None. Never pass it on demo files."""
    config = load_config(config_path)
    order = order or config.order

    lines = read_waitlist(waitlist, run_date)
    bookings = read_appointments(appointments)
    opening_rows = read_openings(openings)
    review_rows, warnings = read_reviewed(reviewed) if reviewed else ([], [])
    decisions, more = build_reviewed(review_rows, {l.line for l in lines})
    warnings += more

    parser = NoteParser(config)
    specs = {l.line: parser.parse(l.notes, run_date) for l in lines}
    people = build_people(lines, specs, bookings, run_date, config, decisions)
    results = match_all(opening_rows, people, bookings, config, order, declined)

    warnings += check_openings_against_export(opening_rows, bookings)
    warnings += [f"{o.opening_id}: therapist '{o.therapist}' doesn't match exactly one therapist in "
                 "config/clinic.json, so this opening gets nobody"
                 for o in opening_rows if config.therapist_by_name(o.therapist) is None]

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    verdicts = line_verdicts(people, decisions.ignore)
    report.write_core(out / "core", people, opening_rows, config)
    report.write_matches_txt(out / "matches.txt", results, run_date, order, config)
    report.write_matches_csv(out / "matches.csv", results, config)
    report.write_line_verdicts(out / "line-verdicts.csv", verdicts)
    inputs = {"waitlist": waitlist, "appointments": appointments, "openings": openings}
    if reviewed:
        inputs["reviewed"] = reviewed
    report.write_preprocess_report(out / "preprocess-report.txt", people, lines, specs, warnings, run_date,
                                   inputs, decisions)
    return {"config": config, "people": people, "results": results, "verdicts": verdicts,
            "warnings": warnings, "specs": specs, "lines": lines, "reviewed": decisions}
