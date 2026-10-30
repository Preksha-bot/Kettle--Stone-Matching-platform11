# Platform plan: Kettle & Stone waitlist matcher

This plan turns the command-line matcher into a small platform:
- **How it runs now:** the three CSV files are uploaded. The appointments and late-openings files stand in for the Kneadly API and build up a booking history. The waitlist file is migrated into the database, which is then kept up to date on screen. A database and a set of screens replace the text files.
- **What it assumes for later:** a live Kneadly connection, updates from calls and texts, a hold in Kneadly on every slot being offered, and client bookings written into Kneadly where the case needs it.

It pulls together [technical-build-plan.md](technical-build-plan.md) (mainly §7.2, §8, §11, §14, §16) and the discovery sources listed in §17. The rules in [project-guidelines.md](project-guidelines.md) still apply:
- Precision beats recall.
- No health details on any screen a client could see.
- Nothing is sent to anyone.
- Unknowns are logged, not guessed.

> **Booking system name:** the clinic's booking system is **Kneadly** (also called "Calendly" in conversation; it's the same system). This project never connects to it. Every Kneadly connection below is an **assumption**, made so the platform can be designed now. It's built only against a stand-in.

**Status markers**

| Marker | Meaning |
|---|---|
| ✅ **Built** | Exists in this folder today and is tested: the command-line matcher (44/44 openings on the sample, 0 wrong names), and since Oct 30 the platform database and file sync (build step 1), the first screens (step 2), the review queue (step 3), the settings screen (step 4), the offer loop (step 5), the cancellation inbox (step 6), the morning call list (step 7) therapist tags with the health routing rules (step 8), the waitlist board (step 9) and the feedback loop (step 10). 292 tests pass. |
| 🔨 **Phase 1: to build** | Designed here. Needs no outside connection. Runs on CSV uploads on the desk computer. |
| 🧪 **Phase 2: simulated** | Built and tested against a **stand-in** for Kneadly, calls and texts. No real connection. |
| 🔮 **Phase 3: assumption** | Depends on a Kneadly API, or a phone or text service, that may not exist. Not built until Julie and Marc answer (§16). |
| ❓ **Open question** | Nobody knows yet. |

---

## 1. The platform in one picture

```
 WHERE DATA COMES FROM                 PLATFORM (desk computer)                               KNEADLY
 ───────────────────────               ───────────────────────────────────────────            ──────────
 🔨 Waitlist CSV: migrated ──┐         ┌───────────────────────┐
    once, then new lines      │         │ ✅ CORE (unchanged):   │      ✅ CORE MATCHER
 🔨 Appointments + openings ──├─adapters┤ read notes, group     ├────► filters → order → ≤3
    CSV (stand-in for API)    │         │ people, mark stale    │      (same code as today)
 🔨 Waitlist board (cards) ───┤         └───────────┬───────────┘             │
 🔨 Desk taps: call list,     │                     ▼                         ▼
    inbox, offers, review ────┤         🔨 DATABASE: people · bookings (history kept) · booking events
 🔮 Kneadly API ──────────────┘            · openings · offers · holds · review · rules · settings · logs
    (🧪 stand-in in Phase 2)                                 │
                                                             ▼
                                        🔨 SCREENS: opening queue + names · offers · review queue
                                           · waitlist board · today & tomorrow · rules · settings
                                                             │
                                        before offer #1      ▼
                                        ├──► HOLD the slot: block or placeholder booking (§10.2) ──► Kneadly
                                        on a yes
                                        └──► client's booking, case by case (§10.3) ───────────────► Kneadly
```

**The main design rule stays the same ✅:** the core data and the core matcher are the same in every phase. Only the **adapters** change: CSV upload now, board and desk taps next, Kneadly API last. The matcher never knows where its data came from, so everything tested for Friday carries over.

**What the platform still never does:** phone, text or email anyone. Every offer is made by a person at the desk.

---

## 2. What is built, and what isn't

| Piece | Status | Where | Notes |
|---|---|---|---|
| Read the three CSV files and check their columns ("Stopped: missing column …") | ✅ | `kettle/adapters/csv_in.py` | Files are only read, never changed |
| Cross-check the openings file against the booking export | ✅ | `csv_in.check_openings_against_export` | Warns on a mismatch |
| Normalise phones, dates and names; nickname table | ✅ | `kettle/core/normalise.py` | |
| Read the shorthand notes; drop health words; keep only the routing tags a rule needs (`needs`) | ✅ | `kettle/core/parse_notes.py` | The built-in health word list (`HEALTH_RE`) is code; the routing words and extra private words are settings (✅ Oct 30) |
| Group lines into people (phone + name), merge, mark stale | ✅ | `kettle/core/people.py` | |
| Release held people: `start over` lines, `reviewed.csv` decisions | ✅ | `parse_notes.py`, `people.build_reviewed` | |
| Matcher: 9 filters, order switch, max 3, `--declined` | ✅ | `kettle/core/match.py` | |
| Settings file and settings check | ✅ | `kettle/config.py`, `config/clinic.json` | Therapist tags (`female` and `prenatal_trained` as the two built-in ones, plus `tags`), routing rules and extra private words checked too (✅ Oct 30) |
| Output files: `matches.txt`, `matches.csv`, `preprocess-report.txt`, `line-verdicts.csv`, `core/` | ✅ | `kettle/output/report.py` | |
| One function that runs it all and returns everything a database needs | ✅ | `kettle/pipeline.py` → `run()` | Returns people, results, verdicts, warnings |
| **Database** (SQLite), seeded with the sample, already processed | ✅ Oct 30 | `kettle/store.py`, `data/kettle.db` | No note text and no unread words are stored (§4.4) |
| **Sync from files:** booking history kept across uploads, openings kept once per appointment, sync log, gap warning; matching from the database | ✅ Oct 30 | `kettle/adapters/upload.py`, `python sync.py` | Same output files as `run.py`, plus `out/sync-log.txt` |
| **Waitlist migration** (first import, then new lines only; a changed old line holds its person) | ✅ Oct 30 | `store.save_lines` | Uses the ✅ parser and grouping |
| **Web back end** on the desk computer (`python serve.py`, http://localhost:8000, this computer only) | ✅ Oct 30 | `webapp/app.py`, `serve.py` | Python's own web server, threaded; nothing to install |
| **Upload screen**: three files and a run date → **check** (the real sync on a temporary copy of the database) → **Save and match** or **Cancel** | ✅ Oct 30 | `webapp/app.py` | Files stay in memory until saved or cancelled; a bad file saves nothing |
| **Opening queue**: soonest first, up to 3 names with phone, line, reason and flags, "not offered" with reasons, gap warning, waitlist counts, downloads of the output files | ✅ Oct 30 | `webapp/pages.py` | Same content as `matches.txt`, plus the offer steps (step 5) |
| **Sync log screen**: every upload, what changed, warnings | ✅ Oct 30 | `webapp/pages.py` | File names only |
| **Review queue**: every held person with the decisions that fit; fill-in card; undo; count in the menu; drift alarm | ✅ Oct 30 | `webapp/pages.py`, `webapp/cards.py`, `store.add_decision` | Uses the ✅ release logic; matching rules unchanged |
| **Settings screen**: order, names per opening, defaults, time words, therapists, nicknames; check with before/after names; versions; compare orders; the owner's pause switch | ✅ Oct 30 | `webapp/settings.py`, `webapp/pages.py` | The ✅ settings check guards every save |
| **Health routing rules**: tags in the core; the Rules screen (rules, therapists with each tag, words, card label, a new rule, extra private words); check, before/after, Marc's approval, versions; a chip per rule on the fill-in card | ✅ Oct 30 | `kettle/config.py`, `parse_notes.py`, `match.py`; `/rules` | The one change to the core: sample results unchanged byte for byte |
| **Waitlist board** (`/board`): a card per person with chips; filters and search; Edit card; Still interested; Take off (a reason from a list); + Add (phone checked first); history; retire the book (board only) | ✅ Oct 30 | `webapp/app.py`, `pages.py`, `cards.py` | Built before Tanya's timing test, so the test can use it (§6) |
| **Cancellation inbox**: the day's bookings from the uploads; enter a cancellation (how it came in, when; no reason); under 24 h → an opening with names at once; 24 h or more → only recorded; by Kneadly number if it isn't uploaded; one row per appointment; notice from now; match again now | ✅ Oct 30 | `/inbox`, `store.record_cancellation` | Fed by the appointments upload (the API stand-in) |
| **Morning call list**: today's (still to come) and tomorrow's unconfirmed bookings; Confirmed / Voicemail (dots, try again) / Cancelled → names under the row; undo | ✅ Oct 30 | `/calls`, `store.call_list` | Phone numbers stay in Kneadly (not in the export) |
| **Offer loop**: who's at the desk; hold step (manual block, ticked); one live offer per opening (kept by the database); yes / no / no answer; next name moves up; booking card with the three cases; filled another way; release; reopen; undo | ✅ Oct 30 | `webapp/app.py` (`/opening`), `store.start_offer` … | Kneadly has no hold, so the desk blocks the time by hand |
| **Daily check** and **rebookings.csv** | ✅ Oct 30 | `/check`, `/files/rebookings.csv` | |
| **Feedback loop**: why someone said no (from a list, never free text); "No, keep me on"; 3 no's in a row flagged on the card; a weekly offer limit per person with a "Resting this week" box; the report (what happened to the openings, by channel, time to fill, answers, reasons, possible wrong offers, the export's own refills); `outcomes.csv` | ✅ Oct 30 | `kettle/feedback.py`, `/report`, `/files/outcomes.csv` | The limit is a setting, **0 = no limit**, until Marc picks a number |
| Kneadly stand-in adapter and event simulator | 🧪 | — | No network |
| Holds and bookings in a fake Kneadly | 🧪 | — | No network |
| Real Kneadly reads (live, plus checks every 1–2 min) | 🔮 | — | Depends on Julie's answers |
| Holds and bookings placed by the platform in Kneadly | 🔮 | — | Depends on the API, and on Marc saying yes |
| Text replies and voicemail as automatic inputs | 🔮 | — | Outside services that hear health details |

---

## 3. Phases and what must be true before each

