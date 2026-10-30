"""Kettle & Stone platform, step 1: sync uploaded files into the database, then match from it.

    first time (fills the database with the sample, already processed):
    python sync.py --waitlist waitlist-2026-10-21.csv --appointments appointments-2026-09-21-to-2026-10-17.csv \
                   --openings late-openings-2026-09-21-to-2026-10-17.csv --run-date 2026-10-21

    later (any of the three files; the database keeps everything synced before):
    python sync.py --waitlist NEW-waitlist.csv --appointments NEW-appointments.csv --openings NEW-openings.csv \
                   --run-date 2026-10-30

Writes the same files as run.py (out/matches.txt, matches.csv, preprocess-report.txt, line-verdicts.csv, core/)
plus out/sync-log.txt. The database is data/kettle.db unless --db says otherwise. Nothing is sent anywhere,
the input files are never changed, and the waitlist note text is never stored.
"""
import argparse
import sys
from datetime import date

from kettle.adapters.csv_in import InputError
from kettle.adapters.upload import line_ranges, sync
from kettle.core.match import ORDERS
from run import parse_declined

DEFAULT_DB = "data/kettle.db"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Sync files into the platform database and match the openings.")
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--waitlist", help="the whole book; only new lines are added")
    ap.add_argument("--appointments", help="added to the booking history")
    ap.add_argument("--openings", help="these openings are matched; without it, every opening in the database is")
    ap.add_argument("--run-date", default=date.today().isoformat(),
                    help="count from this day (YYYY-MM-DD). Sample = 2026-10-21; demo = the demo day")
    ap.add_argument("--order", choices=ORDERS, default=None, help="default from config: first-asked")
    ap.add_argument("--declined", action="append", metavar="OPENING:LINES",
                    help="skip people who said no, e.g. --declined O01:39,42")
    ap.add_argument("--reviewed", metavar="FILE",
                    help="the desk's decisions on held lines, e.g. reviewed.csv (clinic use; not on demo files)")
    ap.add_argument("--out", default="out")
    args = ap.parse_args(argv)

    try:
        result = sync(args.db, date.fromisoformat(args.run_date), args.waitlist, args.appointments, args.openings,
                      args.out, args.order, parse_declined(args.declined), reviewed=args.reviewed)
    except (InputError, ValueError) as e:
        print(f"Stopped: {e}", file=sys.stderr)
        return 1

    s, people = result["summary"], result["people"]
    if "waitlist" in s:
        w = s["waitlist"]
        print(f"Waitlist: {w['lines']} lines, new: {line_ranges(w['new'])}, changed: {line_ranges(w['changed'])}")
    if "appointments" in s:
        a = s["appointments"]
        print(f"Bookings: {a['rows']} rows (visits {a['visits'][0]} to {a['visits'][1]}), new: {a['new']}, "
              f"status changes: {a['status_changes']}")
    if "openings" in s:
        print(f"Openings: {s['openings']['rows']}, new: {s['openings']['new']}")
    print(f"People: {len(people)} ({sum(p.status == 'active' for p in people)} active, "
          f"{sum(p.status == 'stale' for p in people)} stale, {sum(p.status == 'review' for p in people)} held)")
    named = sum(1 for r in result["results"] if r.picks)
    print(f"{len(result['results'])} openings matched: {named} with names, {len(result['results']) - named} with nobody")
    for g in result["gaps"]:
        print(f"Warning: no booking data for visits {g[0]} to {g[1]}: see {args.out}/sync-log.txt")
    print(f"Read {args.out}/matches.txt and {args.out}/sync-log.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
