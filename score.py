"""Checks out/matches.csv against Tanya's answer key (sample data only; Friday's key isn't handed out).

    python score.py --key answer-key-tanya.csv --out out

Match = every name shown is on Tanya's list for that opening, or nobody shown when her answer is nobody.
Hard gate = no name shown that is not on her list (that would be someone unsuitable or out of date).
"""
import argparse
import csv
import re
import sys
from collections import defaultdict


def read_key(path):
    openings, lines = {}, {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if row["type"] == "opening":
                answer = row["answer"].strip().lower()
                openings[row["id"]] = set() if answer == "none" else {int(n) for n in re.findall(r"W(\d+)", row["answer"])}
            else:
                lines[row["id"]] = row["answer"].strip()
    return openings, lines


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", default="answer-key-tanya.csv")
    ap.add_argument("--out", default="out")
    args = ap.parse_args(argv)

    key_openings, key_lines = read_key(args.key)
    ours = defaultdict(set)
    with open(f"{args.out}/matches.csv", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            ours[row["opening_id"]]
            if row["line"]:
                ours[row["opening_id"]].add(int(row["line"]))

    matched, bad_names, misses = 0, [], []
    for oid, shown in sorted(ours.items()):
        truth = key_openings.get(oid)
        if truth is None:
            continue
        wrong = shown - truth
        bad_names += [(oid, n) for n in wrong]
        ok = (not shown and not truth) or (shown and not wrong)
        matched += ok
        if not ok:
            misses.append(f"  {oid}: shown {sorted(shown) or 'nobody'}, Tanya {sorted(truth) or 'nobody'}")
    total = len([o for o in ours if o in key_openings])
    print(f"Openings matched: {matched}/{total}")
    print(f"Names shown that are not on Tanya's list (hard gate, must be 0): {len(bad_names)}")
    for m in misses:
        print(m)

    with open(f"{args.out}/line-verdicts.csv", encoding="utf-8", newline="") as f:
        verdicts = {r["line"]: r["verdict"] for r in csv.DictReader(f)}
    differ = [f"  {k}: ours {verdicts.get(k)}, Tanya {v}" for k, v in sorted(key_lines.items()) if verdicts.get(k) != v]
    print(f"Waitlist line verdicts matching Tanya: {len(key_lines) - len(differ)}/{len(key_lines)}")
    for d in differ:
        print(d)
    return 0 if matched == total and not bad_names else 1


if __name__ == "__main__":
    sys.exit(main())
