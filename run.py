"""Kettle & Stone waitlist matcher. One command, end to end.

    python run.py --waitlist W.csv --appointments A.csv --openings O.csv --run-date 2026-10-30
    python run.py --check-settings      (after editing config/clinic.json)
    add --reviewed reviewed.csv at the clinic to apply the desk's decisions on held lines (never on demo files)

Writes out/matches.txt (read this), out/matches.csv, out/preprocess-report.txt, out/line-verdicts.csv
and the core data in out/core/. Nothing is sent anywhere and the input files are never changed.
"""
import argparse
import sys
from datetime import date

from kettle.adapters.csv_in import InputError
from kettle.config import DEFAULT_CONFIG, load_config
from kettle.core.match import ORDERS
from kettle.pipeline import run

SAMPLE = {
    "waitlist": "waitlist-2026-10-21.csv",
    "appointments": "appointments-2026-09-21-to-2026-10-17.csv",
    "openings": "late-openings-2026-09-21-to-2026-10-17.csv",
}


def parse_declined(values):
    """--declined O01:39,42 -> {"O01": {39, 42}} (waitlist lines who already said no to that opening)."""
    out = {}
    for v in values or []:
        opening, _, lines = v.partition(":")
        out.setdefault(opening.strip(), set()).update(int(x) for x in lines.split(",") if x.strip())
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Who to offer each late opening to (up to 3 names, or nobody).")
    ap.add_argument("--waitlist", default=SAMPLE["waitlist"])
    ap.add_argument("--appointments", default=SAMPLE["appointments"])
    ap.add_argument("--openings", default=SAMPLE["openings"])
    ap.add_argument("--run-date", default=date.today().isoformat(),
                    help="count from this day (YYYY-MM-DD). Sample = 2026-10-21; demo = the demo day")
    ap.add_argument("--order", choices=ORDERS, default=None, help="default from config: first-asked")
    ap.add_argument("--declined", action="append", metavar="OPENING:LINES",
                    help="skip people who said no, e.g. --declined O01:39,42 (re-run for the next names)")
    ap.add_argument("--reviewed", metavar="FILE",
                    help="the desk's decisions on held lines, e.g. reviewed.csv (clinic use; not on demo files)")
    ap.add_argument("--out", default="out")
    ap.add_argument("--check-settings", action="store_true",
                    help="only check config/clinic.json and say what to fix; matches nothing")
    args = ap.parse_args(argv)

    if args.check_settings:
        try:
            config = load_config()
        except ValueError as e:
            print(f"Stopped: {e}", file=sys.stderr)
            return 1
        print(f"Settings OK: {DEFAULT_CONFIG} ({len(config.therapists)} therapists, {len(config.nicknames)} nicknames)")
        return 0

    try:
        run_date = date.fromisoformat(args.run_date)
        result = run(args.waitlist, args.appointments, args.openings, run_date, args.out,
                     args.order, parse_declined(args.declined), reviewed=args.reviewed)
    except (InputError, ValueError) as e:
        print(f"Stopped: {e}", file=sys.stderr)
        return 1

    people = result["people"]
    named = sum(1 for r in result["results"] if r.picks)
    print(f"Run date {run_date}: {len(result['lines'])} waitlist lines -> {len(people)} people "
          f"({sum(p.status == 'active' for p in people)} active, {sum(p.status == 'stale' for p in people)} stale, "
          f"{sum(p.status == 'review' for p in people)} held for review)")
    print(f"{len(result['results'])} openings: {named} with names, {len(result['results']) - named} with nobody")
    if result["warnings"]:
        print(f"{len(result['warnings'])} warning(s), see {args.out}/preprocess-report.txt")
    print(f"Read {args.out}/matches.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
