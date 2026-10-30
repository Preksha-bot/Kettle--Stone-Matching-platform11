"""Writes what the desk reads (matches.txt), what gets scored (matches.csv), and the preprocessing report."""
import csv
import json
from pathlib import Path

from kettle.core.match import hm


def phone_display(digits):
    return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}" if digits else "(no number)"


def opening_header(o, config):
    t = config.therapist_by_name(o.therapist)
    who = t.first_name if t else o.therapist
    return (f"{o.opening_id}  {o.date:%a %b %d} {o.start:%H:%M} · {who} · {o.length_min} min · "
            f"{o.hours_notice:g} h notice" + ("  (no-show)" if o.is_no_show else ""))


def write_matches_txt(path, results, run_date, order, config):
    out = [f"Kettle & Stone · who to offer each late opening · run date {run_date:%a %b %d, %Y} · order: {order}",
           "Call #1 first, one offer at a time. If no / no answer after ~20 min, call #2, then #3.",
           "Book the yes in Kneadly and link it ('rebooked into'). Nothing here is sent to anyone.", ""]
    for r in results:
        out.append(opening_header(r.opening, config))
        if not r.picks:
            out.append(f"  nobody: {r.note}")
        width = max([len(p.person.name) for p in r.picks] + [10])
        for i, p in enumerate(r.picks, 1):
            tag = f"   [{'; '.join(p.tags)}]" if p.tags else ""
            out.append(f"  {i}. {p.person.name:<{width}}  {phone_display(p.person.phone)}  line {p.person.active_line:<3} "
                       f"{p.summary}{tag}")
        if r.closest and not r.opening.is_no_show:
            out.append("  not offered: " + " · ".join(f"{p.name} ({why})" for p, why in r.closest))
        out.append("")
    Path(path).write_text("\n".join(out), encoding="utf-8")


def write_matches_csv(path, results, config):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["opening_id", "date", "day", "start", "therapist", "length_min", "hours_notice",
                    "rank", "line", "name", "phone", "can_take", "flags"])
        for r in results:
            o = r.opening
            base = [o.opening_id, o.date.isoformat(), o.day, o.start.strftime("%H:%M"), o.therapist,
                    o.length_min, f"{o.hours_notice:g}"]
            if not r.picks:
                w.writerow(base + [0, "", "(nobody)", "", r.note, ""])
            for i, p in enumerate(r.picks, 1):
                w.writerow(base + [i, p.person.active_line, p.person.name, phone_display(p.person.phone),
                                   p.summary, "; ".join(p.tags)])


def write_line_verdicts(path, verdicts):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["line", "verdict"])
        for line in sorted(verdicts):
            w.writerow([f"W{line:02d}", verdicts[line]])


def person_record(p, config):
    from kettle.core.match import allowed_therapists

    def t(x):
        return x.strftime("%H:%M") if x else None

    def d(x):
        return x.isoformat() if x else None
    return {
        "person_id": f"P-{p.phone}" if p.phone else f"P-L{p.lines[0].line}",
        "name": p.name, "phone": p.phone, "lines": p.line_ids, "active_line": p.active_line,
        "status": p.status, "reasons": p.reasons,
        "therapists_allowed": sorted(allowed_therapists(p, config)), "excluded": sorted(p.excluded),
        "female_only": p.female_only, "prenatal_only": p.prenatal, "needs": sorted(p.needs), "pref": sorted(p.pref),
        "lengths": sorted(p.lengths), "days": sorted(p.days) if p.days else None,
        "days_excluded": sorted(p.days_excluded),
        "earliest_start": t(p.earliest_start), "start_before": t(p.start_before), "latest_end": t(p.latest_end),
        "notice_hours": p.notice, "day_before": p.day_before,
        "available_from": d(p.available_from), "available_until": d(p.available_until),
        "contact": p.contact, "new_client": p.new_client, "regular_of": p.regular_of,
        "first_asked": d(p.first_asked), "last_contact": d(p.last_contact),
    }


def write_core(core_dir, people, openings, config):
    core_dir = Path(core_dir)
    core_dir.mkdir(parents=True, exist_ok=True)
    (core_dir / "people.json").write_text(
        json.dumps([person_record(p, config) for p in people], indent=2, ensure_ascii=False), encoding="utf-8")
    with open(core_dir / "openings.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["opening_id", "appointment_id", "therapist", "date", "day", "start", "length_min", "kind",
                    "cancelled_at", "hours_notice"])
        for o in openings:
            w.writerow([o.opening_id, o.appointment_id, o.therapist, o.date.isoformat(), o.day,
                        o.start.strftime("%H:%M"), o.length_min, o.kind,
                        o.cancelled_at.strftime("%Y-%m-%d %H:%M") if o.cancelled_at else "", f"{o.hours_notice:g}"])


def write_preprocess_report(path, people, lines, specs, warnings, run_date, inputs, reviewed=None, health_lines=None):
    """`health_lines`: the count of lines with a health detail, when the specs no longer say (the platform's
    database doesn't keep that per line)."""
    from kettle.core.people import start_index

    active = [p for p in people if p.status == "active"]
    stale = [p for p in people if p.status == "stale"]
    review = [p for p in people if p.status == "review"]
    merged = [p for p in people if len(p.lines) > 1]
    health = health_lines if health_lines is not None else sum(1 for s in specs.values() if s.had_health_detail)
    ignored = sorted(reviewed.ignore) if reviewed else []
    out = [f"Preprocessing report · run date {run_date:%a %b %d, %Y}", ""]
    out += ["Inputs (read only, never changed):"] + [f"  {k}: {v}" for k, v in inputs.items()] + [""]
    out += [f"Waitlist: {len(lines)} lines -> {len(people)} people: {len(active)} active, {len(stale)} stale, "
            f"{len(review)} held for review" + (f" ({len(ignored)} lines ignored by reviewed.csv)." if ignored else "."),
            f"Health details: found on {health} lines; none are kept or shown (pregnancy only routes to "
            f"prenatal-trained therapists).", ""]
    out.append("HELD FOR REVIEW (not offered until a person checks the notebook):")
    if review:
        out += ["  To release someone:",
                "  - a note that can't be read: add a new line for them that starts with 'start over', then all their",
                "    details in the usual shorthand (their place in the queue is kept)",
                "  - 'check identity': add a row to reviewed.csv: line, decision (same person / different people /",
                "    ignore), other_line"]
    out += [f"  lines {p.line_ids} {p.name}: " + "; ".join(p.reasons) for p in review] or ["  none"]
    out += ["", "STALE (out of date, never offered):"]
    out += [f"  lines {p.line_ids} {p.name}: " + "; ".join(p.reasons) for p in stale] or ["  none"]
    out += ["", "SAME PERSON, SEVERAL LINES (newest line wins where they differ):"]
    out += [f"  {p.name}: lines {p.line_ids} -> using line {p.active_line}"
            + (f" (started over at line {p.lines[start_index(p)].line})" if start_index(p) else "")
            for p in merged] or ["  none"]
    out += ["", "DESK DECISIONS (reviewed.csv):"]
    if "reviewed" not in inputs:
        out.append("  not used on this run")
    else:
        out += [f"  {d}" for d in reviewed.used] or ["  none"]
    out += ["", "WARNINGS:"] + ([f"  {w}" for w in warnings] or ["  none"])
    Path(path).write_text("\n".join(out) + "\n", encoding="utf-8")
