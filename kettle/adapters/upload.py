"""Platform adapter: syncs uploaded CSV files into the database, then matches from the database.
Plan: platform-plan.md §4.

- Appointments and late openings stand in for the Kneadly API. They are added to what's already there,
  never swapped in, so "booked since" sees every booking ever synced.
- The waitlist is a migration of the green book. New line numbers are added; a line whose text changed
  holds its person until someone checks the book. The note text is never stored.
- Matching then runs on everything in the database, with the same core code and output files as run.py.

Every file is read before anything is saved, so a file that can't be read leaves the database unchanged.
"""
import csv
import json
from datetime import datetime, timedelta
from pathlib import Path

from kettle import feedback, store
from kettle.adapters.csv_in import (InputError, check_openings_against_export, read_appointments, read_openings,
                                    read_reviewed, read_waitlist)
from kettle.config import DEFAULT_CONFIG, load_config
from kettle.core.match import match_all
from kettle.core.parse_notes import NoteParser
from kettle.core.people import STALE, build_people, build_reviewed, line_verdicts
from kettle.output import report

EXTRA_APPOINTMENT_COLUMNS = ("booked_via", "confirmation", "cancel_via")


def _extra_columns(path, columns):
    """Platform-only columns, by appointment_id; a column the file doesn't have is left out."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {row["appointment_id"].strip(): {c: (row[c] or "").strip() or None for c in columns if c in row}
                for row in csv.DictReader(f) if (row.get("appointment_id") or "").strip()}


def line_ranges(numbers):
    """[3, 7, 8, 9] -> '3, 7-9'"""
    out, numbers = [], sorted(numbers)
    for n in numbers:
        if out and n == out[-1][1] + 1:
            out[-1][1] = n
        else:
            out.append([n, n])
    return ", ".join(str(a) if a == b else f"{a}-{b}" for a, b in out) or "none"


def history_gaps(ranges, open_days):
    """Days between uploaded periods that no appointments file covered, leaving out days the clinic is closed.
    Returns [(first, last)]."""
    gaps = []
    covered = sorted(r for r in ranges if r[0] and r[1])
    if not covered:
        return gaps
    end = covered[0][1]
    for start, stop in covered[1:]:
        hole = [end + timedelta(days=i) for i in range(1, (start - end).days)]
        hole = [d for d in hole if d.weekday() in open_days]
        if hole:
            gaps.append((hole[0], hole[-1]))
        end = max(end, stop)
    return gaps


def gap_warning(first, last):
    when = f"{first:%b %d}" if first == last else f"{first:%b %d} to {last:%b %d}"
    return (f"no booking data for visits on {when}: anyone who booked a visit in those days may still be listed. "
            "Check Kneadly before calling")


def people_from_db(con, run_date, config, review_rows=()):
    """Everyone on the waitlist as the core sees them, from the database, with the desk's decisions applied.
    Returns (lines, specs, bookings, people, decisions, warnings)."""
    known = set(config.therapists)
    lines, specs = store.load_lines(con, known)
    for spec in specs.values():
        # a line saved before a therapist was removed from the settings: hold the person, as run.py would
        # (re-reading the note, the therapist's short form would be a word it can't read)
        if spec.therapists is not None and spec.therapists - known:
            spec.therapists &= known
            spec.needs_check.append("names a therapist who is no longer in the settings")
        spec.excluded &= known
        spec.pref &= known
    bookings = store.load_bookings(con)
    decisions, warnings = build_reviewed(list(review_rows) + store.decision_rows(con), {l.line for l in lines})
    people = build_people(lines, specs, bookings, run_date, config, decisions)
    # someone who said yes to an offer is off the list straight away, before the booking reaches an export; a newer
    # line in the book (they called again later) puts them back, as "booked since" does
    for r in store.active_rebookings(con):
        person = next((p for p in people if r["line"] in p.line_ids), None)
        made = datetime.strptime(r["made_at"], "%Y-%m-%d %H:%M").date()
        if person and (person.lines[-1].added is None or person.lines[-1].added <= made):
            person.mark(STALE, f"booked from the waitlist into {r['label']} on {made:%b %d}")
    return lines, specs, bookings, people, decisions, warnings


def with_desk_declines(con, opening_rows, declined=None, people=(), limit=0, now=None):
    """The command line's --declined, plus everyone who said no (or didn't answer) to an offer on the screen, plus
    everyone resting at the weekly offer limit (anti-pestering, plan §11): they're skipped everywhere except an opening
    they're being offered right now, so the next people who fit are shown instead."""
    out = {k: set(v) for k, v in (declined or {}).items()}
    said_no = store.declined_lines(con)
    for o in opening_rows:
        if o.appointment_id in said_no:
            out.setdefault(o.opening_id, set()).update(said_no[o.appointment_id])
    rest = feedback.resting(con, people, limit, now) if now else {}
    live = {r[0]: r[1] for r in con.execute("SELECT appointment_id, line FROM offers WHERE outcome IS NULL")}
    for p in people:
        if p.line_ids[0] in rest:
            for o in opening_rows:
                if live.get(o.appointment_id) not in p.line_ids:
                    out.setdefault(o.opening_id, set()).add(p.active_line)
    return out