| Phase | What runs | What it needs | Cost |
|---|---|---|---|
| **0. Today ✅** | `python run.py …` on the desk computer. Text files out | Nothing | $0 |
| **1. Platform on CSV uploads 🔨** | A local web page on the desk computer. The waitlist is migrated into the database; appointments and openings uploads stand in for the API and add to the history; screens and desk taps. The desk holds each slot with a manual block before offering, and books refills in Kneadly by hand | Python + one small web library + SQLite on the desk computer. Tanya's timing test before the board | $0 |
| **2. Simulated Kneadly 🧪** | The same platform, fed by a stand-in that serves data shaped like an API, plus fake events (reminder sent, confirmed, cancelled, no-show). Holds and bookings go to a fake Kneadly | Nothing outside | $0 |
| **3. Real Kneadly 🔮** | Live reads at each decision point, plus checks every 1–2 min in opening hours (or Kneadly's own notifications). Then, **if the API allows it**, holds placed by the platform, and client bookings written case by case, behind an owner-only switch | Julie confirms the API exists and what it can do. Marc signs a one-page note. Price checked. Stand-in tests pass on the first real data | ~$45/month **if** the higher plan is needed (unchecked) |

**Gates before Phase 3 (all needed):**
1. Julie confirms the API and its fields (§16).
2. Marc signs the one-pager: what is read, where it goes, how long it's kept, who can see it.
3. The real cost stays under $50 a month, all items together.
4. For holds and bookings placed by the platform, also: Marc's explicit yes, and the §10.5 conditions are met.

---

## 4. Data in

### 4.1 Three uploads, two different jobs 🔨

| Upload | Stands in for | How it's taken in |
|---|---|---|
| **Appointments** | What the Kneadly API would return for a period: bookings and their states | **Sync:** added to the booking history by `appointment_id`. Nothing already there is thrown away (§4.3) |
| **Late openings** | What the API and the cancellation inbox would produce: late cancellations and no-shows | **Sync:** added by `appointment_id`, so one cancellation never becomes two openings |
| **Waitlist** | The green book itself | **Migration:** moved into the database once; each later upload only adds new lines, until the board replaces the book (§4.4, §6.3) |

**No weekly or daily export is part of this plan.** The appointments and openings files are only a stand-in for the API:
- They show the data structure.
- They let the built preprocessing and matching run unchanged.
- A file can cover any period: four weeks like the sample, or only the last two days.

```
UPLOAD (example counts)                                         Run date: [2026-10-30 ▾] (default: today)
 Waitlist ............ [waitlist-2026-10-30.csv     ]  ✓ 64 lines · lines 61–64 are new · 0 old lines changed
 Appointments ........ [appointments-NEW.csv        ]  ✓ 86 rows · visits Oct 28–29 · history now Sep 21–Oct 29
                                                          ⚠ no booking data for Oct 18–27
 Late openings ....... [late-openings-NEW.csv       ]  ✓ 10 openings · none seen before
                                                        [Check files]   [Save and match]
```

### 4.2 What happens on each upload (on ✅ code)

| # | Step | Code (✅ built) |
|---|---|---|
| 1 | Check that each file has the expected columns; stop with the same plain message as today | `csv_in._rows`, `read_waitlist`, `read_appointments`, `read_openings` |
| 2 | Normalise phones, dates (year from the run date) and names | `core/normalise.py` |
| 3 | Read each note **in memory**. Health words are dropped and only the prenatal flag survives. The note text is then thrown away | `NoteParser.parse` |
| 4 | Group lines into people, merge them, mark stale and held, using **every booking in the history**, not only the new file | `build_people` |
| 5 | Match every opening | `match_all` |
| 6 | Cross-check openings against the booking history, and check therapists against the settings | `pipeline.run` |
| 7 | **New:** before saving, show what will change: new lines, new bookings, people who turn stale and why, new openings, any gap. On **Save**: add it all to the database, write the **sync log**, and produce the same four files | new, around the same functions |

**"Exactly as the current script":** the back end calls the same functions in the same order as `pipeline.run`. A test proves it: loading the sample files into an empty database with run date Oct 21 must give a `matches.csv` **identical byte for byte** to `python run.py --run-date 2026-10-21`.

From the second upload on, steps 4–6 run on everything in the database. Results can then differ from running the script on the new files alone, but only where the history knows more (e.g. someone who booked weeks ago).

**Columns needed** (from `csv_in.py`; the matcher reads nothing else):

| File | Needed for matching ✅ | Read by the platform only (never by the matcher) |
|---|---|---|
| Waitlist | `line, added, name, phone, notes` | — |
| Appointments | `appointment_id, date, start, end, length_min, therapist, client_id, client_name, booked_at, status, cancelled_at` | `booked_via` (slot taken online), `confirmation` and `cancel_via` (booking states, §9), `rebooked_into` (refill numbers) |
| Late openings | `opening_id, appointment_id, date, start, length_min, therapist, kind, cancelled_at` (`hours_notice` derived if missing) | `heard_via`. **Never** `refilled` / `refilled_how`: what actually happened must not choose the names for that same opening (leakage) |

### 4.3 Appointments and openings: the stand-in for the API 🔨

**The booking history is kept.** "Booked since" can only see bookings that are in the data. Tested Oct 30 on copies of the sample, run date Oct 30:
- **Full 4-week export:** 0 wrong names on the 44 openings.
- **Only the last 2 days of that export** (visits on Oct 16–17): wrong names on 35 of 44 openings, including 3 of the 4 openings inside those 2 days.
- **Why:** Bob Gaudet, Steph Poirier, Claudette Richard and Jen LeBlanc booked after their newest waitlist line. Their bookings fall outside the 2 days, so they look like they're still waiting.

So each appointments upload is **added** to the database, never swapped in. The database starts with the current sample CSVs, already processed, and every later file is synced into it. This is also what stops someone who already got a slot from being offered again.

**Two different needs:**

| Need | Data | Phase 1 | Phase 3 |
|---|---|---|---|
| Call list, new openings, slot checks | A **time window**: recent days, today and tomorrow | The latest upload | API, live |
| "Booked since", regulars | Each waitlist person's **booking history** | Everything synced so far | API: a client's bookings made after a given date ❓ |

**Gaps are named.** If a new file doesn't start where the history ends, the sync log and every screen say so: "⚠ no booking data for Oct 18–27: someone who booked in those days may still be listed". The desk checks Kneadly before calling. Results aren't blocked, because holding everyone whose newest line is older than the gap would empty most lists.

**Changes become events.** A booking seen again with a new status (e.g. not yet happened → `Late cancel`) is updated, and the change is saved as a booking event (§9).

**Notice:** openings from a file count notice from the cancellation time, as Tanya's answers do. Openings entered in the inbox count from now (✅ built, §7.1).

**Friday's demo, on the platform:**
- The database already holds the processed sample: 60 waitlist lines, 4 weeks of bookings, 44 openings.
- Friday's files are synced in: new waitlist lines are migrated, new bookings join the history, and the 10 openings are matched with the run date set to the demo day.
- The sync log lists what changed.
- Bookings made between Oct 17 and the first day of Friday's booking file stay unknown, and the gap warning says so.

❓ What `status` does a booking that hasn't happened yet show? The sample only has `Completed`, `Late cancel`, `Cancelled` and `No-show`.

### 4.4 Waitlist: a migration from the green book 🔨

The green book is **migrated** into the main database. After that, the database is the waitlist, and it's kept up to date on screen (§6).

| Stage | What happens |
|---|---|
| **First migration** | All lines are read (✅ parser, grouping, staleness). Each person gets a record: name, phone, first-asked and last-contact dates, what they can take (therapists, lengths, days, times, notice, dates, contact), status with reasons, and their line numbers. Held people go to the review queue |
| **Later uploads of the book** | The whole file is read again in memory. Tanya adds to the end ("same columns, same handwriting"), so only lines with new numbers are added, and they're merged into existing people with the same phone + name rules. Each old line has a **fingerprint** (a one-way hash, not the text). If an old line's text changed, it's flagged and that person is held |
| **Merging with the board** | Card edits are the newest entries for that person (§6.3). A newer book line still overrides them, field by field, until the cut-over |
| **Cut-over** | One last migration. Then waitlist uploads are switched off and the board is the only input |
| **Linking to Kneadly clients** | Phase 1: suggested by name (nickname rules), confirmed with one tap. Phase 3: by client ID or phone from the API |

**What is migrated, and what isn't:**
- **Migrated:** everything the matcher and the desk need.
- **Not migrated:** health details and the note text. Only the routing tag (e.g. prenatal-trained) is kept, as technical plan §16 requires. The book stays the only copy of the health details.
- **New routing words** apply to old lines on the next upload of the book. While the book is in use it's read in full every time, so nothing extra has to be kept.

Each migration writes a log: lines added, and people merged, changed, turned stale or held, with the reason.

### 4.5 Kneadly API: the assumed connection 🔮 (stand-in 🧪)

We assume Kneadly can hand over the **same columns the CSV adapter already reads**, already extracted. Below is what the platform needs from it, as capabilities. Real endpoint names are unknown.

| What the platform needs | Becomes | Used for | Known? |
|---|---|---|---|
| Appointments in a date range, and **what changed since** a given time | `bookings` rows (the 11 required columns) | Slot taken, call list, booking history | ❓ API unknown. The columns themselves exist in the export ✅ |
| **One slot, right now:** free or taken? | — | The checks before the hold, before each offer, and before "you're booked" (§10.1) | ❓ |
| A **client's bookings made after a given date** | `bookings` (history) | "Booked since", without needing a long export (§4.3) | ❓ |
| Status changes **with timestamps**: booked, reminder sent, confirmed ("reply C"), cancelled (time + channel), no-show, completed | `booking_events` | Bookings at risk, new openings (§9) | ❓ The export has the final `confirmation` value but **no times** for the reminder or the confirmation |
| Client: ID, name, **phone**, text consent | Link a card to a Kneadly client; contact preference | Matching people to clients by phone instead of by name | ❓ The export has **no phone column** today |
| `booked_via`, `rebooked_into` | Reporting fields | Taken online; refill numbers | ✅ in the export |
| A cancellation alert or webhook | A new inbox row within minutes | Faster openings | ❓ (Julie, unanswered) |
| Text replies to the reminder | A **suggested** inbox row | One more channel | ❓ |
| **Create a booking** for an existing client in a free slot, return its ID, and refuse a booking in a taken slot | Client's booking; placeholder hold (§10.2–10.3) | Closing the loop | 🔮 ❓ |
| **Change the client** on an existing booking | Placeholder → client's booking with no gap | Avoids a moment when the slot is free | 🔮 ❓ |
| **Block time** on a therapist's schedule, and remove the block | The hold (§10.2 A) | Stops the online page giving the slot away while it's offered | ❓ Julie: "I can block time by hand, but there's no hold" |
| Create or change a booking **without** Kneadly's automatic message | Placeholder; silent bookings | No message the clinic didn't write | ❓ |
| How often the API may be called | — | Checks every 1–2 min | ❓ |

**Adapters (Phase 2 and 3):**
- `kettle/adapters/kneadly_sim.py` 🧪 reads **fixture files shaped like API answers**. They're generated from the sample CSVs, plus made-up events: reminders, confirmations, cancellations at set times.
- `kettle/adapters/kneadly_api.py` 🔮 has the same interface for the real thing, read only.
- Both produce the **same core records** as `csv_in.py` (`Booking`, `Opening`).
- **Contract test:** the same data through the CSV adapter and the stand-in gives identical core data and identical matches.

**Openings from the feed:** a cancellation with `cancelled_at` less than 24 h before the start becomes an opening, with ID = appointment ID. This replaces the late-openings CSV.

**How fresh: live reads where it matters, fast checks in between.**
- **Live reads at four moments:**
  1. when an opening is created
  2. before the hold is placed
  3. before each offer
  4. just before the desk tells the client "you're booked"

  These are what stop a double booking. No sync speed can, because an online booking can land between any two checks.
- **Between those moments:** check for changes every 1–2 minutes during opening hours, from the desk computer, if Kneadly's limits allow. This keeps the screens current: new online cancellations, slots taken online.
- **Kneadly's own notifications (webhooks), if they exist:** instant, but they need a server Kneadly can reach. That means hosting ($5–12/month) and another one-pager, and with the ~$45 plan the total passes $50. So checks from the desk computer come first.
- **Overnight**, checks run only if the computer is on. That costs little: nobody can act before 8:00, and 29 of 36 late cancellations had come in by 9:15.

---

## 5. Database 🔨

**SQLite**: one file on the desk computer.
- Free; nothing to install beyond Python.
- Easy to back up (copy one file).
- No data leaves the computer.

A hosted database would need Marc's one-pager (§16 of the technical plan) and pushes cost toward his $50 line.

**Created from the first upload:** the waitlist migration plus the current sample CSVs, already processed (people, lines, bookings, openings, review items). Then **kept up to date by**:
- later uploads, which add to it (Phase 1)
- desk taps and board edits (Phase 1)
- the Kneadly feed (Phase 3)

| Table | One row per | Filled by (now → later) | Health data? |
|---|---|---|---|
| `imports` (sync log) | Upload | Upload screen | No. File names, period covered, what changed, gaps, warnings; **not the files** |
| `waitlist_lines` | Notebook line | Waitlist migration | **No note text.** The fields read from it, the routing tags, and a fingerprint (one-way hash) to spot a changed line |
| `people` | Waitlist person (one card) | Built from lines → board | Routing tags only (e.g. `prenatal-trained`) |
| `card_edits` | Change made on a card | Board | No (chips only, no free text) |
| `bookings` | Kneadly appointment, **kept as history** | Appointments upload → API | No |
| `booking_events` | State change of a booking (§9.1) | Upload differences + desk taps → feed | No. **Channel and time only, never the reason** ("woke up with a cold" is not stored) |
| `openings` | Late opening (ID = appointment ID); `source` = desk for the inbox's (D01, D02 …) | Openings upload + inbox (✅) → feed | No |
| `cancellations` (✅ built) | A cancellation entered in the inbox: slot, when, how it came in, late or not. **No reason** | Inbox | No |
| `match_runs`, `matches` | Matcher run; name shown with its reason | Back end | No |
| `offers` (✅ built) | One offer to one person: who offered, when, the answer, and why they said no (one of six listed reasons, ✅ step 10). A database rule allows one live offer per opening | Openings screen | No. The reason is picked from a list, never typed, so no health detail can get in. The desk name is shown on screen (so two people don't call), never in a file |
| `opening_desk` (✅ built; the plan's `holds`) | What the desk did with an opening: held (blocked in Kneadly by hand), filled, taken, released | Openings screen → 🔮 API holds | No |
| `desk_decisions` (✅ built) | The desk's decision on a held person, with who made it and whether it was undone; desk entries (lines 10001 up) live here too | Review screen (replaces `reviewed.csv`) | No. Held reasons come from each run's `people` records, in plain words, **never the note** (risk D2) |
| `rules`, `therapist_tags` | Routing rule; tag per therapist | Rules screen | The rule's name implies a condition (risk D3) |
| `settings_versions` (✅ built) | Version of `config/clinic.json` saved from the settings screen, with what changed | Settings screen | No |
| `rebookings` (✅ built) | Refill, its case (§10.3), length, and whether it's in Kneadly yet | The booking card | No |
| `mistakes` (✅ built as a reason on `offers`) | Wrong offer noted by the desk: the reason "our mistake: they'd said they can't", listed under "Possible wrong offers" on the report (replaces `mistakes-log.csv`) | Openings screen | No |
| `audit_log` | Any change: who, when, old → new | Everything | No |

**Who is the source of truth for what**

| Data | Phase 1 | Phase 3 |
|---|---|---|
| **The schedule** (who is booked when) | **Kneadly, always.** The platform never keeps its own calendar | Kneadly |
| Holds on slots being offered | Kneadly (manual block); the platform tracks them | Kneadly (block or placeholder), placed by the platform |
| Booking history | The database, built up from every upload | The database, plus the API for any client |
| The waitlist | The database, from the migration; the book adds new lines until the cut-over (§6.3), then the board only | The board |
| Cancellations | Kneadly + desk taps in the inbox | Kneadly feed + inbox |
| Offers and their outcomes | Platform | Platform |
| Rules and switches | Platform (versioned); it writes `config/clinic.json` so the command line keeps working | Platform |
| Review decisions | Platform | Platform |

**How long data is kept ❓ (Marc):** suggested 12 months for offers and booking events (for numbers and tests), and 90 days for people who were taken off. Backups go to a clinic-owned place only.

---

## 6. Waitlist board: keeping the list up to date online (✅ built Oct 30, `/board`)

From technical plan §11.2 (editable cards, decided Oct 30). The plan was to build it only after **Tanya's timing test**: 3 real calls each way (the book, a spreadsheet row, a paper mock-up of the board), about 15 minutes. Her rule is "less time than the book, not more". **Built first, on Oct 30, at the builder's request**, so the timing test can use the real board instead of paper. The test still decides whether the book is retired (§6.3): ❓ Tanya.

### 6.1 The card

```
WAITLIST                                            [+ Add]   [Show: active · held · stale]   [Search name/phone]
┌ Amanda Bourgeois  506-555-0125   asked Sep 11 · last contact Sep 30 · lines 26, 42 ───────────────┐
│ [Rachel] [Josée]  [60]  [any day]  [any time]  [2 h notice]  [call]                                │
│ [Still interested ✓]  [Take off ▾]  [history ▾]                                                    │
└────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

As built, every board action is a **desk entry** (the review queue's mechanism, §7.4): saved in `desk_decisions` with who, when and what changed in plain words, undoable, and the last run's openings are matched again at once. The matching rules don't change. Who's at the desk comes from the browser (as for offers), so there's no name to type.

| Action | What it does (✅ built) |
|---|---|
| **Edit card** | The card (§6.2) opens filled in from what the person can take now. Saving it saves the **whole card** (a "start over" entry): it replaces what their older lines say, they keep their place in the queue, and it counts as contact, like a new line in the book. The history records which parts changed ("therapists, notice"), never the values of a routing chip. An unchanged card saves nothing. *Plan change:* "tap a chip" became "edit the card", one save for the whole card |
| **+ Add** | Checks the **phone first**: a number already on the list shows that person's card instead. Then name, phone and the card. The new person is an entry of their own (line 10001 up), asked today |
| **Still interested ✓** | Resets "last contact", so the 60-day clock restarts (also for someone already out of date) |
| **Take off** | A reason from a short list (booked, moved, not interested, going to another clinic). Never free text |
| Filters and search | Active · held · out of date · all, with counts; search by name or by part of the phone |
| **History** | The book's lines (line number and date; the notes were never kept) and every change made on screen, with **Undo** |
| Link to Kneadly client | 🔮 Not built: Phase 3, by client ID or phone from the API |

**No free-text field.** A notes box would bring the shorthand and the health details straight back. Routing chips (e.g. `Prenatal-trained only`) appear only while a card is open for editing (risk D3); on the board a pregnant client's card shows "Amira or Kelsey" (tested: no health word anywhere on the board).

### 6.2 Card fields

Therapist (any · pick some · anyone but · female only) · routing chips from the rules (§7.2) · length 30/45/60/90 · days Mon–Sat · morning/afternoon/evening or "from __ to __" · notice 30 min/1/2/3/4 h/day before · available from/until · call or text (text only with consent on file in Kneadly) · automatic: date added, last contact, added by.

### 6.3 Merging the migrated book with the board (cut-over)

| Mode | When | Rule |
|---|---|---|
| **A. Notebook + board** (✅ the default) | Start of Phase 1 | New lines from the book keep being migrated (§4.4). A card edit is that person's newest entry. A book line uploaded **after** the edit is newer and overrides it, field by field (tested). 🔨 A same-day warning isn't built: a line written the same day but uploaded later wins |
| **B. Board only** (✅ the switch; off) | After the timing test, on a date set with Tanya, Bethany **and the therapists** | **Retire the book: board only** on the board, with the tick "Agreed with Tanya, Bethany and the therapists". Waitlist uploads are then refused (on screen and in `sync.py`); appointments and openings still come in. It can be switched back |

Card edits are stored against the **line numbers** that person had when the edit was made. If a later upload splits that person (a new phone number, say), the edit isn't guessed onto either half. Both are held for review.

---

## 7. Matching on the platform

### 7.1 Same matcher ✅, new triggers 🔨

`match(opening, people, bookings, run_at, config)` is unchanged. The back end runs it:
- after each upload
- when a new opening is entered
- after a card edit or a review decision
- after a settings or rule change
- after a decline
- (Phase 3) after each check of Kneadly that finds a change

Each run is saved, so you can always see who was shown and why.

**Notice on re-runs is counted from now.** Example: after three declines on a 14:00 opening at 11:20, notice is 2.7 h, not "time since the cancellation". This is the planned switch B1 ("count notice from when an offer can go out"). The **adapter** works out `hours_notice`, so the core doesn't change.

Openings that come from a file (the sample, Friday's demo) keep counting from the cancellation time, as Tanya's answers do. Live openings count from now: ✅ the inbox's (worked out again at every run, so the names change as the start gets closer; **Match again now** on the inbox); ✅ the call list's (a cancellation there goes through the inbox); 🔮 the API's.

### 7.2 Health routing rules: front end and back end (✅ built Oct 30; the one core change)

**Before Oct 30:** the clinic has one health rule: pregnancy → prenatal-trained therapists only (Amira, Kelsey). It was built from three hard-coded pieces:
1. The words: `PRENATAL_RE` in `kettle/core/parse_notes.py`.
2. A yes/no field per therapist: `prenatal_trained` in `config/clinic.json`.
3. A filter: `allowed_therapists` in `kettle/core/match.py`.

"Female only" works the same way. A new rule (e.g. "post-op only with therapists trained for it") needed a developer.

**Built (technical plan P2, §15 #2 and #8):**
- **Therapists have tags.** `female` and `prenatal_trained` stay as the two built-in ones (old settings files keep working); any other goes in a `tags` list.
- **People carry the tags they need** (`needs`), from the routing rules' words. The matcher only offers them therapists with every one of those tags. The old `prenatal` flag is still honoured, so lines saved in the database before this change stay safe.
- **The words live in the settings** (`routing` in `config/clinic.json`, with the pregnancy rule written out). A word ending in `*` matches the start of a word (`pregnan*`), otherwise the whole word (`tri`, not `trip`). A settings file without `routing` gets the same pregnancy rule; `"routing": {}` means none (Marc's option (b), technical plan §16).
- **Extra private words** (`health_words`): a piece using one is dropped like any health detail, instead of being held as unreadable.

**This is the one change to the core in this plan.** Checked Oct 30: `matches.csv`, `matches.txt`, `line-verdicts.csv`, `preprocess-report.txt` and `core/openings.csv` identical byte for byte before and after, for the Oct 21 and Oct 30 runs; 44/44, 0 wrong names, 60/60. The only addition: a `needs` field in `core/people.json` (Sarah Collette and Vanessa Caissie: `prenatal-trained`, the same two people as before).

As built (`/rules`, checked in the browser):
```
HEALTH ROUTING RULES
┌ Prenatal ─────────────────────────────────────────────────────────────────────────────────────┐
│ People whose notes use one of these words only see therapists tagged prenatal-trained, even  │
│ if they said "any". The reason is never kept, only the tag.                                  │
│ Therapists with the tag:   ☐ Marc ☐ Dave ☐ Josée ☑ Amira ☑ Kelsey ☐ Rachel                     │
│ Words in the book that set it:  pregnan*, prenatal*, expecting*, trimester*, tri              │
│ Label on the fill-in card:  Prenatal-trained therapists only          ☐ Remove this rule      │
└───────────────────────────────────────────────────────────────────────────────────────────────┘
 New rule: name · tag · label · words · therapists with the tag
 More private words: added so far … [shingles, vertigo]
 [Check changes]
```

**How a rule changes (✅ built; nobody edits a live rule directly):**
1. **Draft:** Julie (or Marc) edits the form; nothing is saved yet.
2. **Check:** the settings check runs (extended for tags and rules). It blocks:
   - a rule whose tag no therapist has
   - a word that is also a therapist short form, a shorthand word (who, when, how long, how soon) or another rule's word
   - an empty rule, a tag that isn't one word
3. **Before/after:** the last run's openings are matched again on a temporary copy with the draft. The check page lists each change and each opening whose names change, by name and line only, never with a condition; and warns if anyone on the list would need a tag no therapist has any more. New words apply to the book's lines on its next upload, and the page says so.
4. **Tests:** 🔨 not run from the screen. The 271 tests are tied to the sample's settings (risk F8), so the before/after above is the check for everyday changes; the tests stay for code changes.
5. **Approve:** saving a change to a rule, the private words or who has a rule's tag needs the tick "Marc has approved this change" (and a name). A tag no rule uses, like "female", is an ordinary setting. The change is saved as a settings version, which can be put back on the Settings screen.

**What the editor can and can't do:**
- **Can:** any rule of the form "people with X only see therapists tagged Y". It's always a **hard filter**, because precision beats recall.
- **Can't:** a new *kind* of rule, such as "not the same therapist as last time", or a soft "usually Josée" (B2: post-op is not a filter). Those still need a developer, 0–2 times a year.
- **Drop-word list** (health words removed while reading notes): Julie can **add** words on the Rules screen (✅), which only makes it safer. Removing a word needs a developer and the privacy test.
- **The fill-in card** (§7.4) has one chip per rule, with the rule's label, ticked from what could be read.
- **No condition is stored per person.** A person carries only the routing tag. The reason they need it is never recorded. §16.1 of the technical plan covers how to decide whether a new rule is worth making without keeping health details.

### 7.3 Switches: front end and back end (✅ settings screen built Oct 30)

The switches that exist today (technical plan §6.5) are on the **Settings** screen (`/settings`).

**How a change is saved (✅ built):**
1. **Check changes:** the form goes through the same settings check every run uses, plus the screen's own rules (never more than 3 names, at least one therapist, a new therapist needs a first and last name). Any problem is named and nothing is saved.
2. **Before/after:** the last run's openings are matched again on a temporary copy of the database with the new settings. The screen lists each setting that changes, each opening whose names would change ("now" and "with the new settings"), and the waitlist counts if those change.
3. **Save:** needs a name, kept for the record and never shown. The settings file is written in one step, and the openings are matched again.
4. **Versions:** every save is kept in the database, including the settings as they were before the first change on the screen. **Put this version back** goes through the same check.

`config/clinic.json` stays the file every run reads (`run.py`, `sync.py` and the screens). If it's edited outside the screen, the settings screen says so.

| Switch | Today ✅ | On the platform | Who changes it |
|---|---|---|---|
| **Order** of people who fit: `first-asked` · `shortest-notice` · `regulars-first` | `--order` or `"order"` in `clinic.json` | ✅ Setting. Each opening has **compare orders**: the 3 names each order puts first, side by side, with why (asked date, notice, regular or not), and everyone who fits (Tanya: "show me what each way would look like"). Every result shows which order was used | Marc + Tanya decide; Julie sets it |
| Max names (3) | `max_names` | ✅ Setting: 1, 2 or 3, never more | Locked at 3 |
| Defaults: length 60, notice 2 h, stale 60 days, regular = N visits | `defaults` | ✅ Settings | Julie |
| Time words: mornings before 12:00, afternoons from 12:00, evenings from 18:00, lunch 12–13 | `time_words` | ✅ Settings | Julie |
| Therapists: short forms, female, prenatal-trained, approval (`see_first` → "ask Josée first") | `therapists` | ✅ A table on the settings screen, with an "Other tags" column; add and remove therapists. Tags a rule uses need Marc's approval (§7.2) | Julie (approval: Marc) |
| Nicknames (Bob → Robert …) | `nicknames` | ✅ A text box, one per line: `bob = robert` | Julie |
| Declined | `--declined O12:39,42` | 🔨 The **offer log** (§10): a "No" tap excludes that person from that opening | Desk, by tapping |
| Run date | `--run-date` | ✅ The upload's run date (default today) | Julie |
| **New:** count notice from the cancellation or from now (B1) | — | Openings from a file count from the cancellation ✅; inbox and call list openings from now ✅ | — |
| **New:** Pause the platform | — | ✅ The owner's switch on the settings screen: stops uploads (the screen and `sync.py`) and review decisions; every screen says "paused, use the notebook". Settings can still be fixed while paused | Marc |
| **New:** platform holds and bookings on or off | — | 🔨 With step 13 | Marc |

The order changes **which 3 come first, never who fits**. That stays tested: the full set of people who fit is identical in every order.

**Therapists added or removed (✅ built):** a note that said "any" is saved as "any", so it follows the therapist list: a new therapist is included, and a removed one isn't. A line that named a removed therapist ("Dave only") holds that person for review, as `run.py` would when re-reading the note.

### 7.4 Review queue: flagged cases (✅ built Oct 30)

The three kinds of flags in technical plan §7.3 become one **Needs review** screen (`/review`). Decisions are saved in the `desk_decisions` table, which replaces hand-editing `reviewed.csv` (the file still works with `--reviewed`), and the last run's openings are matched again straight away.

Example rows (made up, not from the sample; no sample person is held on Oct 21):
```
NEEDS REVIEW (4)                                                     never offered until someone checks the book
 Marcel B.   line 18      regular who booked since              Your name [____]  [Still wants an extra visit] [Take off]
 Amanda B.   lines 26, 42 shares phone with line 62             Line 62 and this person: [Same person] [Different people] [Leave line 62 out]
 Gilles P.   line 61      can't read 'one word (see the book)'  [Fill in what they can take] [Take off]
```

| Flag (✅ raised today) | Fix today ✅ | On the platform ✅ |
|---|---|---|
| Can't read part of a note | New line starting `start over - …` | **[Fill in what they can take]**: a card filled in from what could be read, including the prenatal routing. Saving it is a `start over` entry: older limits are dropped, and the person keeps their first-asked date |
| Identity mix-up (one phone, two names; one name, two phones; `same #` with no match) | Row in `reviewed.csv`: `same person` / `different people` / `ignore` | The same three buttons, one question per other line. For `same #` with no match, the desk types the other line's number |
| Date can't be read | New line | **[Fill in what they can take]** |
| Regular who booked since (B7) | New line | **[Still wants an extra visit]** (counts as contact) / **[Take off the list]** |
| Line changed since it was first saved (§4.4) | — | **[Keep the new text]** |
| Run warnings (opening not in the export, unknown therapist) | Julie reads the report | Listed at the bottom. 🔨 **[Acknowledge]** not built |

**How the desk's entries work:** "fill in", "still wants an extra visit" and "take off" are saved as **desk entries**: lines the desk adds on the screen instead of in the book, numbered from 10001 up so they never meet a book line (a book line numbered 10001 or more stops the sync). Each entry sits right after the newest book line at the time it was made, so a later line in the book still overrides it, as a newer line does today. The matching rules themselves are unchanged.

**Rules (✅ all built):**
- There's no "release all" button.
- Every decision needs a name, which is kept for the record and never shown on a screen or in an output file. 🔨 Per-person PINs (§12) would replace typing it.
- A decision can be undone; its row stays, marked undone.
- A count shows on every screen ("Needs review (4)").
- A **drift alarm** fires when more than 1 in 10 people are held: "the way the book is written may have changed".

**⚠ Privacy finding (Oct 30, this copy):**
- Today, an **unknown word** is quoted in the output. Tested by adding the line `any - 1hr - AM - shingles` to a copy of the sample waitlist: `preprocess-report.txt` and `out/core/people.json` both say `line 61: can't read 'shingles'`.
- `HEALTH_RE` has no "shingles", so a health word **missing from the drop list is printed**.
- The same thing on a desk screen would show a health word a client could read.
- **On the platform (✅ built Oct 30):** the unknown word is never stored. The person is still held, with the reason `line 61: can't read 'one word (see the book)'`, so the desk finds the word in the book.
- The command-line version in the frozen reference folder has the same behaviour (risk D2).

---

## 8. Output on screen (✅ opening queue and offers built Oct 30; booking states 🔨)

The files stay the same and can be downloaded from every run: `matches.csv`, `matches.txt`, `preprocess-report.txt`, `line-verdicts.csv` (✅ `report.py`). The **screen** is what the desk uses. It needs plain words, big buttons, no codes, and has to work for Bethany, who doesn't know the clients. It must pass the 10-second test.

Names and reasons below are the real output for O01 and O03 (`python run.py --run-date 2026-10-21`). The offer state is an example.

```
OPENINGS                                          soonest first · order: first asked · booking data from Oct 17
┌ MON SEP 21 12:30 · Josée · 60 min · 2.7 h notice · cancelled 09:47 by phone ── OFFERING #1 · Tanya · 10:05 (12 min) ┐
│  1  Amanda Bourgeois  506-555-0125  Josée or Rachel · 60 min · 2 h notice        [ask Josée first]  ▶ offered        │
│        [Yes]   [No]   [No answer]                                                                                     │
│  2  Joel Bertin       506-555-0135  any therapist · 30/45 min · weekdays · 12:00–1:00 · 0.5 h notice  [ask Josée first]│
│  3  Nicole Vautour    506-555-0139  Amira or Josée · 60 min · not Fri · 2 h notice   [ask Josée first]                │
│     Not offered: Gisele Maillet (no contact over 60 days) · Pauline Bastarache (mornings only)                        │
└───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
┌ TUE SEP 22 11:00 · Kelsey · 90 min · 3.8 h notice ───────────────────────────────────────────────────── NEW ────────┐
│  1  Sarah Collette    506-555-0109  Amira or Kelsey · 60 min · weekdays · 2 h notice            [Offer]                │
│  2  Ginette Losier    506-555-0119  female therapist · 60 min · Tue/Thu · 2 h notice            [Offer]                │
│  3  Tina Saulnier     506-555-0129  Amira or Kelsey · 60 min · done by 2:30 · 2 h notice        [Offer]                │
└───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```
Sarah Collette's line says she is pregnant. The screen shows only "Amira or Kelsey", as the files do today.

- **Up to 3 names, or "Nobody fits"**, each with phone, a one-line reason and flags (`ask Josée first`, `new client, phone only`, `text only`).
- **Not offered:** the closest people left out, and why. This is so Tanya can answer "why didn't I get the call?"
- **Order** used is shown on every opening.
- **Booking data** is shown at the top: when it was last updated, and any **gap** in the history ("⚠ no booking data for Oct 18–27: someone who booked in those days may still be listed").
- **Hold** shown on each opening being offered ("held: manual block 10:04"). [Offer] stays locked until the hold is placed (§10.1).
- **No health detail anywhere**, including the prenatal reason, which shows only as the therapists offered.
- Status per opening: new → offering #n → filled / expired / taken online.

---

## 9. Bookings at risk, and how a slot changes state

### 9.1 States

Technical plan §8, extended with the at-risk stage the desk works today. **"Not confirmed" is not "cancelled".**

```
BOOKED ──(Kneadly reminder, T−48 h, "reply C")──► REMINDED ──reply C / desk call──► CONFIRMED ──────────┐
                                                     │                                                  │
                                                     └── no reply by T−24 h ──► AT RISK (still booked!) ┤
                                                           │  call list: [Confirmed] [Voicemail ●] [Cancelled]
                                                           │                                            │
   any state ──── cancelled (online · voicemail · text reply · phone · morning call) ─────► CANCELLED ◄─┘
                                                                                               │
                         cancelled_at ≥ 24 h before start → NORMAL CANCEL (recorded; Kneadly's online page refills it)
                         cancelled_at < 24 h before start → LATE OPENING → OFFERING #1…#n → FILLED → new booking (§10)
                                                                                         └──► EXPIRED / TAKEN ONLINE
   not arrived by start + 15 min ──────────────────────────────────────────► NO-SHOW (recorded; never offered)
   arrived ────────────────────────────────────────────────────────────────► COMPLETED
```

### 9.2 What the sample data says (checked Oct 30)

| Fact | Number | What it means for the design |
|---|---|---|
| Late cancellations that had **confirmed** first | **26 of 36** (23 by text, 3 by phone) | Confirmation predicts little. **At risk must never create an opening.** It's a list to call, not a list to fill |
| No-shows that were **unconfirmed** | **7 of 8** | "At risk" mostly predicts **no-shows**, which are never offered anyway. Its value is getting a late cancel out of someone **during the call**, early enough to refill |
| Late cancellations already in by 9:15 | 29 of 36 | Heard overnight or during the morning calls. A "Cancelled" tap at 08:20 has to produce names at once (§11.5 of the technical plan) |
| Overall confirmation | text C 53.8% · phone 17.3% · none 26.9% · same day 2.0% | About 44% of bookings weren't confirmed by text (phone + none). Those are the ones on Tanya's call list today, so the at-risk list will be about that size |
| How the 36 late cancellations were heard | voicemail 12 · online 11 · phone 5 · morning call 5 · text reply 3 | Only "online" (11) can arrive by itself, and only with a feed. Text replies (3) only if Kneadly passes them on. The rest are desk taps unless a phone service is added |
| How the 12 refills happened | client happened to call 5 · desk called the waitlist 4 · rebooked online 3 | The offer log will show whether the platform moves the "desk called" number |
| The 3 online rebookings | All overnight (01:02, 05:06, 07:20); all 3 had been cancelled by **voicemail** | Holding a slot at once would block these, so the hold starts at the first offer. And Kneadly's state can't be guessed from the channel (§10.1) |

### 9.3 Where each update comes from

| Event | Phase 1: uploads + desk taps 🔨 | Phase 3: assumed feed 🔮 | What the platform does |
|---|---|---|---|
| Reminder sent | **Not in the export** ❓. Assumed at T−48 h for every booking, as the interview says | Event with a time, if Kneadly exposes it | BOOKED → REMINDED |
| Client replies "C" | The `confirmation` column in the appointments upload (value only, no time) | Event with a time | → CONFIRMED |
| No reply at T−24 h | Worked out from the upload: unconfirmed and starting within 24 h | Same, from live data | → AT RISK; appears on the call list |
| Desk call: confirmed / voicemail / cancelled | ✅ **One tap on the call list** | Same (taps stay) | → CONFIRMED / voicemail dot (try again) / CANCELLED. The desk still marks it in Kneadly as today |
| Online cancellation | Next upload: `status`, `cancelled_at`, `cancel_via` | Checks every 1–2 min, then a live read | → CANCELLED; if late, → opening + names |
| Overnight voicemail | ✅ Inbox: the desk picks the booking, "voicemail (overnight)", and the time it was left | 🔮 Voicemail-to-text service → **suggested** row, then one tap to confirm. An outside service hearing health details needs Marc's one-pager | Same |
| Text reply ("can't make it") | ✅ Inbox entry ("text reply") | 🔮 Only if Kneadly passes replies on → **suggested** row, then one tap | Same |
| "Running late" | Nothing (it isn't a cancellation) | Suggested rows never become openings by themselves | — |
| Not arrived at +15 min | Desk tap "No-show" or the upload's `status` | Feed | → NO-SHOW. Kept as a risk signal for the call list, never offered |
| Someone books the freed slot online | Upload (`booked_via = online`), or the desk's check in Kneadly before the hold | Live read before the hold and before each offer | Opening → TAKEN ONLINE; "stop calling" shows on the offer |
| Visit completed | Upload `Completed` | Feed | Closed. Feeds "booked since" and regulars |

### 9.4 Screens for this

**Today & tomorrow (the call list) ✅ (built Oct 30, `/calls`)**, from technical plan §11.5. It replaces the sticky note and the dots. As built (checked in the browser):

```
MORNING CALLS                     Calls for [2026-10-30] and the day after [Show]   Phone numbers: in Kneadly
To call (2)
 Fri 17:30  Kelsey · 60 min  M. Gallant    A-99402                          [Confirmed] [Voicemail] [Cancelled]
 Sat 10:00  Rachel · 60 min  L. Arsenault  A-99403                          [Confirmed] [Voicemail] [Cancelled]
Cancelled (1)
 Fri 15:00  Dave · 60 min    R. Comeau     A-99401   cancelled 11:20
   D01 · 3.7 h notice left · hold and offer on the Openings page
   1 Luc Bernard 506-555-0121 line 53 · any therapist · 60/90 min · not Sat · 2 h notice
   2 Greg Wilson 506-555-0133 line 37 · any therapist · 60 min · Fri · from 3:00 · 2 h notice   …
```

- **Who's on it:** today's bookings still to come and tomorrow's, from the latest upload, not cancelled or missed, and not confirmed: "text C" and "phone" count as confirmed, "n/a (same day)" needs no call. Another pair of days can be looked at.
- **Confirmed:** the row moves to Confirmed (folded away). **Voicemail:** the row moves to "Try again" with a dot and the time per call. Both can be undone.
- **Cancelled** goes through the inbox as a "morning call" with `cancelled_at` = now: under 24 h before the start it's an opening at once, matched, and its names (with phone numbers) are shown **under that row**: Tanya is already on the phone. 24 h or more ahead, it's only recorded. Already heard another way (the inbox) → no second opening. A visit that has started can't be cancelled here (that's a no-show). A cancellation can't be undone on the call list: release the opening on the Openings page.
- **Phone numbers** of the booked clients aren't in the booking export, so they stay in Kneadly ❓ (the API may give them, §4.5).
- 🔨 Optional sort by risk signals (technical plan §12: new client, past no-show or late cancel, booked long ago). It's off until Marc decides, because ranking clients by past behaviour has to be explainable (risk C8).
- The list is only as fresh as the last appointments upload: a client who confirmed by text since then still shows. 🔮 The API fixes that.

**Cancellation inbox ✅ (built Oct 30, `/inbox`)**, from technical plan §11.6. It has one row per cancelled appointment, whichever way it was heard. Rows sort soonest-start first. The same cancellation heard twice (voicemail, then online) is merged by `appointment_id`.
- **Enter a cancellation:** the day's bookings (from the uploads) are listed with the client as "R. Comeau"; **Cancelled** → how it came in (voicemail, phone, text reply, morning call, online, other) and when (now, or the voicemail's time). No reason is asked for or kept. A booking made after the last upload is entered with its Kneadly appointment number.
- **Under 24 h before the start:** an opening (D01, D02 …) with names straight away; the page jumps to it, ready for the hold step. The booking is marked "Late cancel", so "booked since" stays right.
- **24 h or more:** only recorded ("not late: Kneadly's online page offers it"); the booking is marked "Cancelled".
- **Refused:** a time after the start (a no-show, never offered), a time later than now, a channel not on the list, a second entry for the same appointment ("already in the inbox").
- **The list:** "Coming up" (with notice left and status: new, held, offering, filled …) and "Earlier"; the openings screen also puts upcoming openings first.

**Suggested updates 🧪/🔮.** Anything that arrives automatically appears as a grey row, e.g. "Online cancel at 06:31 looks like Tue 11:00 Dave: confirm?". It only becomes an opening after a person taps **Confirm**. Rows from Kneadly's own cancellation record can be set to confirm themselves, but only once Julie confirms the feed is reliable.

### 9.5 Rules for this part

1. **Only a recorded cancellation creates an opening:** in Kneadly, or by a desk tap. "At risk" never does.
2. **No pre-matching of at-risk slots.** The matcher takes under a second, so there's nothing to gain. A list of names next to a slot that is still booked invites someone to call about it, which risks a double booking.
3. **"Late" is decided by `cancelled_at` vs the start**, not by when the platform heard about it.
4. **One opening per `appointment_id`**, however many channels report it.
5. **The slot is held in Kneadly before the first offer** (§10.2). The desk never frees a slot and then offers it: a cancellation the desk heard is recorded in Kneadly together with the hold. This replaces technical plan §8 rule 2 ("the desk frees the slot before the first offer"), which leaves the slot open to the online page while the desk is calling.
6. **Kneadly's state is read, never guessed** from how the cancellation was heard (§10.1).
7. **No cancellation reason is stored.** Only the channel and the time.

---

## 10. The refill loop: from a late cancellation to a new booking in Kneadly

Two things can give the same slot away:
- **Kneadly's online booking page**, the moment a slot is free there.
- **The desk's calls and texts**, which often happen outside Kneadly.

A faster sync makes the gap between them smaller but can't close it, because an online booking can land between any two checks. Only a **hold on the slot in Kneadly** closes it.

**The rule:** while the platform is offering a slot, Kneadly shows that slot as taken.

### 10.1 Check → Hold → Offer → Confirm → Release

Phase 1 is ✅ built (Oct 30) on the openings screen, except where marked.

| # | Step | Phase 1 ✅ (no API) | Phase 3 🔮 (API) |
|---|---|---|---|
| 1 | **Opening created** (upload, inbox tap, call list, API) | ✅ Matcher gives up to 3 names (from an upload, the inbox or the call list) | Same |
| 2 | **Check:** is the slot still free in Kneadly? | ✅ Desk looks in Kneadly; **Already taken in Kneadly** closes the opening | Live read |
| 3 | **Hold**, at the first offer, not at the cancellation | ✅ Desk blocks the time in Kneadly by hand and ticks **"It's still free, and I blocked it"** → **Hold placed**. **[Offer] doesn't appear until then** | Platform places the hold (§10.2) |
| 4 | **Offer** | ✅ One live offer per opening: the database itself refuses a second (`one_live_offer`). Every screen shows "Offering to Amanda Bourgeois · Tanya · 12 min". Who's at the desk is remembered by the browser, so it's one tap | Same |
| 4a | No, or no answer after ~20 min | ✅ Logged in `offers`; that person is never offered **that** opening again; the openings are matched again at once, so the next person who fits moves up. After 20 minutes the card says "if there's no answer, move on" | Same |
| 4b | All 3 fail | ✅ Happens by itself: each no is matched out straight away (replaces `--declined`). Inbox openings count notice from now (§7.1) | Same |
| 5 | **Confirm**, on a yes, **before** telling the client "you're booked" | ✅ The **booking card** needs the tick "our hold is still there"; nothing is saved before | Live read of the slot |
| 6 | **Book** | ✅ Case by case on the booking card (§10.3), length from what they can take | Case by case; through the API where allowed (§10.4) |
| 7 | **Release**: nobody left can meet their notice | ✅ **Nobody left: release** needs the tick "I removed the block in Kneadly". **Filled another way** (a client called in, booked online) withdraws a live offer. **Reopen** if marked by mistake | Platform removes the hold |
| 8 | **Close and count** | ✅ Opening → filled; the person is off the list at once ("booked from the waitlist into O05 …"), until a newer book line; **Undo: not filled** puts it all back. 🔨 Refill numbers per channel (§11) | Same, plus Kneadly's new appointment ID |

**Why the hold starts at the first offer, not at the cancellation:**
- All 3 online rebookings in the sample happened overnight (01:02, 05:06, 07:20), before the desk opens.
- Holding a slot as soon as it's cancelled would block those.
- The desk can't call anyone before 8:00 anyway.

**Cancellations heard by the desk** (phone, text, voicemail, morning call): don't free the slot in Kneadly and then offer it. Record the cancellation **together with** the hold, or together with the new booking.

**Never assume the slot's state from how the cancellation was heard.** All 3 slots rebooked online in the sample had been cancelled by **voicemail**, yet they were free online overnight. Example: O12, voicemail at 21:58, rebooked online at 01:02. Nobody knows what freed them ❓. So always read the slot.

### 10.2 How a slot is held

Julie: "I can block time by hand, but there's no hold." Whether the API can block time is unknown ❓. There are four ways, best first:

| Way | How | Status | Risks |
|---|---|---|---|
| **A. Block through the API** | The platform blocks the therapist's time, and removes the block on release | 🔮 ❓ | Unknown whether the API can block time |
| **B. Placeholder booking through the API** | The platform books the slot to a clinic-owned client, "WAITLIST HOLD", with no phone or email. On a yes it becomes the client's booking; on release it's removed | 🔮 ❓ | See below |
| **C. Manual block by the desk** | The desk blocks the time in Kneadly and ticks "hold placed" | 🔨 works today | One more step at a busy desk. Skipping it re-opens the gap, so [Offer] stays locked until it's ticked |
| **D. No hold** | Only the live read just before "you're booked" | Fallback; not recommended | A window of minutes in which someone can book online |

**Risks of B (the placeholder booking):**
- Kneadly may send its automatic messages for it. With no contact details on the placeholder they go nowhere, but that needs checking ❓.
- It appears in exports as a booking and then a cancellation, so reports and the "booked since" check must leave it out by its client ID.
- Removing it might be recorded as a late cancellation.
- A placeholder left behind blocks a slot that could have been refilled. It's removed automatically when the opening closes, and the daily check lists any that remain.

**Turning a placeholder into the client's booking:** change the client on the same booking, if the API allows it. If the API can only cancel and re-book, there's a short gap in which the slot is free. Whether that gap can be avoided depends on Kneadly ❓. Book the client first if Kneadly accepts two bookings in one slot for a moment; otherwise remove the placeholder and book straight away, with a live read in between.

### 10.3 Booking the client into Kneadly, case by case

The **hold** is always placed. Whether the **client's booking** goes into Kneadly, and when, depends on the case:

| Case | Suggested | Why |
|---|---|---|
| Existing client, visit later today or tomorrow | Write the booking now (the hold becomes the booking), ideally without Kneadly's automatic message ❓ | The therapist sees who is coming; "booked since" and "rebooked into" stay right |
| Existing client, visit within ~2 h | The hold, with the client's name, is enough; the desk turns it into a booking at check-in | A confirmation message minutes before the visit is noise |
| New client (no Kneadly profile) | The hold, with the client's name; profile and intake form when they arrive | No profile or text consent yet |
| A client called in and Tanya booked them directly | One tap, "filled another way", on the opening | Stops the platform offering a slot that's gone |

**Every refill ends up in Kneadly by the end of the visit.** The therapist's schedule, treatment notes, payment and the "rebooked into" link (how refills are counted) all live there. So "not required" means "not required straight away". The **daily check** (✅ built, `/check`, with a count on the openings screen) lists:
- every refill not in Kneadly yet, with **It's in Kneadly now** (and the Kneadly number, optional)
- every slot still blocked after its start time, never filled or released, with **I removed the block**
- every offer waiting more than 20 minutes for an answer

**rebookings.csv** (✅ built, a download): every refill, with opening, "rebooked into", client, phone, length, how, whether it's in Kneadly. No desk names.

**Booking card** as built (✅): the client, phone, line and "new client, phone only" flag; **Length** (what they can take that fits the opening); **How it goes into Kneadly**: "I've booked it in Kneadly now" (+ number, optional) / "Keep the hold with their name; book it at check-in" / "New client: keep the hold; profile and intake when they arrive"; the required tick **"I checked Kneadly: our hold is still there"**; then **Save: filled**. The design sketch it came from, continuing the O01 example in §8 (the Kneadly client link and the platform booking button are 🔮 Phase 3):
```
CONFIRM REFILL ─ O01 / A-24010 (late cancel, cancelled 09:47 by phone)
  Client:     Amanda Bourgeois · 506-555-0125 · Kneadly client: [link ▾] (suggested by name)
              ← shows "new client: create the profile in Kneadly first" if there is none
  Therapist:  Josée Landry  ☐ asked Josée     Date: Mon Sep 21    Start: 12:30    Length: [60 ▾] (opening 60; she asked for 60)
  Rebooked into: A-24010      Offered by: Tanya, 10:05 · said yes 10:11
  Hold:       manual block, placed 10:04 by Tanya      ☐ still there
  Case:       [visit later today: book now ▾]
  [Booked in Kneadly by hand]            [Book in Kneadly]   (platform bookings: off)
```

### 10.4 What the platform does, depending on what the API allows

| What the Kneadly API allows | Check | Hold | Client's booking |
|---|---|---|---|
| Nothing (Phase 1) | Desk looks | Desk blocks by hand (C) | Desk books by hand |
| Reading only | Live read | Desk blocks by hand (C) | Desk books by hand |
| Reading + blocks or bookings | Live read | Platform holds (A or B) | Desk books by hand |
| Reading + bookings without automatic messages | Live read | Platform holds (A or B) | Platform books, case by case (§10.3) |

Each level only adds to the one before. The rule at the top of §10 holds at every level.

### 10.5 Before the platform places holds or bookings itself (all needed)

1. The API can do it, and refuses a booking in a slot that's already taken ❓ (§16).
2. Marc says yes in writing, with a one-pager: what is written, where, and by whom. This is a change from the technical plan (§10.6).
3. Every simulated test passes: one live offer, hold placed and released, slot taken during the offer, timeout, no placeholder left behind, and the daily check finds a planted difference.
4. Only existing Kneadly clients with a linked client ID get bookings from the platform. New clients are booked by hand.
5. Every booking the platform creates carries a key (the opening ID), so a retry never books twice. On a timeout the status becomes "unknown: check Kneadly", with no automatic retry.
6. Marc has seen the exact wording of any message Kneadly sends when the platform creates or removes a booking.
7. An owner-only switch turns it off. Everything then falls back to the manual way (first row of §10.4).

### 10.6 Changes from the technical plan

- **§8 rule 2** said "before the first offer, the desk frees the slot in Kneadly". **Now:** the slot is **held** before the first offer, and a cancellation heard by the desk is recorded together with the hold.
- **§11.4** said "the platform never writes bookings; the desk does". **Now:** the platform may place holds and write bookings, but only at the levels in §10.4 and behind Marc's switch.
- If §10.5 can't be met, it stays manual: the desk blocks and books by hand. Nothing else in this plan depends on the platform writing to Kneadly.

---

## 11. Feedback loop (✅ built Oct 30, `/report`; technical plan §11.7)

**Leakage rule:** an opening's outcome never decides who is offered **that same** opening. Outcomes only inform later ones, and always through a person. The matcher never learns by itself. (A "no" still takes that person off that one opening, as in step 5; that is their answer, not learning.)

| Offer data | Feeds into | Who acts | Status |
|---|---|---|---|
| Offered / yes / no / no answer | **Anti-pestering:** someone offered the weekly limit's number of times in the last 7 days **rests** until the oldest of those offers is a week old. They stay on the opening they're being offered right now; everywhere else the next person who fits is shown. A "Resting this week" box on the openings screen and a chip on their card say until when. A slot someone declined is never offered to them again (step 5) | Automatic limit; **Marc sets the number** (Settings → "Offers per person per week", 0 = no limit) | ✅ (off until Marc decides) |
| 3 no's (or no answers) in a row | Their card on the board says "said no 3 times in a row: ask if still interested" | Desk | ✅ |
| "No, keep me on" | A second "No" button: counts as contact (the 60-day clock restarts, through a "still interested" entry), and still a no for this opening | Automatic | ✅ |
| Why they said no: the time, the day, too short notice, the therapist, the length, or "our mistake: they'd said they can't". Picked from a list; **no free text** and no health reasons are ever kept | "Why people said no" on the report: a reason that keeps coming back may mean a default is wrong | Julie with Marc, monthly | ✅ |
| Each week's openings, offers and answers | `outcomes.csv` (opening, slot, therapist, notice, each offer as "W51 no (the day)", who got it): the raw material for **new test cases**. Turning them into tests is still by hand | Julie runs the tests | ✅ file / 🔨 tests |
| `heard_via`, the offers, the rebooking | The report: what happened to each late opening (refilled from the waitlist, filled another way, released, offered but not filled, no offer recorded), refills by channel, and the **median time from hearing about a cancellation to booking someone** (Marc's numbers) | Report | ✅ |
| `booked_via` + `rebooked_into` in the booking export | "How the booking export says slots were refilled": booked online / the client phoned / the desk called. In the sample (Sep 21–Oct 17): 5 phoned, 4 the desk called, 3 online | Report | ✅ |
| "Our mistake: they'd said they can't" | Listed under "Possible wrong offers" on the report (opening, person, line, when): each one becomes a test case | Julie | ✅ list / 🔨 tests |

**Not done:** a resting person comes back on the openings screen at the next match (any upload or desk action), not at the exact minute the week ends. That errs on the side of fewer names, never wrong ones. Offers made outside the platform aren't counted (risk H5).

---

## 12. How it's built

**Stack 🔨:**
- **Python** (the existing `kettle` package, unchanged except the tag change in §7.2).
- Python's own web server (`wsgiref`, one thread per connection), not Flask or FastAPI: nothing to install, in keeping with the matcher's standard-library-only build (✅ Oct 30).
- **SQLite**.
- Pages rendered on the server with very little JavaScript, so Julie can look after it and there's no build step.
- It runs on the desk computer at `localhost` and starts from a desktop shortcut (`python serve.py`). It refuses requests that name another host or come from another site.
- ❓ Which browser the desk uses (Julie).

**Folders (planned):**
```
kettle/                         ✅ unchanged core: normalise, parse_notes, people, match, report, pipeline
kettle/adapters/csv_in.py       ✅ CSV adapter (used by the upload screen as is)
kettle/store.py                 ✅ the database: tables (§5), saving and loading the records the core uses
kettle/adapters/upload.py       ✅ syncs an upload into the database: booking history, waitlist migration, sync log, gap check
sync.py                         ✅ the same sync from the command line (the upload screen calls the same code)
serve.py                        ✅ starts the screens: python serve.py, then http://localhost:8000
kettle/adapters/board_in.py     🔨 cards + card edits → the same people records the matcher uses
kettle/adapters/kneadly_sim.py  🧪 stand-in for the Kneadly API (fixture files, no network)
kettle/adapters/kneadly_api.py  🔮 real adapter, same interface (reads first; holds and bookings only if §10.5 is met)
webapp/app.py                   ✅ upload (check, save, cancel), openings, downloads, sync log · 🔨 offers, review, board, call list, rules, settings
webapp/pages.py                 ✅ the HTML for each screen
webapp/cards.py                 ✅ the fill-in card on the review screen → the same fields the note parser produces
webapp/settings.py              ✅ the settings form ↔ config/clinic.json, the screen's own checks, changes in plain words
webapp/states.py                🔨 booking states and events (§9)
webapp/holds.py                 🔨/🧪/🔮 holds and client bookings: manual (desk ticks), fake Kneadly, real API (§10.4)
run.py                          ✅ stays: the command line keeps working as a fallback
```
The web folder isn't called `platform/`: that name would hide Python's own `platform` module, which pytest and other tools use.

**Who can do what:** per-person PINs on the shared desk computer. These exist for the audit log, not for security theatre. No personal accounts or devices.

| Role | Can |
|---|---|
| Desk (Tanya, Bethany) | Board, call list, inbox, offers, review (identity, unreadable notes) |
| Julie (admin) | Uploads, settings, rule drafts, warnings, backups, replays, the admin view of unreadable words |
| Marc (owner) | Approve rules and order changes; **Pause platform**; **platform holds and bookings on/off**; read the audit log ("what was sent to whom": here, what was written to Kneadly) |

**Off switch:**
- **Pause the platform** (✅ built Oct 30, on the settings screen) stops uploads, `sync.py` and review decisions; 🔨 later also holds and bookings. Every screen then says "paused, use the notebook".
- The notebook and the command line still work.
- The platform sends no messages, so there's nothing else to switch off.

**Running cost:**

| Item | Phase 1–2 | Phase 3 |
|---|---|---|
| Software and hosting | $0 (desk computer) | $0 if it stays on the desk computer |
| Kneadly plan | $0 | ~$45/month **if** the higher plan is needed (unchecked) |
| Texting | none | none |
| **Total** | **$0** | **~$45**: under Marc's $50 only if nothing else is added. Hosting ($5–12) would push it over, which is another reason to stay local |

**Upkeep:**
- A web app with a database is more to look after than a script.
- To keep Julie near **1 hour a month**: it starts automatically, there's a "health" page (last upload, gaps in the booking history, open holds, held count, warnings, last backup), and the database is copied every night to a clinic-owned place ❓.
- Phase 2/3 work needs a developer: about $90–120 an hour.

---

## 13. Tests

| Test | Checks | Phase |
|---|---|---|
| The 148 matcher tests | Unchanged and still passing after every change | ✅ |
| **Same as the script** | Sample files into an empty database → `matches.csv`, `matches.txt`, `line-verdicts.csv` and `core/` identical byte for byte to `run.py`; the report identical apart from its list of inputs; matching again from the database alone gives the same names | ✅ `tests/test_sync.py` |
| **History kept** | The sample export split in two (all but the last 2 days, then the last 2 days as a second upload) → the same results as the full export; 0 wrong names. A 2-day file on its own leaves the 4 people who got in looking active | ✅ |
| Gap check | A file that starts after the history ends → a gap warning naming the missing days (Sundays left out) | ✅ |
| Database round trip | Every sample line's fields come back from the database unchanged, except what is never kept | ✅ |
| Nothing saved from a bad file | A file with a missing column stops the sync and the database is unchanged | ✅ |
| Adapter contract | CSV adapter, stand-in adapter and board adapter give identical core records and matches for the same data | 🔨/🧪 |
| Privacy, extended | No health word, note text or unknown word in **the database file**, any output file, or the HTML of the upload, check, openings and sync log screens | ✅ |
| Screens | Check saves nothing; save fills the database and gives `run.py`'s `matches.csv`; a bad file or bad date is refused with nothing saved; a cancelled check can't be saved; gaps shown before and after saving; names escaped; other hosts and sites refused; only the output files can be downloaded | ✅ `tests/test_webapp.py` |
| Review queue | Each kind of held person shown with the right decisions; same person / different people / leave out / typed-in line; fill-in releases and keeps the queue place; the card starts from what could be read, prenatal routing included; a bad card saves nothing; a later book line still overrides a desk entry; still wants it; take off; keep new text; undo holds them again; a name is required and never shown; each decision re-matches the last run's openings; unclear decisions refused; drift alarm | ✅ `tests/test_review.py` |
| Settings | An unchanged form saves nothing; a change lists the names it changes before saving; saving writes a file the settings check accepts, keeps versions (with the settings before the first change) and matches again; putting a version back; each kind of mistake named with nothing saved; adding and removing therapists ("any" follows the list; "Dave only" is held); a new order; an edit outside the screen pointed out; name required and never shown; compare orders (O01: the 4 on Tanya's list fit); pause stops uploads, `sync.py` and decisions, not settings. All on a copy of `config/clinic.json` | ✅ `tests/test_settings.py` |
| Waitlist migration | Same files twice → no change; the same book + new lines → only those added and merged into the right person; a changed old line → warning + held, still held on the next run; the same cancellation in two files → one opening; a status change → a booking event | ✅ |
| Notice by source | Openings from a file count from the cancellation; live ones from now | 🔨 |
| Card edit vs notebook line | Edit overrides only its fields; a later notebook line overrides the edit; a same-day tie → edit wins + warning | 🔨 |
| Review decisions | Each button gives the same result as the matching `reviewed.csv` row today | 🔨 |
| Routing rules | The sample routes exactly the two pregnant clients; a file without `routing` gets the same rule; no rules = no routing; a new rule routes to the tagged therapist and the card's reason never shows; start over drops an older line's routing; old saved lines still route by the old flag; extra private words dropped, not held; whole-word and `*` matching; each rule mistake named | ✅ `tests/test_routing.py` |
| Rules screen | Shows the pregnancy rule; a new rule needs Marc's approval (refused without, nothing saved), then routes the next upload's lines to the tagged therapist without keeping the reason; a tag nobody has, a bad tag or a shorthand word refused; taking a tag away shows the names it changes; a private word added, then dropped, not held; a chip per rule on the card; a tag no rule uses needs no approval | ✅ `tests/test_rules_screen.py` |
| Switches | Every order gives the same **set** of people who fit; the 3 shown = the first 3 in that order | 🔨 (✅ partly) |
| Offer loop | Who's at the desk is remembered; no offer before the hold (and the hold needs its tick); the database refuses a second live offer; a no brings the next name and counts for that opening only; the minutes and the 20-minute hint; a yes goes through the booking card (hold tick, length, how) before anything is saved; whoever said yes is off the list everywhere; undo puts it all back; refills not in Kneadly in the daily check and rebookings.csv; filled another way withdraws the offer (not counted as a no) and can be reopened; release needs the block removed; slots still blocked after their start; refused while paused; desk names on screen, never in a file | ✅ `tests/test_offers.py` |
| Cancellation inbox | The day's bookings listed (client as "R. Comeau"); a late cancellation becomes an opening with names at once, marked "Late cancel" with a booking event; notice from now, so the names change as the start gets closer; 24 h or more only recorded; one row per appointment however it's heard (including the sample's own openings); times after the start or later than now refused; entry by Kneadly number, with bad numbers, therapists and times refused; the list's statuses; desk name needed; refused while paused; no reason column | ✅ `tests/test_inbox.py` |
| Morning call list | Only unconfirmed bookings today (still to come) and tomorrow: text-confirmed, started, same-day and later ones left out; soonest first; another day; Confirmed (and undo); Voicemail with a dot per call, then confirmed; Cancelled today → an opening with its names under the booking (rendered as names); Cancelled 26 h ahead → only recorded; already in the inbox → no second opening; a cancellation can't be undone there; a started visit can't be cancelled; desk name needed; refused while paused | ✅ `tests/test_calls.py` |
| Waitlist board | Cards with chips and no health detail (a pregnant client shows "Amira or Kelsey"); filters and search; Edit card shows each field once, changes the names at once and keeps the queue place; an unchanged card saves nothing; a newer book line overrides the card; still interested resets the clock; take off with a listed reason only; + Add refuses a number already on the list and a bad number, then adds; history without notes, and undo; board only refuses book uploads (not openings) and can be switched back; desk name needed; refused while paused | ✅ `tests/test_board.py` |
| Feedback loop | No limit → nobody rests; at the limit (2) a person leaves every other opening's names but stays on the one they're being offered, shows in "Resting this week" and on their card, and is back a week later; the reason for a no is kept and counted, and anything not on the list is dropped; "No, keep me on" restarts the 60-day clock and is still a no; 3 no's flag the card; "our mistake" listed as a possible wrong offer; the report's counts on the sample (36 late openings, 8 no-shows, a refill and a "filled another way", the export's 5/4/3); `outcomes.csv` rows with no desk names; the limit on the Settings screen with its check | ✅ `tests/test_feedback.py` |
| Booking states | Every transition in §9.1; at risk never creates an opening; a cancellation heard twice → one opening; late vs normal by `cancelled_at` | 🧪 |
| Time zone | Notice across the **Nov 1, 2026** clock change (Atlantic Daylight → Standard Time) is right to the minute | 🔨 |
| Holds and bookings (fake Kneadly) | Block and placeholder placed and released; placeholder → client's booking with no free moment; slot taken online before the hold → "taken online", no offer; a retry never books twice; a timeout → "unknown"; no placeholder left after the opening closes; the daily check finds a planted difference | 🧪 |
| Robustness (technical plan P2) | Shuffled rows, run dates Oct 21 / Oct 30 / Nov 15, an extra therapist → expected results | 🔨 |

---

## 14. Build order

| # | Step | Status | Depends on |
|---|---|---|---|
| 1 | Database tables; seed them with the current sample CSVs (waitlist migration, booking history, openings); the sync itself (history, migration, sync log, gap warning) from the command line; "same as the script" test | ✅ Oct 30: `python sync.py` | — |
| 2 | Upload screen on top of the sync; opening queue; downloads; sync log screen | ✅ Oct 30: `python serve.py` | 1 |
| 3 | Review queue (replaces `reviewed.csv`); unknown words no longer quoted on screen | ✅ Oct 30: `/review` | 1 |
| 4 | Settings and switches screen, with compare orders | ✅ Oct 30: `/settings`, `/compare` | 1 |
| 5 | Offers: check, hold step (manual block, ticked), lock, timer, yes/no/no answer, re-run, release, booking card with cases, daily check, `rebookings.csv` | ✅ Oct 30 | 2 |
| 6 | Cancellation inbox + one-tap entry | ✅ Oct 30: `/inbox` | 5 |
| 7 | Today & tomorrow call list from the appointments upload + "Cancelled → names" | ✅ Oct 30: `/calls` | 6 |
| 8 | Tags + routing words in the core, then the rules editor with check, preview, tests and approval | ✅ Oct 30: `/rules` (one core change; sample unchanged) | 4 |
| 9 | Waitlist board, mode A, **after Tanya's timing test**; mode B on a set date | ✅ Oct 30: `/board` (built before the timing test; mode B is a switch, off) | 3, ❓ timing test |
| 10 | Feedback reports and anti-pestering limits | ✅ Oct 30: `/report`, `outcomes.csv`; the weekly limit is a setting (0 = off until Marc decides) | 5 |
| 11 | Kneadly stand-in + booking-state simulator + fake Kneadly for holds and bookings | 🧪 | 7 |
| 12 | Real Kneadly reads: live at the four moments, checks every 1–2 min | 🔮 | §3 gates |
| 13 | Holds placed by the platform, then client bookings case by case | 🔮 | §10.5 |
| 14 | Text replies and voicemail as suggested rows | 🔮 | Marc's one-pager, Julie |

---

## 15. Risks

**The five that matter most**
1. **A double booking**: the online page gives away a slot the desk is offering, the hold is skipped, two staff offer at once, or the platform books twice (A1–A5, A9, A10). This is Marc's first deal-breaker.
2. **A health word on a desk screen**: an unknown word quoted in the review queue, or a routing chip in view (D2, D3).
3. **Missing booking history**: a file covering only a few days can't show who booked earlier, so a person who already got a slot is offered again (the hard-gate failure). Tested: a 2-day file on its own gives wrong names on 35 of 44 sample openings (B4).
4. **The Kneadly API doesn't exist, can't hold or book, or costs more than assumed.** The platform would stay at the manual level (§10.4). The plan is built so Phase 1 stands alone (B1, A6, B3).
5. **Tanya doesn't use it**: more taps than the book, or two lists during the transition (H1, E1).

### A. Double booking, holds and bookings in Kneadly

| # | Risk | How it would happen | Mitigation | Status |
|---|---|---|---|---|
| A1 | Two people say yes to one slot | Two staff offer the same opening (it happened last spring), or someone texts from the clinic mobile outside the platform | One live offer per opening, kept by the database itself; every screen shows who is offering and for how long; 20-minute hint; desk rule: offers only through the platform | ✅ |
| A2 | Slot taken online while it's being offered | An online cancellation frees the slot on Kneadly's online page straight away | Hold before the first offer (§10.2); live reads before the hold and before "you're booked"; a new `online` booking in the slot closes the opening ("taken online") | 🔨/🔮 |
| A3 | The platform creates a booking twice | Timeout, then a retry | Key = opening ID; "unknown: check Kneadly", no automatic retry; daily check | 🧪/🔮 |
| A4 | The platform books the wrong client, length or therapist | Client linked by name (A5 nickname matching) | Client link confirmed by a person; the booking card shows every field; only linked existing clients | 🔮 |
| A5 | Booked by hand **and** by the platform | Desk doesn't know which way this opening is booked | One way per opening, shown on the booking card; daily check | 🔮 |
| A6 | The API can't block time or create bookings, or only on the higher plan | Kneadly limits | Manual hold and booking (first row of §10.4); nothing else depends on it | 🔮 |
| A7 | Kneadly sends its own message when a booking or placeholder is created or removed | Kneadly's automatic confirmations | Marc sees the exact wording first; no contact details on the placeholder ❓ | 🔮 |
| A8 | Length booked isn't what the person wanted | A 45-min person takes a 60 opening | The desk picks the length on the booking card; clinic rule ❓ (Tanya/Marc) | 🔨 |
| A9 | **The hold isn't placed** | A busy desk skips the manual block | [Offer] doesn't appear until "hold placed" is ticked; the tick is saved with who and when | ✅ |
| A10 | Placeholder booking problems | Kneadly treats "WAITLIST HOLD" as a real client: messages, exports, late-cancel records; a placeholder left behind blocks a slot | No contact details on the placeholder; reports and "booked since" leave it out by its client ID; removed automatically when the opening closes; daily check | 🔮 |
| A11 | A gap while a placeholder becomes the client's booking | The API can only cancel and re-book | Change the client on the same booking if possible; otherwise book first or re-book straight away with a live read (§10.2) ❓ | 🔮 |
| A12 | A refill never reaches Kneadly | The "book at check-in" case is forgotten | The daily check lists every refill not in Kneadly yet | ✅ |
| A13 | Kneadly's state guessed from how the cancellation was heard | All 3 online rebookings in the sample were voicemail cancellations, yet free online overnight | Always read the slot (§9.5 rule 6) | 🔨 |

### B. Data from Kneadly (assumptions)

| # | Risk | Mitigation | Status |
|---|---|---|---|
| B1 | **No API, no change feed, no alerts** | Phase 1 works on uploads, desk taps and manual holds. The plan doesn't rely on any weekly or daily export | ❓ Julie |
| B2 | API fields or values differ from the CSV (status names, confirmation values, IDs, UTC times) | One adapter maps them; contract tests; **first real data run read-only, side by side with the uploads**, before trusting it | 🔮 |
| B3 | Higher plan ~$45/month (unchecked); with hosting, over $50 | Stay on the desk computer; Julie checks the price before Phase 3 | ❓ |
| B4 | **Missing booking history.** "Booked since" only sees bookings in the data. Tested Oct 30, run date Oct 30, using only the last 2 days of the sample export (visits Oct 16–17): wrong names on 35 of 44 openings, including 3 of the 4 inside those 2 days. Bob Gaudet, Steph Poirier, Claudette Richard and Jen LeBlanc look like they're still waiting. Hard-gate failure | The database keeps every booking ever synced (§4.3); gap warning; Phase 3: ask the API for a client's bookings since a date | 🔨 |
| B5 | Lag between checks (1–2 min, or longer if Kneadly limits calls) | Live reads at the four moments (§4.5); the hold | 🔮 |
| B6 | **Time zones and the clock change**: the CSV has local times with no zone, and an API may use UTC. Notice across **Nov 1, 2026** (Atlantic Daylight → Standard Time) is off by an hour. The notice filter could then offer someone who can't make it | Store times with the America/Moncton zone; test across the change | 🔨 |
| B7 | Where Kneadly stores data is unknown (PHIPAA, Marc's one-pager) | Ask Julie before Phase 3 | ❓ |
| B8 | Kneadly outage or rate limit | Platform works on its last data, with a banner: "Kneadly data from 10:12" | 🔮 |
| B9 | No phone number in the export, so people are matched to clients **by name** (the weakest link, technical plan §13 risk 2) | Nickname table, flag when unsure; Phase 3 matches by client phone if the API gives it | ✅ / 🔮 |
| B10 | The `status` of a booking that hasn't happened yet is unknown (the sample only has past visits) | The adapter maps it once known; until then the call list treats anything not completed or cancelled as booked | ❓ |
| B11 | The stand-in is built from **our guesses**, so it passes tests the real API might fail | Phase 2 results don't count as proof; the B2 side-by-side run decides | 🧪 |
| B12 | **A gap in the history**: a new file doesn't start where the last one ended (e.g. Friday's files after the sample ends on Oct 17) | Gap warning in the sync log and on every screen, naming the days; the desk checks Kneadly before calling. Not fully solvable from files: anyone who booked in the gap is invisible | 🔨 |
| B13 | Checks every 1–2 min exceed Kneadly's limits or slow the desk computer | Slow down outside opening hours; live reads only at the four moments | 🔮 ❓ |

### C. Bookings at risk and booking states

| # | Risk | Mitigation | Status |
|---|---|---|---|
| C1 | "At risk" treated as cancelled, so a booked slot gets offered (double booking) | At risk never creates an opening; no pre-matching; only a recorded cancellation moves a slot on | 🔨 |
| C2 | At-risk tracking costs effort but fills little. Unconfirmed predicts **no-shows** (7 of 8), not late cancellations (only 10 of 36 unconfirmed) | Keep it to the call list Tanya already makes; measure "Cancelled tap → filled" from the offer log before adding more | 🔨 |
| C3 | An automatically read message is misread ("running late" taken as "can't make it") | Suggested rows only; a person confirms | 🧪/🔮 |
| C4 | Reminder and confirmation **times** aren't in the export, so T−24 h is worked out from assumptions | State it on screen ("reminder assumed Sun"); use real times when the feed has them | 🔨 ❓ |
| C5 | Late vs normal cancel decided by when it was heard, not when it happened | Rule: `cancelled_at`; the inbox asks when they cancelled (for voicemail, the time it was left) | ✅ |
| C6 | The same cancellation heard twice becomes two openings | One row per `appointment_id`: the inbox says "already in the inbox" | ✅ |
| C10 | An inbox entry for a booking that isn't in the uploads relies on the desk typing the right Kneadly number | Same number → same row; a wrong number makes a second opening for the same slot, which the hold step (checking Kneadly) catches | 🔨 risk stays until the API |
| C7 | Desk too busy between 9:00 and 10:30 to tap | Same as today; the inbox keeps the rows so nothing is lost | — |
| C11 | The call list is only as fresh as the last appointments upload (someone who confirmed by text since still shows; a booking made since is missing) | Upload the day's file before 8:00; 🔮 the API, polled | 🔨 |
| C8 | Ranking clients by past no-shows feels like profiling | Off by default; desk-only; explainable signals; Marc decides | 🔨 |

### D. Health information and privacy

| # | Risk | Mitigation | Status |
|---|---|---|---|
| D1 | The uploaded waitlist file contains health text | Read in memory; file and note text never stored; privacy test scans the database | 🔨 |
| D2 | **An unknown health word is quoted.** Today `preprocess-report.txt` and `out/core/people.json` print `can't read 'shingles'`, because "shingles" isn't in the drop list (tested Oct 30 on a copy of the waitlist with one added line). On a desk screen, a client could read it | The platform never stores the word, so it can't be shown: the reason says "one word (see the book)" (✅ built Oct 30, tested). Add common terms to the drop list. **`run.py`, here and in the frozen reference folder, still prints the word:** port a fix there if wanted | ✅ fixed on the platform; `run.py` unchanged |
| D3 | A routing chip or rule name implies a condition ("Prenatal-trained only") on a desk screen | Chips shown only on the fill-in card and the Rules screen; openings show only therapist names; the label is a setting Marc decides | ✅ / ❓ wording |
| D4 | The prenatal tag is itself health information | Marc's decision (a) keep as a hidden routing tag or (b) don't keep it (technical plan §16) | ❓ |
| D5 | The rules editor invites storing conditions "in case" | People carry routing tags only; no condition field; no free text; the reason is never kept (tested) | ✅ |
| D6 | Voicemail-to-text or text reading = an outside service hearing health details | Suggested rows only; transcript not stored (channel + time only); Marc's one-pager | 🔮 |
| D7 | Names and phones visible on the desk screen | No health detail anywhere; screen placement; screen dims after inactivity | 🔨 |
| D8 | Hosting moves personal data off the desk computer | Stay local; if hosted, Marc's one-pager | 🔮 |
| D9 | Backups hold personal data | Clinic-owned, encrypted location ❓; no personal accounts | 🔨 |
| D10 | Shared desk computer: who did what | Per-person PINs for the audit log; `checked_by` never shown in output | 🔨 |

### E. Waitlist data: the migration and the board

| # | Risk | Mitigation | Status |
|---|---|---|---|
| E1 | **Two lists during the transition.** Bethany and the therapists keep writing in the book | Mode A rules (§6.3); one cut-over date for everyone, with the board-only switch (refuses book uploads) | ✅ / ❓ the date |
| E2 | A card edit is lost or misapplied when a new upload regroups people (e.g. a new number) | Edits attached to line numbers; a split → both halves held for review | 🔨 |
| E3 | Same-day tie between a notebook line (date only) and a card edit | As built, the line uploaded later wins; 🔨 a warning when the line's date is the edit's date | 🔨 |
| E4 | Duplicate cards | "+ Add" checks the phone first and shows the existing card (tested) | ✅ |
| E10 | A card edit counts as contact, so editing someone's card without talking to them restarts their 60-day clock | Edit a card when the client has called, as with a new line in the book; History shows every edit | — |
| E11 | Saving the whole card drops what the card doesn't show (a "pref" sort hint) | Only affects who is shown first, never who fits | — |
| E5 | Wrong file in the wrong box, or an old file uploaded | Column checks ✅; counts before saving; undo the last import | 🔨 |
| E6 | Tanya rewrites a page, so line numbers or text change | Changed old line → warning + held | 🔨 |
| E7 | The migration carries health details into the database | Only the fields matching and the desk need are migrated; note text and health words dropped; the privacy test scans the database | 🔨 |
| E8 | A changed old line can't be spotted without keeping its text | A fingerprint (one-way hash) per line, not the text | 🔨 |
| E9 | A line in Friday's book that isn't at the end (a line inserted) breaks "only new numbers are new" | Line numbers and fingerprints checked on every upload; any mismatch → warning, those people held | 🔨 |

### F. Rules and switches

| # | Risk | Mitigation | Status |
|---|---|---|---|
| F1 | A rule edit silently changes who is offered (e.g. a tag removed from Amira: pregnant clients get only Kelsey, or nobody) | Draft → check → before/after (with a warning if anyone would need a tag nobody has) → Marc's approval tick → versions + put back | ✅ |
| F2 | The tag change in the core breaks today's results | Checked: all outputs identical byte for byte (Oct 21 and Oct 30 runs); 44/44; all tests pass | ✅ |
| F9 | Removing or renaming a rule leaves lines saved earlier with the old tag | A rule's tag can't be renamed on the screen (a new tag is a new rule); a person needing a tag nobody has is warned about on the check page and is offered nothing (precision); the next upload of the book re-reads every line | ✅ / 🔨 a person stays routed until the next upload |
| F3 | Order changed without anyone knowing ("why didn't I get the call?") | Order shown on every opening; changes logged; Marc + Tanya decide | 🔨 |
| F4 | Settings in two places (database and `clinic.json`) drift | `clinic.json` stays the one file every run reads; the database only keeps the versions saved from the screen; an edit made outside the screen is pointed out on the settings screen | ✅ |
| F7 | A therapist removed from the settings is still named in lines saved earlier (found Oct 30: the matcher stopped with an error) | "any" is saved as "any"; a line naming a removed therapist holds that person for review; tested | ✅ fixed |
| F8 | The 212 tests are tied to the sample's settings: after a real settings change, some will fail even though nothing is wrong | The screen's before/after replaces "run the tests" for everyday changes; the tests stay for code changes, on the sample settings | — |
| F5 | A new *kind* of rule needs a developer | Expected 0–2 times a year; budgeted at $90–120/h | — |
| F6 | Amira's and Rachel's approval is assumed `none` | Open question for Marc; it only adds a flag, never removes a name | ❓ |

### G. Review queue

| # | Risk | Mitigation | Status |
|---|---|---|---|
| G1 | Held people pile up, so openings get fewer names | Count on every screen; drift alarm at ~10%; Julie's monthly check | 🔨 |
| G2 | A wrong "same person" decision puts one person's limits on another (wrong name) | Both lines side by side; decision logged and reversible | 🔨 |
| G3 | Pressure to clear the queue by guessing | No "release all"; each release is one person's decision | 🔨 |

### H. Adoption and usability

| # | Risk | Mitigation | Status |
|---|---|---|---|
| H1 | **Tanya won't use it**: more taps than the book, no time between clients | Timing test with the real board (built Oct 30) before the book is retired; one screen; one tap per outcome; the book stays as a fallback | ❓ Tanya |
| H2 | Therapists feel it's taken out of their hands | "Ask Josée first" stays; no booking without the desk; a therapist view later ❓ | 🔨 |
| H3 | Bethany on Saturdays doesn't know the clients | Reasons on every name; same screens | 🔨 |
| H4 | Overnight cancellations still can't be acted on before 8:00, or before 10:30 for the waitlist | Value depends on "Cancelled tap → names" during the 8:00–9:15 calls, and on moving the calls (technical plan §12). Faster data alone doesn't fix it (technical plan §13 risk 1) | — |
| H5 | Offers made outside the platform aren't logged, so anti-pestering and the numbers are wrong | Desk rule; the "Offer" button is one tap (the desk name is remembered) | ✅ |
| H6 | **No limit on calls per person yet.** The weekly limit is 0 (off) until Marc picks a number, so someone who fits many openings can be called several times a week | The setting and the "Resting this week" box are built and tested; Marc's number turns it on (§16 Marc 3) | ✅ / ❓ Marc |
| H7 | A resting person comes back on the openings only at the next match, not at the exact minute their week ends | Any upload or desk action matches again; until then they're missing from names (fewer names, never a wrong one) | 🔨 |
| H8 | The desk skips the "why" or picks a reason at random, so the monthly check reads too much into a few taps | The why is optional; the report shows counts, not conclusions; Julie and Marc read it together | 🔨 |

### I. Running it

| # | Risk | Mitigation | Status |
|---|---|---|---|
| I1 | More to look after than a script, so Julie's ~1 h/month is at risk | Starts automatically; health page; nightly backup; the command line as a fallback | 🔨 |
| I2 | Desk computer off or broken | Pause → notebook; restore from backup | 🔨 |
| I3 | Kneadly changes its export or API | Adapter stops with a clear message (✅ for CSV); a developer fixes the adapter only | ✅ / 🔮 |
| I4 | Phase 2/3 need a developer | Phase 1 is useful without them | — |
| I5 | Two browser tabs or two users change the same thing | Database locks; last change shown with who made it | 🔨 |

### J. Testing and overfitting

| # | Risk | Mitigation | Status |
|---|---|---|---|
| J1 | Tuned to 44 openings and 60 lines | The technical plan §9 guard: no per-person rules, facts in settings, fail safe, unseen test sets; every real week and every `mistakes` row become tests | ✅ / 🔨 |
| J2 | Simulated events (Phase 2) don't match real timing | Build fixtures from the sample's real `cancelled_at` times and channels; check against real data in Phase 3 | 🧪 |

---

## 16. Open questions (logged, not guessed)

**Julie (booking account)**
1. Does Kneadly have an API? Read only, or can it create bookings? Is there a change feed or webhooks? How often may it be called? Is the higher plan needed, and what does it really cost?
2. Does Kneadly alert on cancellations? Does it expose text replies to the reminder?
3. Can the API read **one slot right now**, and return a **client's bookings made after a given date**?
4. What `status` does a booking that hasn't happened yet show? Are the reminder-sent and confirmation times available?
5. Can the export or API include the client's **phone number**?
6. Holds (by hand: yes; built-in hold: no): can the API **block time**? If not, can it book a clinic-owned placeholder client? Can it **change the client** on an existing booking? Does Kneadly accept two bookings in one slot, even for a moment?
7. Does a booking or block created or removed by the API make Kneadly send a message? Can that be turned off per booking? What does it say?
8. The 3 voicemail cancellations that were rebooked online overnight (O04, O12, O44): how did those slots become free online? Did the clients also cancel online, or did someone record them?
9. Where does Kneadly store the data? Which browser does the desk use?

**Marc (owner)**
1. May the platform place holds and write bookings in Kneadly (§10.4–10.5)? Is a "WAITLIST HOLD" placeholder client acceptable?
2. Prenatal tag: keep it as a hidden routing tag (a) or don't keep it (b)? How should routing chips be worded?
3. Who approves rule and order changes? **Max offers per person per week?** The setting is built and set to 0 (no limit) until Marc picks a number (e.g. 2).
4. How long are offers, events and taken-off people kept? Where do backups go?
5. Amira's and Rachel's say over their table (`none` is assumed).
6. Should the call list rank by risk signals (past no-shows), or stay by start time?

**Tanya (desk)**
1. The timing test: the book vs a spreadsheet vs a paper board (15 min).
2. When a 45-min person takes a 60-min opening, which length is booked?
3. Is ~20 min still the right wait after a voicemail?
4. Does the phone show the time a voicemail was left?
5. A cut-over date for retiring the notebook, agreed with Bethany and the therapists.
6. Which case in §10.3 fits each kind of refill? Is blocking the time by hand before the first call workable at a busy desk?

**Program lead (demo)**
1. What period does Friday's booking file cover, and does it continue from the sample (which ends Oct 17)?

---

## 17. Sources

- [technical-build-plan.md](technical-build-plan.md): §1 design rule, §4 core data, §6 matching and switches, §7.2 rebooking loop, §7.3 flags, §8 slot lifecycle, §11 future platform (11.2 board, 11.3 Kneadly options, 11.4 interfaces, 11.5 call outcome, 11.6 inbox, 11.7 feedback), §12, §13 risks, §14 build order, §16 health information.
- [project-guidelines.md](project-guidelines.md): done checks, scoring, hard bans, what not to build.
- [handover-plan.md](handover-plan.md): owner, cost, what happens when it's wrong.
- [discovery-notes.md](discovery-notes.md), [interview-tanya-boudreau-2026-10-22.md](interview-tanya-boudreau-2026-10-22.md), [follow-up-answers-oct-29.md](follow-up-answers-oct-29.md): what Tanya, Marc and Julie said.
- [step2-csv-facts.md](step2-csv-facts.md), [step3-combined-facts.md](step3-combined-facts.md), and the sample CSV files: the numbers in §9.2. Confirmation counts were rechecked from `late-openings-2026-09-21-to-2026-10-17.csv` on Oct 30. Technical plan §8 and §12 say "24 of the 44 late openings had confirmed"; that counts text confirmations only. Counting text and phone confirmations among the 36 late cancellations gives 26.
- Code in this folder (`kettle/`, `config/clinic.json`, `run.py`): what is built. Checked Oct 30: `python -m pytest` → 148 passed.
