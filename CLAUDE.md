# Kettle & Stone: future platform build

This folder is the **future platform** version of the Kettle & Stone waitlist matcher (Sprint 2).
It was copied on 2026-10-30 from `C:\Users\joonp\Documents\Claude\sprint-2-Kettle-&-Stone`, which
holds the working command-line matcher used for the Friday demo. **Never edit that folder from here.**
It is the frozen reference. If a matching fix is needed there too, say so and let the user port it.

## What we are building

The design in `technical-build-plan.md` §11 (Future platform), plus §7.2 (rebooking loop), §11.5–11.7
(call outcome → instant match, one cancellation inbox, feedback loop) and §14 (build order):

1. **Booking data in (simulated).** The clinic's booking system is **Kneadly** (the user sometimes
   says "Calendly"; same thing). We do **not** connect to it. Assume its data arrives with the right
   columns already extracted, and feed it through an adapter that stands in for the real API.
2. **Matching.** Reuse the existing matcher in `kettle/` (core in `kettle/core/`, CSV adapter in
   `kettle/adapters/csv_in.py`). Add new adapters instead of changing the core rules.
3. **Waitlist board.** A new interface where the waitlist is kept up to date online
   (editable cards, see §11.2), instead of the CSV export.
4. **Output.** Similar to today's `out/matches.txt`, plus a plan for how it plugs into real
   rebooking and the feedback loop.

## Rules that still apply

- `project-guidelines.md` is the rulebook: precision beats recall, hard bans, run date is a parameter.
- Never send real messages and never connect to Kneadly or any real booking system.
- No health details outside the places §16 of the plan allows.
- Unknowns are logged as open questions, not guessed.

## Sources of truth

`discovery-notes.md`, `follow-up-answers-oct-29.md`, `interview-tanya-boudreau-2026-10-22.md`,
`step1-discovery-facts.md`, `step2-csv-facts.md`, `step3-combined-facts.md`, `handover-plan.md`.

## Running the existing matcher

```
python run.py --run-date 2026-10-21
python -m pytest
```