def sync(db_path, run_date, waitlist=None, appointments=None, openings=None, out_dir="out", order=None,
         declined=None, config_path=DEFAULT_CONFIG, reviewed=None, now=None, input_names=None, opening_ids=None,
         note=None, allow_paused=False):
    """Adds the given files to the database (any of them may be left out after the first sync), matches,
    and writes the same files as run.py plus out/sync-log.txt. Matches the openings in this upload, else
    `opening_ids` (appointment IDs), else every opening in the database. The desk's decisions from the review
    screen always apply. `input_names`: how to name the files in the report when the paths are temporary
    (uploads from the screen). `note`: why this run happened, for the sync log (e.g. a desk decision).
    Stops while the owner has paused the platform, unless `allow_paused` (matching again after a settings change)."""
    config = load_config(config_path)
    order = order or config.order
    now = now or datetime.now()

    new_lines = read_waitlist(waitlist, run_date) if waitlist else None
    if new_lines and new_lines[-1].line >= store.DESK_LINE_START:
        raise InputError(f"waitlist line {new_lines[-1].line}: line numbers from {store.DESK_LINE_START} up are kept "
                         "for entries made on the review screen")
    new_bookings = read_appointments(appointments) if appointments else None
    new_openings = read_openings(openings) if openings else None
    review_rows, warnings = read_reviewed(reviewed) if reviewed else ([], [])
    parser = NoteParser(config)
    new_specs = {l.line: parser.parse(l.notes, run_date) for l in new_lines} if new_lines else {}
    files = {k: Path(v).name for k, v in (("waitlist", waitlist), ("appointments", appointments),
                                          ("openings", openings)) if v}

    con = store.connect(db_path)
    try:
        if store.is_paused(con) and not allow_paused:
            raise InputError("The platform is paused (the owner's switch on the settings screen). Use the notebook "
                             "until it's switched back on")
        if new_lines is not None and store.board_only(con):
            raise InputError("The waitlist is kept on the board now (the book was retired "
                             f"{store.get_meta(con, 'board_only_since', '')}): upload only appointments and openings")
        if store.is_empty(con) and new_lines is None:
            raise InputError("The database is empty: the first sync needs the waitlist file")
        summary, sync_warnings, visits = ({"note": note} if note else {}), [], None
        with con:
            import_id = store.new_import(con, now, run_date, files)
            if new_lines is not None:
                new, changed, unchanged, missing = store.save_lines(con, import_id, new_lines, new_specs,
                                                                    set(config.therapists))
                store.set_meta(con, "lines_with_health_detail", sum(s.had_health_detail for s in new_specs.values()))
                summary["waitlist"] = {"lines": len(new_lines), "new": new, "changed": changed,
                                       "unchanged": len(unchanged), "missing": missing}
                if changed:
                    sync_warnings.append(f"waitlist line(s) {line_ranges(changed)} changed since they were first "
                                         "saved: those people are held until someone checks the book")
                if missing:
                    sync_warnings.append(f"waitlist line(s) {line_ranges(missing)} are in the database but not in "
                                         "this file: kept as they were")
            if new_bookings is not None:
                n_new, n_updated, n_changes = store.save_bookings(
                    con, import_id, new_bookings, _extra_columns(appointments, EXTRA_APPOINTMENT_COLUMNS))
                visits = (min(b.date for b in new_bookings), max(b.date for b in new_bookings))
                summary["appointments"] = {"rows": len(new_bookings), "new": n_new, "updated": n_updated,
                                           "status_changes": n_changes,
                                           "visits": [visits[0].isoformat(), visits[1].isoformat()]}
            if new_openings is not None:
                heard = {a: x.get("heard_via") for a, x in _extra_columns(openings, ("heard_via",)).items()}
                summary["openings"] = {"rows": len(new_openings),
                                       "new": store.save_openings(con, import_id, new_openings, heard)}
            ranges = store.visit_ranges(con) + ([visits] if visits else [])
            gaps = history_gaps(ranges, store.open_weekdays(con))
            sync_warnings += [gap_warning(*g) for g in gaps]
            summary["warnings"] = sync_warnings
            store.finish_import(con, import_id, summary, visits)

        lines, specs, bookings, people, decisions, more = people_from_db(con, run_date, config, review_rows)
        warnings += more
        if new_openings is not None:
            opening_rows = store.load_openings(con, list(dict.fromkeys(o.appointment_id for o in new_openings)), now)
        else:
            opening_rows = store.load_openings(con, opening_ids, now)
        with con:
            store.save_live_notice(con, opening_rows)
        results = match_all(opening_rows, people, bookings, config, order,
                            with_desk_declines(con, opening_rows, declined, people, config.max_offers_per_week, now))
        warnings += check_openings_against_export(opening_rows, bookings)
        warnings += [f"{o.opening_id}: therapist '{o.therapist}' doesn't match exactly one therapist in "
                     "config/clinic.json, so this opening gets nobody"
                     for o in opening_rows if config.therapist_by_name(o.therapist) is None]
        warnings += sync_warnings

        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        verdicts = line_verdicts(people, decisions.ignore)
        report.write_core(out / "core", people, opening_rows, config)
        report.write_matches_txt(out / "matches.txt", results, run_date, order, config)
        report.write_matches_csv(out / "matches.csv", results, config)
        report.write_line_verdicts(out / "line-verdicts.csv", verdicts)
        given = (("waitlist", waitlist), ("appointments", appointments), ("openings", openings))
        inputs = {"database": str(db_path), **{k: (input_names or {}).get(k, v) for k, v in given if v}}
        if reviewed:
            inputs["reviewed"] = reviewed
        report.write_preprocess_report(out / "preprocess-report.txt", people, lines, specs, warnings, run_date,
                                       inputs, decisions,
                                       health_lines=int(store.get_meta(con, "lines_with_health_detail", 0)))
        with con:
            store.save_run(con, import_id, run_date, order, [report.person_record(p, config) for p in people], results)
            store.add_run_warnings(con, import_id, warnings)
        matched = ("from this upload" if new_openings is not None
                   else "from the last run" if opening_ids is not None else "in the database")
        write_sync_log(out / "sync-log.txt", con, db_path, import_id, len(opening_rows), matched)
        return {"config": config, "people": people, "results": results, "verdicts": verdicts, "warnings": warnings,
                "lines": lines, "summary": summary, "gaps": gaps, "import_id": import_id}
    finally:
        con.close()


