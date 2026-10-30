**Sprint 2: Kettle & Stone waitlist matcher, hand-in**

**Done check 1: up to 3 people who fit, or nobody ✅**
For every late opening, the matcher shows up to 3 waitlist people who fit, each with phone, notebook line and a one-line reason, or "nobody". No-shows always get nobody. On the sample (run date Oct 21), the full set of people who fit equals Tanya's list on all 44 openings, not just the 3 shown.

**Done check 2: Friday live run (10 new openings, ≥ 8 match, nobody unsuitable or out of date)**
- Sample result: **44/44 openings match, 0 names outside Tanya's list, 60/60 waitlist lines get the same verdict as Tanya** (active / stale / repeat line).
- Dry run with run date Oct 30: still 44/44 and 0 wrong names. Lines added Aug 24–29 now count as stale under the 60-day rule, as expected.
- Unreadable notes and name/phone mix-ups are held back, never guessed. A health word no longer hides a scheduling word written next to it ("sore neck, Rachel only" keeps Rachel).
- A mistake in the settings file (e.g. one short form for two therapists) stops the run instead of quietly misreading notes.
- Live result: **__ / 10 matched, __ unsuitable or out-of-date names shown** _(fill in after the demo)_

**Done check 3: written plan ✅**
[handover-plan.md](handover-plan.md):
- **Who looks after it:** Julie, ~1 hr/month; the desk uses it after each cancellation.
- **Cost:** $0/month. No internet, AI service or subscription.
- **When it's wrong:** a table of each kind of mistake, how it's noticed, what the desk does and how it gets fixed. Mistakes go in `mistakes-log.csv`, and the notebook is always the fallback. Someone held for review is released only by a desk decision: a `start over` line, or a row in `reviewed.csv`.

**Done check 4: no real messages, no real booking system ✅**
Nothing is sent and nothing connects to Kneadly. The input files are only read; a test checks they're unchanged. No health detail appears in any output; a test checks every output file.

**Steps to run**
```bash
python run.py --waitlist NEW-waitlist.csv --appointments NEW-appointments.csv --openings NEW-openings.csv --run-date 2026-10-30
```
Read `out/matches.txt` (names per opening) and `out/preprocess-report.txt` (who is stale or held for review, plus warnings).

Sample check:
```bash
python run.py --run-date 2026-10-21
python score.py
python -m pytest
```
Expected: `44/44`, `0` wrong names, `60/60` line verdicts, `148 passed`. Requires Python 3 with pytest; nothing else.

**Files**
- `run.py`: one command, end to end
- `score.py`: compares output with Tanya's answer key (sample only)
- `kettle/`: matcher code
  - `adapters/csv_in.py`: reads the CSVs
  - `core/parse_notes.py`: notebook shorthand
  - `core/people.py`: repeat lines and stale people
  - `core/match.py`: the rules
  - `output/report.py`: the output files
- `config/clinic.json`: therapists, defaults, time words, nicknames (no rules hard-coded)
- `tests/`: 148 tests: parsing, merging, staleness, each matching rule, all 44 sample openings, privacy, shorthand not in the sample, settings check, releasing held people
- `out/`: results of the last run
- `handover-plan.md`: done check 3
- `technical-build-plan.md`: design, decisions, and the future platform (Kneadly feed, cancellation inbox, call outcome → instant match)
- `project-guidelines.md`: the rules this was built against
- `mistakes-log.csv`: blank log for the desk
- `reviewed.csv`: blank file for the desk's decisions on held lines (clinic use with `--reviewed`; not used on the demo files)

**Decisions I made where the clients hadn't decided**
- **Notice:** counted from the cancellation time.
- **Stale:** more than 60 days since the person's newest line.
- **Length:** a shorter request fits a longer opening (60 in a 90), never the reverse.
- **Post-op clients:** no automatic Josée filter; the matcher follows what's written.
- **Offer order:** whoever asked first, with other orders switchable. Marc and Tanya still need to settle this.

All of these match Tanya's answer key; details in `technical-build-plan.md` §3.