def write_sync_log(path, con, db_path, import_id, n_matched, matched):
    """What this sync changed, what the database now holds, and every earlier sync."""
    history = store.import_history(con)
    this = next(h for h in history if h["id"] == import_id)
    s = json.loads(this["summary"])
    out = [f"Sync log · database {db_path}",
           f"This sync (#{import_id}): {this['synced_at']} · run date {this['run_date']}"]
    if s.get("note"):
        out.append(f"  {s['note']}")
    if "waitlist" in s:
        w = s["waitlist"]
        out.append(f"  {this['waitlist_file']}: {w['lines']} lines · new: {line_ranges(w['new'])} · changed: "
                   f"{line_ranges(w['changed'])} · already saved: {w['unchanged']}")
    if "appointments" in s:
        a = s["appointments"]
        out.append(f"  {this['appointments_file']}: {a['rows']} rows, visits {a['visits'][0]} to {a['visits'][1]} · "
                   f"new: {a['new']} · updated: {a['updated']} · status changes: {a['status_changes']}")
    if "openings" in s:
        o = s["openings"]
        out.append(f"  {this['openings_file']}: {o['rows']} openings · new: {o['new']}")
    n_lines = con.execute("SELECT COUNT(*) FROM waitlist_lines").fetchone()[0]
    n_book, first, last = con.execute("SELECT COUNT(*), MIN(date), MAX(date) FROM bookings").fetchone()
    n_open = con.execute("SELECT COUNT(*) FROM openings").fetchone()[0]
    out += ["", f"Database now: {n_lines} waitlist lines · {n_book} bookings"
                + (f" (visits {first} to {last})" if n_book else "") + f" · {n_open} openings",
            f"Matched: {n_matched} opening(s) {matched}",
            "", "Warnings from this sync:"] + ([f"  {w}" for w in s["warnings"]] or ["  none"])
    out += ["", "All syncs:"]
    for h in history:
        names = ", ".join(f for f in (h["waitlist_file"], h["appointments_file"], h["openings_file"]) if f)
        out.append(f"  #{h['id']} {h['synced_at']} · run date {h['run_date']} · "
                   f"{names or json.loads(h['summary']).get('note') or 'no files'}")
    Path(path).write_text("\n".join(out) + "\n", encoding="utf-8")
