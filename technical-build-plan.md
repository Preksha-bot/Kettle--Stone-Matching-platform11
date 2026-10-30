# Technical build plan: Kettle & Stone waitlist matcher

How the solution is built: what it is now (CSV files in, names out) and what it would become later (a small platform connected to the booking system). Rules and constraints are in [project-guidelines.md](project-guidelines.md); this file is about the build.

**Status markers used below**
- ✅ **Decided**: build it this way.
- 🟡 **Partly decided**: direction is clear, details need your call in [§3 Discussion](#3-discussion-decide-these-before-preprocessing).
- ❓ **Unknown**: depends on facts nobody has yet (mostly Julie and Kneadly). Plan for it, don't build it now.

> Note on names: the clinic's booking system is **Kneadly**, not Calendly.

> **Oct 30 review:** your 15 ❓❓ notes are answered in [§15](#15-review-of-your--notes-oct-30) and folded into each section. Where health information may go is in [§16](#16-health-information-where-it-may-and-may-not-go), and how flags work today is in [§7.3](#73-flags-how-theyre-handled-now--built-one-gap-planned). The resulting changes are in [§14 step 8](#14-build-order): **P1 built Oct 30** (health words, settings check), plus the P2 release of held people (`start over`, `reviewed.csv`); the rest of P2 and P3 planned, not built.

---

## 1. The idea in one picture

```
            PRESENT (Friday demo)                          FUTURE (platform)
  ┌───────────────────────────────────┐        ┌──────────────────────────────────────┐
  │ waitlist.csv  (handwritten notes) │        │ Waitlist board (editable cards)      │
  │ appointments.csv (weekly export)  │        │ Kneadly feed, ideally every 30 min   │
  │ late-openings.csv                 │        │ Desk one-tap "cancellation" entry    │
  └────────────────┬──────────────────┘        └──────────────────┬───────────────────┘
                   │ CSV adapter                                  │ platform adapters
                   │ (clean + parse notes)                        │ (no parsing needed)
                   ▼                                              ▼
            ┌───────────────────────── CORE DATA ─────────────────────────┐
            │  openings · waitlist people · bookings (reference only)     │
            └────────────────────────────┬────────────────────────────────┘
                                         ▼
                              ┌──────────────────────┐
                              │   CORE MATCHER       │  same code in both worlds
                              │ filters → order → 3  │
                              └──────────┬───────────┘
                                         ▼
                   Up to 3 names + reasons per opening (or "nobody")
                                         ▼
           Desk offers #1 → #2 → #3 → re-run for more → slot filled or expires
           (rebooking stays manual in Kneadly; nothing is sent automatically)
```

**The main design rule ✅:** the **core data** and the **core matcher** are the same in both worlds. Only the **adapters** change: the CSV adapter today, platform adapters later. So everything built for Friday carries over to the platform. The matcher never knows where its data came from.

---

## 2. Your ideas, organised

| # | Your idea | Where it lands | Status |
|---|---|---|---|
| 1 | Weekly (at best daily) CSVs are too slow, because late cancellations happen within 24 hours | §11 Future platform: Kneadly feed every ~30 min. See the caveat in §13 | ❓ |
| 2 | Two input-output systems: present CSVs and a future platform | §1: one core, two sets of adapters | ✅ |
| 3 | Preprocess CSVs into core data; find which columns matter | §4 Core data, §5 Preprocessing | ✅ |
| 4 | Parse the free-text waitlist notes by script or AI | §5.3: script first, AI only as an optional helper | 🟡 |
| 5 | Matching rules: timing, customer preferences, health routing, therapist, day, notice, therapist's say, first come first served, regulars (later) | §6 Matching rules | ✅ |
| 6 | Matching leads to rebooking; if it fails, use the other names, then re-match | §7 Output and the rebooking loop | ✅ |
| 7 | Future: replace the notebook with something digital with fixed fields. **Your note (Oct 30):** a list of editable cards fits better than a form | §11.2 The waitlist board (editable cards), see [§15 #1](#15-review-of-your--notes-oct-30) | 🟡 design changed; test with Tanya |
| 8 | Unsure how core, platform, Kneadly and rebooking connect | §11.4 Interfaces | ❓ → plan given |
| 9 | Unsure when a slot actually counts as a late cancellation | §8 Slot lifecycle | 🟡 → plan given |
| 10 | Tests for preprocessing and matching; platform tests later | §9 Tests | ✅ |
| 11 | Friday demo runs on present-style inputs | §10 Friday runbook | ✅ |
| 12 | Discuss data discrepancies before preprocessing | §3 Discussion | ✅ decided Oct 30 |
| 13 | Reduce Tanya's morning confirmation calls, with no automatic calling or emailing | **Call outcome → instant match** and **one cancellation inbox** are now part of the platform plan (§11.5, §11.6). Other ideas stay optional (§12) | ✅ (design only) |

---

## 3. Discussion: decisions before preprocessing

**Decided on Oct 30, 2026.** All 3B recommendations and A2–A8 accepted as written. A1 changed: identify people by **phone and name together** (§5.1 step 4). These decisions are now the preprocessing and matching settings in `config/clinic.json`.

### 3A. Data discrepancies (the files themselves)

| # | Discrepancy | What the data shows | Recommendation | Your decision |
|---|---|---|---|---|
| A1 | **Waitlist has no client ID**; one person can have several lines | Same person appears as `Lynn Savoie` / `Lynn S.`, `Amanda Bourgeois` / `Amanda B.`, `Tina Saulnier` / `Tina S` | Use the **normalised phone number** (digits only) as the person key. Name is display only. | ✅ **Phone + name together** (see §5.1 step 4). |
| A2 | **Phone written as `same #`** (lines 7, 31) | Line 7 `Lynn S., same #` = line 5 Lynn Savoie. Line 31 `Claudette R, same #` = line 9 Claudette Richard | Resolve `same #` to the **nearest earlier line whose first name matches and last name starts with the given initial**. If none or more than one match, flag the line and don't offer it. | ✅ As recommended |
| A3 | **Phone formats differ** | `506-555-0101`, `506 555 0102`, `(506) 555-0103`, `5065550105`, `(506)555-0113` | Strip to 10 digits. Anything else → flag. | ✅ As recommended |
| A4 | **Waitlist dates have no year and mixed formats** | `Jul 6`, `7/14`, `Sept 1`, `10/19` | Parse all formats; year = run date's year; if that lands after the run date, use the year before. | ✅ As recommended |
| A5 | **Booking export has no phone number**, so waitlist people can only be matched to bookings by name | `Mel Arsenault` → `Melanie Arsenault`, `Bob Gaudet` → `Robert Gaudet`, `Jen LeBlanc` → `Jennifer Leblanc`, `Steph Poirier` → `Stephanie Poirier` | Match on last name + first name, with accents removed and a **small nickname table** (Bob/Robert, Mel/Melanie, Jen/Jennifer, Steph/Stephanie, …). If two clients could match, flag rather than guess. | ✅ As recommended |
| A6 | **Accents differ between files** | Waitlist `Joel Bertin`, `Terry Hebert`; answer key `Joël Bertin`, `Terry Hébert` | Remove accents and lowercase for all comparisons; display the waitlist spelling. | ✅ As recommended |
| A7 | **Answer key refers to lines as `W39`** | `W39` = waitlist `line` 39 | Use the line number as the line ID everywhere (Tanya only adds to the end, so numbers are stable). | ✅ As recommended |
| A8 | **Late-openings file duplicates part of the export** | Each opening's `appointment_id` is a `Late cancel` / `No-show` row in appointments | Use the openings file as input for Friday; cross-check against the export and warn on mismatch. In the future, openings come from Kneadly directly. | ✅ As recommended |

### 3B. Rule interpretations (open in the guidelines)

| # | Question | What the data shows | Recommendation | Your decision |
|---|---|---|---|---|
| B1 | **Notice counted from when?** Cancellation time, run time, or ~10:30 when the desk can act? | Answer key follows the file's `hours_notice` (cancellation → start). O01 has 2.7 h notice: Lise (needs 2 h) ✓, Chantal (needs 3 h) ✗. O31 says "1h 14m notice". The 10:30 desk limit is **not** applied (O15 at 09:00 is offered) | **Friday:** use `hours_notice` from the cancellation time. **Future:** use the time an offer can actually go out (a config switch). | ✅ As recommended |
| B2 | **Post-op "usually Josée"**: filter or preference? | Line 16 Carole (hip replacement) "Josée" → line 48 "Jos or Rachel ok now" → key: **Josée or Rachel** | **Not a filter.** Follow what's written on the person's line; don't derive a therapist from surgery words. | ✅ As recommended |
| B3 | **"Two months"**: calendar months or 60 days? | No difference on the sample (both make lines up to Aug 15 stale on Oct 21) | **60 days** from the person's **newest line** (simpler to explain). ⚠ On a **Friday Oct 30** run, late-August lines (line 10 Sarah Aug 24, line 12 Denis Aug 26, line 14 Chantal Aug 29) turn stale under either rule. | ✅ As recommended |
| B4 | **Opening length vs requested length** | A 60 person is offered a 90 opening (O03: Sarah, Patrick…). A 30/45 person is offered a 60 opening (O01: Joël). A 45 person is **not** offered a 30 opening (O13) | Fits if **requested length ≤ opening length**. Exception: `90 only` means the opening must be 90. | ✅ As recommended |
| B5 | **Time words** | Mornings: O05 at 11:45 counts, O20 at 12:00 doesn't. Afternoons: 12:00 and 17:45 both count (Lise). "after 5" = starts 5:00 or later (key) | Mornings = start **before 12:00**; afternoons = **12:00 or later**; evenings = **18:00 or later**; `after N` = start ≥ N (1–7 read as p.m.); `not before N` = start ≥ N; `done by N` = end ≤ N; `lunch 12-1` = whole visit within 12:00–13:00. | ✅ As recommended |
| B6 | **Newest line vs older lines** for one person | Line 43 Tina "done by 2:30" keeps "Kelsey or Amira, 1hr" from line 30. Line 48 Carole changes therapist, keeps 60. Line 60 Mireille "add: not Thurs" adds to line 44 | **Newer line overrides only the fields it mentions; everything else carries over.** | ✅ As recommended |
| B7 | **"Booked since" = stale** | Mel, Bob, Jen, Steph, Claudette all booked **after** their newest line. Marcel Bujold booked Aug 22, **before** his Sep 2 line → still active | Stale if a **non-cancelled booking was made (`booked_at`) after the person's newest line**. ⚠ A regular wanting an *extra* visit who books his usual next visit would wrongly turn stale. Flag lines with `reg` / `extra` for review instead of auto-removing. | ✅ As recommended |
| B8 | **"Female only"** | Key treats Josée, Amira, Kelsey, Rachel as fitting; Marc and Dave not | Put therapist attributes in a **config table**, not in the code. | ✅ As recommended |
| B9 | **Pregnancy rule** | `pregnant … female` (line 10) and `pregnant … Amira pref` (line 40) both → **Amira or Kelsey**. "Rachel doesn't take prenatal clients" | Pregnancy → **prenatal-trained only** (config: Amira, Kelsey), always overriding "any". | ✅ As recommended |
| B10 | **"pref"** (e.g. `Amira pref`) | Only case is line 40, where the pregnancy rule overrides it anyway | Treat `pref` as a **sort hint, not a filter**. Revisit if Friday shows otherwise. | ✅ As recommended |
| B11 | **"Next day only" / "told the day before"** | Line 55 Sylvie is offered O05 (Wed, cancelled Tue 23:22), not O34 (cancelled the same morning) | Fits only if the cancellation came on an **earlier calendar day** than the opening. | ✅ As recommended |
| B12 | **Default notice / length** when not written | O13, O31, O40 (~1.2 h notice) only go to people who said 30 min or 1 h | Default notice **2 h**; default length **60**. `quick` / `can come in 30 min` = 0.5 h; `same day ok` = 2 h (default). | ✅ As recommended |
| B13 | **Unclear or unknown shorthand** | Friday lines are new | **Don't offer** a line with an unparsed restriction; list it under "needs review". Precision beats recall (see guidelines). | ✅ As recommended |
| B14 | **First come, first served**: by which date? | Key lists names in line order; order isn't scored | Priority date = the person's **earliest line** ("they asked first"); ties by line number. Other orders as switchable options (§6.3). | ✅ As recommended |
| B15 | **New clients** (`NEW client`, no profile) | Line 37 Greg is offered O33 (Dave) | Offer them; mark "new client, phone only" (no text consent). For therapists set to "see first" (Josée), mark "ask Josée first". | ✅ As recommended |
| B16 | **Regulars first** (Marc) | Only line 18 says `Marc's reg`; the export can count visits | **Off for Friday.** Build as an option: regular = written `reg`, or ≥ N completed visits with that therapist in the export. N = your call. | ✅ As recommended |

---

## 4. Core data

Keep it small. Only what matching needs, plus what the future platform will produce directly.

### 4.1 Core tables ✅

**`openings`**: one row per late opening
| Field | Example | Notes |
|---|---|---|
| `opening_id` | O01 | From file; future: = Kneadly appointment ID |
| `appointment_id` | A-24010 | Unique key, stops one cancellation being processed twice |
| `therapist` | Josée Landry | |
| `date`, `day`, `start`, `length_min` | 2026-09-21, Mon, 12:30, 60 | `end` derived |
| `kind` | late cancel / no-show | No-shows → always "nobody" |
| `cancelled_at` | 2026-09-21 09:47 | |
| `hours_notice` | 2.7 | Derived if missing: start − cancelled_at |
| `status` | open / offering / filled / expired | Future only |

**`people`**: one row per waitlist **person** (lines merged)
| Field | Example | Notes |
|---|---|---|
| `person_id` | P-5065550125 | From normalised phone |
| `display_name`, `phone` | Amanda Bourgeois, 5065550125 | |
| `line_ids`, `active_line` | [26, 42], 42 | Audit trail back to the notebook |
| `first_asked`, `last_contact` | 2026-09-11, 2026-09-30 | For ordering and staleness |
| `therapists_allowed` / `therapists_excluded` | {Rachel, Josée} / {} | `any` = all |
| `needs` (planned; replaces `female_only`, `prenatal_only`) | {} or {"prenatal-trained"} | One general field: the therapist **tags** this person needs. Tags and the words that set them live in config, so a new clinic rule is a settings change, not code. Never shown on screen; never the reason itself ([§15 #2](#15-review-of-your--notes-oct-30)) |
| `lengths_ok`, `length_exact` | {60}, false | `90 only` → exact |
| `days_ok` | {Mon…Sat} | |
| `earliest_start`, `latest_start`, `latest_end` | 15:30, –, 14:30 | |
| `min_notice_h`, `needs_day_before` | 2.0, false | |
| `available_from`, `available_until` | 2026-10-10, – | `til Oct 9`, `here til Oct 10`, `before wedding Oct 3` |
| `contact_pref`, `is_client` | text only, true | Text only for existing clients (consent lives in Kneadly) |
| `status`, `status_reason` | stale, "booked Oct 2 (Robert Gaudet)" | active / stale / needs-review |
| `parse_flags` | ["unparsed: 'ins ok's it'"] | Anything not understood |
| ~~`health_note`~~ 🔒 | (none) | **Not kept at all** (built Oct 30). Health text is dropped while parsing; the notebook remains the only copy. Only `prenatal_only` survives as a routing flag |

**`bookings`** (reference only): from the export, used for "booked since", regulars, and later therapist schedules.
`appointment_id, date, start, end, length_min, therapist, client_id, client_name, booked_at, status, cancelled_at, rebooked_into`

**`config`** : one editable file, no rules hard-coded: therapists (short forms, female, prenatal-trained, approval mode), defaults (notice 2 h, length 60, stale 60 days), time-word definitions, nickname table, ordering mode, max names = 3. The six therapists are confirmed: they're the six in the discovery notes and the only six in the export. Facts about the clinic in a settings file aren't overfitting. A therapist who isn't in the file means a warning, and that opening gets nobody ([§15 #3](#15-review-of-your--notes-oct-30)). Working days aren't needed: each opening already names the therapist and the time. Planned: a settings check that stops on a short form used by two therapists.

### 4.2 Which CSV columns matter ✅

| File | Keep for matching | Keep for reporting only | Drop |
|---|---|---|---|
| **appointments** | `appointment_id, date, start, end, length_min, therapist, client_id, client_name, booked_at, status, cancelled_at` | `rebooked_into, desk_notes` (refill check: "filled from waitlist"), `confirmation, cancel_via` (optional §12); **platform:** `booked_via`, which spots a slot taken online while the desk is offering it, and shows how slots get refilled ([§15 #4](#15-review-of-your--notes-oct-30)) | `service` (repeats length), `late_fee`; `booked_via` for the CSV version |
| **late-openings** | `opening_id, appointment_id, date, day, start, length_min, therapist, kind, cancelled_at, hours_notice` | `heard_via, client_had_confirmed, booked_value_cad` | `refilled, refilled_how`: what actually happened. It **must never feed the matcher for that same opening** (leakage). In the platform, outcomes come back through the feedback loop: reports, offer limits, new test cases, always through a person ([§11.7](#117-feedback-loop--design-only), [§15 #5](#15-review-of-your--notes-oct-30)) |
| **waitlist** | all: `line, added, name, phone, notes` | | |
| **answer key** | **tests only**, never read by the matcher | | |

---

## 5. Preprocessing (CSV adapter)

### 5.1 Pipeline ✅
1. **Load** the three input CSVs (UTF-8). Check the expected columns exist; stop with a clear message if not.
2. **Normalise**: phones → digits; dates → ISO with year (A4); names → accent-free lowercase key (A6); times → 24 h.
3. **Parse each waitlist note** into fields (§5.3). Health words are dropped; only the prenatal routing survives. ✅ Fixed Oct 30 ([§15 #7](#15-review-of-your--notes-oct-30)): the pieces beside a health word, and anything in brackets, are read when they hold a scheduling word; a piece mixing both holds the person for review, with a reason that doesn't quote the note.
4. **Group lines into people using phone and name together** (A1, decided): ✅
   - **Same person** if the normalised **phone matches**, or if the line says `same #` (A2).
   - **Name check** on every pair: names are compatible when the **first name matches** and the last name matches or is **its initial** (`Lynn Savoie` ↔ `Lynn S.`, `Amanda Bourgeois` ↔ `Amanda B.`, `Tina S` ↔ `Tina Saulnier`), or the full **last name matches** with a nickname/short first name (`Jen LeBlanc` ↔ `Jennifer Leblanc`, `Normand V` ↔ `Normand Vienneau`).
   - **Phone matches + names compatible** → merge.
   - **Phone matches + names clearly different** (e.g. a parent's number shared by a child) → don't merge; flag both for review.
   - **Names compatible + phones differ** (new number?) → don't merge automatically; flag both for review and don't offer them until checked. A wrong merge could carry one person's limits onto another, so precision wins here.
5. **Merge each person's lines**, oldest to newest; newer overrides only the fields it mentions (B6).
6. **Mark stale** (each with a reason): newest line older than 60 days (B3); booked since (B7, uses A5 name matching); explicit signals (`moved`, `not in service`, `take off`, `going to someone … now`); `available_until` before the run date.
7. **Write core data** (`core/people.json`, `core/openings.csv`) plus a **preprocessing report**: stale people with reasons, merged groups, flagged lines.

### 5.2 Script or AI for the notes? 🟡 → recommend script
| | Script (rules + vocabulary) | AI service |
|---|---|---|
| Repeatable for the demo | ✅ same output every run | ❌ can vary between runs |
| Testable line by line | ✅ | partly |
| Health data leaves the desk computer | ✅ never | ❌ yes, needs Marc's one-pager |
| Cost | $0 | a few cents/month, but a new outside service |
| Handles brand-new shorthand | ❌ flags it | ✅ better |

**Recommendation:** a **script** for Friday and for the platform's import of old notebook data. When the script meets an unknown phrase it **flags the line** (B13); it never guesses. An AI helper is optional and offline: it suggests a parse for flagged lines, a person accepts or rejects it, and health words are removed before anything is sent. In the future platform the waitlist board makes parsing unnecessary (§11.2).

### 5.3 Vocabulary the parser must understand (from the 60 sample lines)
**New phrasing (tested Oct 30, [§15 #6](#15-review-of-your--notes-oct-30)):**
- New combinations of known words are read correctly.
- New words hold that person for review; they're never guessed.
- **Decided Oct 30:** no phrase book. The report keeps a **log of unknown words** with counts, and the platform's waitlist board (fixed fields, §11.2) removes free-text shorthand for new entries. The parser is then only needed until the board replaces the notebook, and once to import the old notebook.

| Field | Phrases seen |
|---|---|
| Therapist | `any`, `J only`, `Jos`, `Josée`, `Dave only`, `Amira`, `R/J`, `Josée or Rachel`, `Marc or Dave`, `AB Dave`, `anyone but Dave`, `any but Dave`, `not Marc (neighbour)`, `female`, `female only`, `any female`, `Amira pref`, `Marc only` |
| Length | `90`, `1hr`, `60`, `45`, `30 or 45`, `45 or 60`, `90 only`, `90 or 60 fine`, `wants 90 if poss, 60 ok`, `can do 90 if ins ok's it` (→ 60) |
| Day | `Mon`, `Tues/Thurs`, `Wed or Fri`, `Mon or Wed`, `Mon/Tues`, `not Thurs`, `not Mon`, `not Fri`, `not Sat`, `Sat only`, `Fri only`, `wkdays` |
| Time | `AM`, `mornings`, `afternoons`, `evenings after 6`, `after 5`, `after 3:30`, `after 4`, `not before 10`, `lunch`, `on his lunch 12-1 only`, `has to be done by 2:30` |
| Notice | `can come in 30 min`, `30 min notice ok`, `can come quick`, `same day ok`, `can come in an hour`, `can come in 2 hrs`, `needs 3h`, `needs 2-3 hrs` (→ 3, key), `needs 4 hrs`, `next day only` |
| Availability dates | `only til end of Sept`, `away hunting til Oct 9`, `back now`, `here til Oct 10`, `wants one before wedding Oct 3`, `wedding is Sat the 3rd` |
| Gone signals | `moved to Hfx??`, `# not in service??`, `going to someone in Dieppe now, take off` |
| Repeat markers | `again`, `called again`, `called back`, `still`, `still waiting`, `sorry, add:`, `same #`, `ok now` |
| Contact | `landline`, `TEXT don't call`, `text only` |
| Client status | `NEW client (intake form)`, `Marc's reg, wants an extra` |
| Health 🔒 (dropped; therapists get health details from the intake form and treatment notes in Kneadly, not from the waitlist: [§15 #7](#15-review-of-your--notes-oct-30)) | `sciatica`, `low back`, `knee replacement`, `hip replacement`, `post-op shoulder (rotator cuff …)`, `pregnant, 2nd tri`, `pregnant 30 wks`, `fibro`, `light pressure`, `MVA claim, ins pays`, `TMJ`, `migraines`, `concussion (MVA), light only`, `cancer survivor, no deep`, `hockey, hamstring` |
| Ignore (context) | `retired`, `works at the bank…`, `drives in from Shediac`, `(work)`, `(2 kids)`, `(shift work)`, `(school pickup)` |

Only **pregnancy** turns into a matching rule (→ prenatal-trained therapists). All other health words are **dropped and don't affect matching** (B2).

**If the clinic adds another rule later** (e.g. "post-op only with therapists trained for it"), it shouldn't need a developer. Planned ([§15 #8](#15-review-of-your--notes-oct-30)):
- Therapist **tags** plus **routing words** in config.
- A settings check.
- A before/after report.
- A short checklist for Julie.

A new *kind* of rule (e.g. "not the same therapist as last time") still needs a developer.

---

## 6. Matching rules (core matcher)

A plain function, so it's easy to test and reuse:
```
match(opening, people, bookings, run_at, config) -> { names: [≤3], excluded: [...with reasons] }
```

### 6.1 Hard filters (all must pass) ✅
1. Opening is **not a no-show** (no-show → nobody).
2. Person is **active** (not stale, not duplicate, not needs-review).
3. Opening date is within `available_from` … `available_until`.
4. **Therapist**: in allowed set, not excluded; `female_only` → female therapist; `prenatal_only` → prenatal-trained therapist (B8, B9).
5. **Length**: requested ≤ opening length; `length_exact` → equal (B4).
6. **Day** in `days_ok`.
7. **Time window**: start/end within the person's window (B5).
8. **Notice**: `hours_notice ≥ min_notice_h`; `needs_day_before` → cancelled on an earlier day (B1, B11, B12).
9. **Not already declined** this opening (future: offer log).

### 6.2 Soft signals (sort only, never exclude)
`pref` therapist (B10), regulars (B16, off for Friday). (The earlier idea of a "parse confidence" score is dropped: a line is either fully read or held for review, so there's no half-sure person to rank lower. [§15 #9](#15-review-of-your--notes-oct-30))

### 6.3 Order and pick 3 ✅
- Default **first asked** (B14). The order is a **switch**: a setting changed without touching code, either `--order …` on the command line or `"order"` in `config/clinic.json`. That lets Tanya see each order side by side, as she asked: `first-asked` · `shortest-notice` (can get here fastest) · `regulars-first`.
- The order changes **which 3 of the people who fit are shown first, never who fits.** With 15 who fit, first-asked and regulars-first can show different 3s. It's not the only switch; all of them are in §6.5.
- Show **max 3**. Any 3 who fit count as a match, so the order matters for fairness and explaining to clients, not for the demo score.
- Show **fewer than 3** rather than include anyone with a parse flag. If any part of a person's notes couldn't be read, they're held for review and left out, even if that leaves the opening with 1–2 names or nobody. They're listed in `preprocess-report.txt` for the desk to fix ([§15 #11](#15-review-of-your--notes-oct-30), §7.3).

### 6.4 Therapist's say ✅ (3 therapists unconfirmed)
Config per therapist: `approval: none | see_first`. It never blocks the list; it only adds a flag to the name ("ask Josée first").

| Therapist | Setting | Evidence |
|---|---|---|
| Josée | `see_first` | "Josée wants to see who it is" (Tanya); Marc: a brand-new client with a complicated history at an hour's notice |
| Kelsey, Dave | `none` | "Kelsey and Dave will take anyone"; Dave: "just send them" |
| Marc | `none` | Marc: "Just fill it. I don't care who." |
| **Amira, Rachel** | `none` **(assumed)** | Nothing on record. **Open question for Marc:** ask both |

Assuming `none` is safe for the score, because approval never changes who is shown. The worst case is booking without asking. Planned option: a narrower setting `see_first: new clients or under N hours' notice`, which is Josée's actual concern, so Tanya doesn't ask about every booking ([§15 #12](#15-review-of-your--notes-oct-30)).

### 6.5 Switches (settings you can change without code) ✅ built
| Where | Switch | Does what |
|---|---|---|
| Command line | `--run-date` | Day to count from (staleness, dates) |
| Command line | `--order first-asked \| shortest-notice \| regulars-first` | Order of people who fit (which 3 come first) |
| Command line | `--declined O12:39,42` | Skip people who said no to that opening; re-run for the next names |
| Command line | `--waitlist`, `--appointments`, `--openings`, `--out` | File names and output folder |
| `config/clinic.json` | `max_names`, `length_min`, `notice_hours`, `stale_after_days`, `order`, `regular_min_visits` | Defaults |
| `config/clinic.json` | `mornings_before`, `afternoons_from`, `evenings_from`, `lunch_from/until`, `quick_notice_hours` | What the time words mean |
| `config/clinic.json` | per therapist: short forms, `female`, `prenatal_trained`, `approval` | Who can take whom |
| `config/clinic.json` | `nicknames` | Matching waitlist names to the export |

Not built yet: B1's switch "count notice from when an offer can go out" (platform), and the planned therapist tags.

---

## 7. Output and the rebooking loop

### 7.1 Output per opening ✅
Readable in ~10 seconds by someone who doesn't know the clients (Bethany test):
```
O01  Mon Sep 21 12:30 · Josée · 60 min · 2.7 h notice
  1. Joël Bertin      506-555-0135  line 39  any therapist · 30 min at lunch · 30 min notice   [ask Josée first]
  2. Amanda Bourgeois 506-555-0125  line 42  Rachel or Josée · 1 h                             [ask Josée first]
  3. Nicole Vautour   506-555-0139  line 45  Josée or Amira · 1 h · not Fri                    [ask Josée first]
  Closest not offered: Pauline Bastarache (mornings only) · Lynn Savoie (stale: 2+ months) · Ray Daigle (stale)
```
No health words anywhere, including the pregnancy reason (shown only as "Amira or Kelsey").
Files: `out/matches.csv` (for scoring), `out/matches.txt` (for reading), `out/preprocess-report.txt`.

### 7.2 Rebooking loop (desk process; logging is future) ✅
1. Desk offers **#1** (one at a time, never two at once, to avoid two yeses).
2. **Yes** → desk books it in Kneadly and links "rebooked into". Opening = filled.
3. **No / no answer after ~20 min** (Tanya's current wait) → **#2**, then **#3**.
4. All three fail → **re-run** with those three excluded and notice recalculated from now → next names.
5. Stop when nobody left can meet their notice → opening = expired.
6. **Anti-pestering** (future): cap offers per person (e.g. 2 a week, your call), and never re-offer a slot someone declined.

Present version: steps 1–5 are a written desk procedure. The tool supports step 4 with the `--declined` option.

### 7.3 Flags: how they're handled now ✅ built (one gap planned)

There are three kinds. Only the first changes who is offered.

**1. Holding flags: the person is held for review and never offered.**

| Flag | Raised when | Where the desk sees it |
|---|---|---|
| Can't read part of a note | Any word left over after parsing (`"can't read 'weekends'"`) | `preprocess-report.txt` → HELD FOR REVIEW; `line-verdicts.csv` = review; "not offered" line in `matches.txt` |
| Identity mix-up | Same phone under another name; same name and initial with a different phone; `same #` with no earlier matching line; phone that can't be read | Same places, on **every** line of both people |
| Date can't be read | `added` isn't a date | Same |
| Regular booked since | A `reg … extra` person booked after their newest line (B7: may still want the extra visit) | Same |

Stale marks (gone, 60 days, `til` date passed, booked since) work the same way but read "stale". When both apply, stale wins because it's the clearer reason.

**2. Display flags: shown next to a name, never change who is shown.**
- `ask Josée first`: the therapist's `approval` is `see_first`.
- `new client, phone only`: no Kneadly profile yet, so no text consent.
- `text only` / `call (landline)`: the person's contact preference.

These appear in `[…]` in `matches.txt` and in the `flags` column of `matches.csv`.

**3. Run warnings: listed under WARNINGS in `preprocess-report.txt`; the run doesn't stop.**
- An opening that isn't in the booking export, or that the export shows differently.
- A therapist who isn't in `config/clinic.json`. That opening gets nobody.

A missing file or column **stops** the run with "Stopped: …" instead.

**Releasing a held person ✅ built Oct 30.** A plain newer line still doesn't release someone: the old unreadable words might still apply. The desk now has two ways to release a person, and both need a person's decision:
- **`start over` line** (or `new:`), for a note that can't be read: `start over - Rachel only - 60`. Everything the older lines said about what they can take is dropped, and so are their unreadable words. The older lines still count for "first asked", so the person keeps their place in the queue. A bare `start over` with no details is held, so it can't silently become "anyone, any time". "NEW client" (no colon) is unaffected. In `parse_notes.py` and `people.start_index`.
- **`reviewed.csv`**, for identity flags. Columns: `line, decision, other_line, checked_by`.
  - **Decisions:**
    - `same person`: merge them; the newest readable number is used.
    - `different people`: no merge, no flag.
    - `ignore`: leave the line out; its verdict is "ignored".
  - **Doubtful rows don't apply.** An unknown decision, a line that isn't on the waitlist, a missing `other_line`, or two rows that contradict each other are skipped with a warning, and the lines stay held.
  - **Never echoed:** `checked_by` doesn't appear in any output.
  - **Opt-in:** it's used only with `--reviewed reviewed.csv` (the clinic's shortcut), **never on the demo files** (no hand edits). Code: `csv_in.read_reviewed`, `people.build_reviewed`, `group_lines`.
  - **In the report:** `preprocess-report.txt` now says how to release each kind of held person and lists the desk decisions used.

**Still a gap (planned):**
- **Unknown words aren't counted.** The report lists each held person, but not "'weekends' appears on 3 lines". Planned: an **unknown-word log** in the report (word, how many lines, which lines). The desk then rewrites those lines in known shorthand, or Julie adds a short form or nickname to the settings.

---

## 8. When is a slot a "late opening"? (slot lifecycle)

The confusion comes from treating **"not confirmed"** as if it were **"cancelled"**. They are different states:

```
BOOKED ──(T-48h Kneadly reminder)──► REMINDED ──► CONFIRMED ────────────────┐
                                         │                                  │
                                         └─(no reply by T-24h)─► AT RISK ───┤   (still booked!)
                                                                            │
   any of these ──(cancel via online / voicemail / text reply / call)──► CANCELLED
                                                                            │
                         cancelled_at ≥ 24 h before start → normal cancel (online page refills it)
                         cancelled_at < 24 h before start → LATE OPENING → MATCHED → OFFERING #1..#n
                                                                                       → FILLED / EXPIRED
   not arrived at T+15 min ─────────────────────────────────────────────► NO-SHOW (never offered)
```

**Rules for a safe design ✅ (present and future)**
1. **Only a cancellation recorded in Kneadly creates an opening.** "At risk" (unconfirmed) never does. Data backs this: 24 of the 44 late openings had **confirmed** first, so confirmation predicts little.
2. **Two kinds of "source of truth"** ([§15 #13](#15-review-of-your--notes-oct-30)):
   - **The schedule** (who is booked when) is **Kneadly only**, now and later. The desk books there; a second calendar would drift and cause double bookings, Marc's first "no".
   - **Cancellation events** can move to the platform's **inbox** (§11.6). The platform may hear first: morning-call taps, desk taps, and later voicemail or text replies if those channels can be connected.

   The rule becomes: an opening starts when a cancellation is recorded in Kneadly **or** in the inbox. **Before the first offer, the desk frees the slot in Kneadly**, so Kneadly always matches reality. A message read automatically ("can't make it" or "running late"?) **never creates an opening alone**; a person confirms it with one tap.
3. "Late" is decided by **`cancelled_at` vs start** (when it happened), not by when we found out.
4. **Opening ID = appointment ID**, so seeing the same cancellation twice changes nothing.
5. **Re-check the slot is still empty** just before each offer (data may be up to 30 min old; someone may have grabbed it online).
6. **One live offer per opening** + Julie's **manual time block** in Kneadly while offering (Kneadly has no hold).
7. An opening **expires** automatically once no remaining candidate can meet their notice.

**For Friday (assumption ✅):** "we were told". The late-openings file is the list of confirmed late openings. "At risk" is not used.

---

## 9. Tests

### Priority 1: preprocessing (raw CSV → core data) ✅
| Test | Checks | Expected source |
|---|---|---|
| Phone normalisation | all 5 formats → 10 digits; `same #` resolves to lines 5 and 9 | hand-written cases |
| Person identity (phone + name) | phone match + compatible names → merged (`Lynn Savoie`/`Lynn S.`, `Tina Saulnier`/`Tina S`); phone match + different names → flagged, not merged; compatible names + different phones → flagged, not merged | answer key `duplicate of` + made-up cases |
| Date parsing | `Jul 6`, `7/14`, `Sept 1`, `10/19` → 2026 ISO dates | hand-written |
| Name matching | accents, `Lynn S.`, nicknames (Bob → Robert, …) | hand-written + export |
| Note parser, line by line | each of the 60 lines → expected fields | answer key's "Can take: …" text, turned into a table once |
| Grouping and merging | duplicate groups match the key (`W02 → W51`, `W26 → W42`, …); inherited fields (line 43 keeps "Kelsey or Amira") | answer key `duplicate of` |
| Staleness | the 20 stale lines match the key **with the right reason** (30 active, 10 duplicates) | answer key `stale` notes |
| Run date | same files, run date Oct 30 → late-August lines turn stale | hand-written |
| Unknown shorthand | made-up phrase → line flagged, not offered | hand-written |
| Privacy | no health word appears in any output field | health vocabulary list |
| Bad input | missing column / empty file → clear error, no crash | hand-written |

### Priority 2: matching ✅
| Test | Checks |
|---|---|
| One test per filter | therapist, female, prenatal, length (incl. `90 only`), day, time window, notice, day-before, availability dates, using small made-up people |
| **Golden test: all 44 openings** | every shown name is in Tanya's list; "nobody" when she says nobody; never > 3; report score (target 44/44, floor 8/10 per Friday rules) |
| Hard gate | **zero** stale or unsuitable names across all 44 |
| No-shows | all 8 → nobody |
| Unseen-shorthand set | your own new lines written in fresh shorthand → expected results, so the parser isn't tuned only to these 60 lines |
| Ordering modes | Each mode returns the same *set* of fit people, ordered differently, so **the 3 shown can differ** (15 fit → first-asked and regulars-first may show different 3s). Checks: (a) in every mode, the 3 shown are all on Tanya's list ✅; (b) the **full** fit set (no 3-name cap) equals Tanya's list on all 44 ✅, which keeps any order from bringing a wrong person into view; (c) planned: the full set is identical across modes, and the 3 shown are the first 3 in that mode's order ([§15 #14](#15-review-of-your--notes-oct-30)) |

⚠ **Overfitting guard** (strengthened Oct 30, [§15 #15](#15-review-of-your--notes-oct-30)):
1. **No per-person rules.** No rule may name a person or a line number. Every fix is a general rule or a config value. ✅
2. **Clinic facts in settings, not code.** Therapists, time words and nicknames are there now ✅. Planned: therapist tags + routing words (§15 #2). Shorthand: unknown-word log now; the board's fixed fields later (§15 #6).
3. **Fail safe on anything unknown.** An unknown word, therapist, phone or date → held or warned, never guessed ✅. Health words no longer swallow schedule words ✅ (§15 #7).
4. **Settings check.** Stop on a short form used by two therapists, an unknown setting or a bad time, before a run ✅ (built Oct 30).
5. **Unseen test set, written before seeing new data.** 8 cases + the 12 phrasings tried on Oct 30 + 3 health-mix cases ✅.
6. **Held-out real data.** Score Friday's 10 openings **once, as delivered, before any fix**. After that, every fix must keep both the 44 sample openings and Friday's 10 passing. After go-live, every row in `mistakes-log.csv` becomes a test. Planned.
7. **Robustness checks.** The same results with rows shuffled, with run dates Oct 21 / Oct 30 / Nov 15 behaving as expected, and with an extra therapist added to the settings without changing anyone else's results. Planned.
8. **Drift alarm.** If more than ~10% of people are held for review in one run, the report says "the notebook style may have changed: check before trusting short lists". Planned.

### Priority 3: future platform ❓ (later)
Event deduplication (same cancellation heard on two channels → one inbox row), one-live-offer lock, expiry timing, "Cancelled" tap on the call list → opening + 3 names, adapter contract tests (each adapter produces valid core data).

---

## 10. Friday demo runbook ✅ (built Oct 30)

```bash
python run.py --waitlist waitlist-NEW.csv --appointments appointments-NEW.csv --openings late-openings-NEW.csv --run-date 2026-10-30
```
1. Save the new files into the project folder **unchanged** (no hand edits). Any name works; pass them with the flags above.
2. Run the command → `out/matches.txt` (read this), `out/matches.csv`, `out/preprocess-report.txt`, `out/line-verdicts.csv`, core data in `out/core/`.
3. Read `preprocess-report.txt` first: anyone **held for review** is left out, not guessed. Check WARNINGS is "none".
4. Read out the names per opening for checking against Tanya's answers.
5. If someone says no: `--declined O01:39,42` re-runs that opening without them.
   **Don't pass `--reviewed` on the demo files:** desk decisions are clinic use only (no hand edits).
6. Hand-in comment: each done check, files, the command above, and the test results.

**Sample results (run date Oct 21):** `python run.py --run-date 2026-10-21` then `python score.py` → 44/44 openings match, 0 wrong names, 60/60 waitlist line verdicts match Tanya. With the 3-name cap removed, the full set of people who fit equals Tanya's full list on all 44. `python -m pytest` → 148 tests pass. `python run.py --check-settings` → "Settings OK".

**Oct 30 dry run on the sample files:** lines 10, 12, 14 (added Aug 24–29) turn stale under the 60-day rule; still 44/44 and 0 wrong names.

**Stack ✅:** Python 3 standard library only (`csv`, `datetime`, `re`, `unicodedata`, `json`) + `pytest`. Runs on the desk's Windows PC, $0/month, no network, no data leaves the computer.

**Folder layout**
```
run.py                     # one command, end to end
score.py                   # sample only: compare out/ with Tanya's answer key
kettle/
  config.py                # loads config/clinic.json
  pipeline.py              # CSV → core data → matches → files
  adapters/csv_in.py       # present: CSV → records (+ export cross-check, A8)
  core/normalise.py        # phones, dates, names
  core/parse_notes.py      # shorthand → fields (health text dropped)
  core/people.py           # group (phone + name), merge, stale
  core/match.py            # filters, order, pick ≤3
  output/report.py         # txt + csv + core data
config/clinic.json         # therapists, defaults, time words, nicknames
reviewed.csv               # the desk's decisions on held lines (clinic use, --reviewed; blank to start)
tests/                     # 148 tests: priority 1 and 2, privacy, unseen shorthand, settings check, desk fixes
out/                       # results; out/core/ = core data (people.json, openings.csv)
```
Input CSVs stay where they are (project folder); they are only read.

---

## 11. Future platform ❓ (design only, not built now)

### 11.1 What changes vs present
| | Present (Friday) | Future platform |
|---|---|---|
| Openings arrive | late-openings CSV, weekly | Kneadly feed every ~30 min + desk one-tap entry |
| Waitlist | handwritten notes, parsed by script | waitlist board: one editable card per person, fixed choices, no parsing |
| Staleness | inferred (60 days, booked since) | automatic: "booked since" from feed; 30-day "still interested?" check by the desk |
| Output | text/CSV file | desk screen: opening queue + 3 names + one-tap outcome |
| Morning confirmation calls | sticky note + dots; a cancellation waits until ~10:30 | **call list with one-tap outcome; "Cancelled" → 3 names at once** (§11.5) |
| Where cancellations are heard | voicemail, text reply, phone, online, morning calls, each noted separately | **one cancellation inbox** (§11.6) |
| Offer history | none | offer log (who, when, yes/no/no answer) |
| Core data + matcher | **same** | **same** |

### 11.2 The waitlist board: editable cards instead of a form 🟡 (design changed Oct 30)

Your idea, adopted: a **list of cards, one per person**, edited in place, not a separate form ([§15 #1](#15-review-of-your--notes-oct-30)).
```
WAITLIST                                   [+ Add]   [Show: active · held · stale]
┌ Amanda Bourgeois  506-555-0125   asked Sep 11 · last contact Sep 30 ─────────────┐
│ [Rachel] [Josée]  [60]  [any day]  [any time]  [2 h notice]  [call]               │
│ [Still interested ✓]  [Take off]  [history ▾]                                     │
└───────────────────────────────────────────────────────────────────────────────────┘
```
- **Tap a chip to change it.** The card keeps a history ("Oct 30, Tanya: Josée → Rachel or Josée"). No repeat lines, so no merging, no `same #`, no "which line is newest".
- **+ Add** opens a blank card at the top with the same chips: name, phone, then ~6 taps.
- **Still interested ✓** resets the contact date (staleness). **Take off** asks for a reason from a short list (booked, moved, not interested).
- The board also shows **held** and **stale** cards, so cleanup happens where the list is kept.
- The chips come from the settings, so a new therapist or tag shows up without code.

**Why cards beat a form here:** the notebook *is* a list. Tanya scans it and adds to it, and a list shows the person's current state at a glance. A form hides the list and invites duplicates.

**Still to test (Tanya's rule: "less time than the book, not more"):** time 3 real calls each way: the book, a spreadsheet row (the present stopgap in `handover-plan.md`), and a paper mock-up of the board. About 15 minutes with Tanya.

**Card fields** (same as the old form design):

| Field | Input type |
|---|---|
| Name, phone | text (phone checked for 10 digits); auto-links to the Kneadly client if one exists |
| Therapist | `Any` / pick one or more / `Anyone but…` / `Female therapist only` |
| Desk-only routing | One chip per therapist **tag** in the settings, e.g. `Prenatal-trained only` (no reason recorded). Never shown on a screen a client can see |
| Length | 30 / 45 / 60 / 90 (tick all that work) |
| Days | Mon–Sat ticks |
| Time | Morning / Afternoon / Evening ticks, or "from __ to __" |
| Notice needed | 30 min / 1 h / 2 h / 3 h / 4 h / day before |
| Available from / until | optional dates |
| Contact | Call / Text (text only if consent is on file in Kneadly) |
| Auto | date added, last contact, added by |

No free-text health field, and **no free-text field at all on the card**. A free-text "notes" box would bring the shorthand and the health details straight back. Tanya's test: filling it must take **less time than writing in the book** (≈ 6 taps + name + phone).

### 11.3 Getting cancellations from Kneadly: options ❓
| Option | Freshness | Needs | Known? |
|---|---|---|---|
| A. Desk one-tap entry ("this appointment cancelled") | instant when the desk sees it | nothing | ✅ works today |
| B. Daily scheduled report | once a day | Marc's owner-account switch + one-page note, "a few days" | ✅ exists |
| C. Kneadly API / webhooks, polled every ~30 min | ~30 min | possibly the higher plan (~$45/mo, unchecked) | ❓ ask Julie |
| D. Kneadly cancellation alert emails, read automatically | minutes | Kneadly must send them | ❓ ask Julie |

**Recommendation:** design for **A now, B for the client list and "booked since", and C/D when Julie confirms they exist**. All four feed the same `openings` table through one interface (§11.4).

### 11.4 Interfaces: how the parts connect 🟡
```
[Kneadly] ──read only──► Ingest adapter ─────────────┐
[Morning call list taps (§11.5)] ────────────────────┼─► Cancellation inbox (§11.6) ──► openings ─┐
[Desk one-tap entry: voicemail / phone / text] ──────┘   (one row per appointment ID)            │
[Waitlist board] ────────────────────────────────────────────────────────────────► people ───────┤
                                                                                                 ▼
                                                     Matcher ──► 3 names on the inbox row ──► offer log
                                                                                                 │
                                                                                                 ▼
                                    Desk books the yes in Kneadly by hand (+ "rebooked into" link)
```
- **Read only from Kneadly.** The platform **never writes bookings**; the desk does. So the platform can't cause a double booking.
- **Every source produces the same core records**, so new sources don't touch the matcher.
- **Messages:** drafts only (clinic name, time, therapist's first name, how to reply), sent by a person from the clinic phone. Marc's off switch and a sent log are in the design.
- **Privacy one-pager for Marc:** what is read (appointment times, names, no treatment notes), where it's stored (desk PC or one named host), how long, who can see it.
- **Running cost target:** $0–$12/month without the higher plan; ≤ $57 with it, right at Marc's line. Needs the real price from Julie.

### 11.5 Call outcome → instant match ✅ (design only)

**Why:** the 8:00–9:15 call block is when Tanya is already on the phone, but today a cancellation she hears then waits on a sticky note until ~10:30, so morning openings are "written off". In the sample, **29 of 36 late cancellations had already come in by 9:15** (the night before or early that morning), and only 11 of those were refilled. This feature is the only way the morning openings get a chance.

**What the desk sees at 8:00**
```
TOMORROW + TODAY, NOT CONFIRMED                               [Confirmed] [Voicemail] [Cancelled]
 Tue 11:00  Dave · 60   R. Comeau   506-555-0xxx                   ✓          ●           ✕
 Tue 14:00  Kelsey · 90 M. Gallant  506-555-0xxx                   ✓          ●           ✕
 ...
```
**Flow**
1. The call list is built automatically: today's and tomorrow's visits not yet confirmed (from Kneadly: daily report at minimum, feed if available). It replaces the sticky note and the dots.
2. One tap per call:
   - **Confirmed** → row done.
   - **Voicemail** → row gets the dot and moves to "try again"; it stays one tap away if they call back.
   - **Cancelled** → the inbox (§11.6) creates the **opening immediately** (`appointment_id` as its ID, `cancelled_at` = now, notice worked out from the start time). The matcher runs and **3 names appear right under that row**. Tanya is already on the phone, so she can call #1 next.
3. **Yes** → Tanya books it in Kneadly, then taps "Filled by …" → offer log. **No / no answer** → next name (§7.2).

**Rules**
- **No double entry:** Kneadly stays the source of truth. The desk still marks the confirmation or cancellation in Kneadly as today; the tap replaces the sticky note, not that step. When the Kneadly feed later shows the same cancellation, it's matched by `appointment_id` and ignored.
- **Nothing is sent automatically.** Every call is still made by a person.
- **No health detail** on the list. It's on the desk screen, which a client could see.
- Same screen works for **Bethany on Saturdays** (desk from 8:30): names come with reasons, so she doesn't need to know the clients.

**Needs:** a list of tomorrow's unconfirmed visits before 8:00. That's the daily report (Marc's switch) at minimum. ❓ What time does the daily report arrive? Ask Julie.

### 11.6 One cancellation inbox ✅ (design only)

**Why:** cancellations arrive five ways (overnight voicemail 12, online 11, phone 5, morning call 5, text reply 3 of the 36 sample late cancels) and end up on sticky notes. One list means nothing gets lost and every cancellation turns into an opening with names in one step.

**One row per cancelled appointment**
```
HEARD    VIA          SLOT                       NOTICE LEFT   STATUS              NAMES
07:58    voicemail    Tue 11:00 · Dave · 60      3.0 h         offering #1 (8:05)  Shawn D · Mireille C
08:21    morning call Fri 13:15 · Josée · 60     4.9 h         new  [ask Josée]    Chantal M · Amanda B · Andrea P
01:42    online       Wed 15:00 · Kelsey · 60    13.3 h        filled (Sarah C)    —
```

**How each channel gets in**
| Channel | How it reaches the inbox | Automatic? |
|---|---|---|
| Online cancel in Kneadly | Kneadly feed (§11.3 C/D); daily report is too slow | ❓ depends on Julie's answers |
| Overnight voicemail | Desk plays it at 8:00 and taps the appointment → "Cancelled (voicemail)", with the voicemail's time if the phone shows it (decides "late", §8 rule 3) | one tap |
| Text reply to the Kneadly reminder | From the feed, if Kneadly exposes replies; otherwise one tap | ❓ ask Julie |
| Phone call in the day | One tap | one tap |
| Morning call outcome | From §11.5 | automatic |

**Rules**
- **One row per `appointment_id`**: the same cancellation heard twice (voicemail, then online) is merged, never two openings.
- **Status per row:** new → offering #n → filled / expired. A row **expires by itself** once no one left can meet their notice.
- **One live offer per row** (§8 rule 6); before each offer the desk glances at Kneadly to check the slot is still empty.
- **No cancellation reason stored** ("woke up with a cold", "hurt my back"): only the channel and time. Keeps health details out.
- **Sorted by soonest start**, so the most urgent opening is always at the top.
- **Gives Marc the numbers he can't get today:** refill rate per channel and time from "heard" to "filled", from the offer log instead of hand-linked "rebooked into".

**Smallest working version:** the inbox + one-tap entry + the matcher, running as a local page on the desk PC, works with **no Kneadly connection at all** (option A). The feed only makes online cancellations appear by themselves.

**More channels later (your idea, [§15 #13](#15-review-of-your--notes-oct-30)):**
- **Morning calls:** need no outside connection; that's the §11.5 tap.
- **Voicemail:** needs a phone system that turns voicemails into text or email. That service hears "I'm cancelling, my back is out", so it's an outside service handling health details and needs Marc's one-page sign-off (§16).
- **Text replies:** reach Kneadly's number, so they're only available if Kneadly passes them on (ask Julie).

Whatever arrives automatically lands as a **suggested** row ("Voicemail 06:31 looks like a cancellation: Tue 11:00 Dave?"). It becomes an opening only after a person taps **Confirm** (§8 rule 2).

### 11.7 Feedback loop ✅ (design only)

Your idea ([§15 #5](#15-review-of-your--notes-oct-30)): what happened to past offers should improve future ones.

**Leakage rule:** an opening's outcome never decides who is offered **that same** opening. Outcomes only inform later ones, and always through a person.

| Outcome data | Feeds back into | Who acts |
|---|---|---|
| Offer log: offered, said yes / said no / no answer | Anti-pestering: max offers per person per week; never re-offer a slot someone declined | Automatic limit, set by Marc |
| "Said no" 3 times in a row | Card shows "ask if still interested" | Desk |
| "Yes, keep me on, but not this one" | Counts as contact: resets the 60-day clock | Automatic |
| Declines grouped by reason the desk taps (time, notice, therapist) | Monthly check: a rule that keeps producing refused offers (e.g. a notice default that's too short) | Julie, with Marc |
| Each week's real openings + who said yes | **New test cases**: the test set grows from real use, the strongest guard against overfitting (§9) | Julie runs the tests |
| Filled via waitlist / online / client called (`booked_via`, `rebooked_into`) | Marc's numbers: refill rate per channel, time from "heard" to "filled" | Report |

The matcher **never learns by itself**. A rule only changes when a person edits the settings and the tests pass.

---

## 12. Fewer morning confirmation calls (plan only, not a priority)

**Constraint:** our system never phones, texts or emails anyone by itself. Kneadly's own existing reminders are not ours to change, only to ask Julie about.

**Evidence:** confirmation calls take ~6.25 h/week (~$7k/yr). 24 of 44 late openings had confirmed anyway ("confirming doesn't mean anything").

| Idea | What it does | Build size |
|---|---|---|
| **Risk-ranked call sheet** | From the export, list only unconfirmed visits for today/tomorrow, ranked by risk signals (new client, past no-show or late cancel, booked long ago). Tanya calls the top of the list; Marc decides whether low-risk regulars get no call. | small |
| **Call outcome → instant match** | ✅ **Moved into the platform plan: §11.5** | medium (platform) |
| **One cancellation inbox** | ✅ **Moved into the platform plan: §11.6** | medium (platform) |
| **Move the calls** | Call tomorrow's unconfirmed in the afternoon lull instead of 8:00, freeing the morning for refills. A process change, no build. | none |
| **Ask Julie** | Can Kneadly send a second reminder at 24 h? (Kneadly sends it, not us.) | none |

---

## 13. Risks and honest caveats

1. **Faster data alone doesn't fix overnight cancellations.** Tanya: with a perfect list at 8:00, "I still couldn't have called anyone"; nobody acts before ~10:30. A 30-min feed mainly helps **online** cancellations (11 of 36 late cancels) and same-day ones. It pays off only together with a desk change: call outcome → instant match (§11.5) and the cancellation inbox (§11.6).
2. **Name matching to the export (A5) is the weakest link.** A missed match means a stale person is offered, which fails the hard gate. Mitigation: nickname table, flag ambiguous cases, test on the 5 known "got in" cases.
3. **Overfitting to 44 openings and 60 lines.** Mitigation: the 8-point guard in §9.
4. **Run-date effects:** an Oct 30 run makes several late-August lines stale. Tested ✅.
5. **Unknowns that could change the platform design:** Kneadly API or alerts, the higher plan's price, where Kneadly stores data, text consent for people who aren't clients yet. All are questions for Julie.
6. **A health word can swallow a schedule word (found Oct 30).**
   - What happens: the parser drops the whole piece of a note that has a health word in it.
   - Example: `sore neck, Rachel only - 60` loses "Rachel only", so the person would be offered **any** therapist. That's a wrong name, and a hard-gate failure.
   - Sample: no line does this; every health word there is set off with " - ".
   - Friday: "same handwriting", but it isn't guaranteed.
   - ✅ **Fixed Oct 30 (P1):** see §15 #7. `sore neck, Rachel only - 60` now keeps Rachel; `sore neck Rachel only - 60` (no comma) is held for review. Sample results unchanged.
7. **A short form shared by two therapists (found Oct 30).**
   - **Where the problem is:** it doesn't affect the opening side. Each opening comes from a booking with the therapist's full name, so the opening's therapist is always clear. It affects reading the **waitlist note**, which says which therapists the *person* will accept.
   - **Shown on Oct 30 with a temporary copy of the settings:** `M only - 60 - Tues` reads as **Marc** today. Add a therapist "Melissa" with short form `m` below Marc, and the same note reads as **Melissa**, with no warning.
   - **Result:** that person is offered Melissa's openings (a wrong name) and never Marc's (a missed fit).
   - ✅ **Fixed Oct 30 (P1):** the settings check stops on a short form used twice (every run, and `python run.py --check-settings`). Julie removes the letter from both therapists, and from then on any note using it is held for review ("`m`: Marc or Melissa?").
   - **Same idea, smaller case:** two therapists with the same first name. Today an opening's therapist is matched on full name *or* first name, in settings order, so the wrong one could be picked. ✅ **Fixed Oct 30:** full name first; a first name (with an optional start of the last name, `Josée L.`) only when exactly one therapist fits; otherwise a warning and nobody for that opening.
8. **Held people couldn't be released by a new line (found Oct 30).** The desk advice at the time ("rewrite as a new line") didn't clear an older unreadable line. ✅ **Fixed Oct 30:** `start over` lines and `reviewed.csv` (§7.3); `handover-plan.md` §1.2 updated.

---

## 14. Build order

1. ✅ §3 decisions made (Oct 30) → write `config/clinic.json` from them.
2. ✅ Normaliser + note parser + priority-1 tests (parser table built from the answer key's "Can take" text).
3. ✅ Grouping, merging, staleness + tests against the key's duplicate/stale verdicts.
4. ✅ Matcher + golden test on 44 openings + hard-gate test.
5. ✅ Output format + `run.py` + a dry run with run date Oct 30.
6. ✅ Unseen-shorthand test set.
7. ✅ Written plan for done check 3: [handover-plan.md](handover-plan.md) (owner, cost, when it's wrong), pointing to §11.5 and §11.6 for the future. Hand-in text: [hand-in-comment.md](hand-in-comment.md).
8. **Changes from the Oct 30 review (§15).** P1 ✅ built Oct 30; P2 and P3 planned, not built.

| Priority | Change | Size | From |
|---|---|---|---|
| ✅ **P1: built Oct 30** | Health words no longer take the whole piece with them. Parts beside a health word, and brackets, are read when they hold a scheduling word (`kettle/core/parse_notes.py`). A part mixing both is held with a reason that doesn't quote the note. Tests: the 12 probes + 3 health-mix cases + brackets | small | §15 #6, #7 |
| ✅ P1: built Oct 30 | Settings check on every run and `python run.py --check-settings`: duplicate short forms, unknown settings, bad values and times, a broken file (`kettle/config.py`). Openings matched on the full therapist name first. Tests: `tests/test_config.py` | small | §15 #3, §13 risk 7 |
| ✅ P2: built Oct 30 | `start over` / `new:` lines that start a person over; `reviewed.csv` for identity decisions (`--reviewed`); report says how to release each held person; `handover-plan.md` §1.2 updated. Tests: `tests/test_desk_fixes.py` | small | §7.3 |
| P2 | Unknown-word log in the report (word, count, lines); drift alarm. (Phrase book dropped Oct 30: the board's fixed fields replace shorthand) | small | §15 #6, #15 |
| P2 | Therapist tags + routing words replace `female`/`prenatal_trained`; before/after report when settings change; anonymous health-category counts for deciding new rules | medium | §15 #2, #8, §15.1 |
| P2 | Robustness tests: shuffled rows, three run dates, extra therapist | small | §15 #15 |
| P3: platform | Waitlist board (after the timing test with Tanya), feedback loop, `booked_via` for "taken online", suggested rows from extra channels, narrower `see_first` | large | §15 #1, #4, #5, #12, #13 |

---

## 15. Review of your ❓❓ notes (Oct 30)

Each note is answered here and folded into the section it came from (look for "§15 #n"). **Type:** C = caveat to fix · I = idea · Q = question.

| # | Your note (where) | Type | Answer | Change to the plan |
|---|---|---|---|---|
| 1 | A list of editable cards, not a form (§2 #7) | I | Agreed. The notebook is a list and Tanya works by scanning and adding. One card per person, edited in place, removes repeat lines, `same #` and merging altogether. It still has to pass Tanya's "less time than the book" test, so time it before building | §11.2 rewritten as the waitlist board; 15-min timing test with Tanya |
| 2 | `female_only`/`prenatal_only` too specific; other medical info? (§4.1) | C | Right: two hard-coded yes/no fields mean any new clinic rule needs code. The clinic has exactly **one** medical rule today (prenatal); post-op → Josée is "usually", not a rule (B2). Other health words correctly stay out. Generalise: therapists get **tags** (`female`, `prenatal-trained`, …), and people get `needs` = tags. Settings map words to tags (`pregnant`, `expecting`, `tri` → `prenatal-trained`). A new rule = two settings lines | §4.1 `needs` field; §15 #8; build order P2 |
| 3 | Is the therapist list complete? Overfitting? (§4.1) | Q + C | Complete: six in the discovery notes, and the export has exactly those six (Dave 115, Josée 112, Rachel 105, Amira 103, Kelsey 102, Marc 58 visits in 4 weeks). Settings that hold clinic facts aren't overfitting; rules tuned to sample lines would be. Already safe: an unknown therapist in openings → warning + nobody; in a note (`Dave or Sophie`) → held. **New risk found:** two therapists with the same initial → the last one silently wins. This happens when reading the *person's note*, not the opening (follow-up in §15.1) | §4.1 text; "working days" removed (not needed); settings check (P1); §13 risk 7 |
| 4 | `booked_via`: useless for matching, but for the platform? (§4.2) | Q | Not for matching. Two platform uses: (1) **slot taken online**: while the desk offers a slot, a new booking in it with `booked_via = online` closes the row ("taken online, stop calling"); (2) **refill reporting**: in the sample, 12 refills: 3 rebooked online, 5 a client happened to call, 4 desk called the waitlist. It shows whether the waitlist is what fills slots | §4.2 moved to "keep for reporting (platform)"; §11.7 |
| 5 | `refilled` must not feed the matcher, but should be feedback (§4.2) | I | Agreed, with one line: an opening's outcome never picks names for **that** opening. Across openings it should feed: offer limits, "still interested?", rule review, new test cases, Marc's numbers. Always through a person; no self-learning | New §11.7 feedback loop |
| 6 | Can the script handle a new version of the shorthand? (§5.3) | Q | Tested 12 new phrasings today. **New combinations of known words: yes** (`Wednesdays after 2, 45 min`; `Rachel - mornings, can come in 45 min`; `Marc pls - 1hr - Tue`). **New words: held, never guessed** (`Kels only`, `weekends`, `before noon`, `90min`, `needs 1 day notice`, `Dave or Sophie`). That costs names, never correctness. Teaching a word is a code change today, except therapist short forms and nicknames (`kels` can go in the settings now). **Decided (follow-up):** an unknown-word log only, with no phrase book; the platform's fixed fields remove the shorthand. **One real gap:** see #7 | §5.3 note; P1 tests; P2 unknown-word log |
| 7 | Health: remove it? The therapist may need to know (§5.3) | Q + C | **Remove it from this tool, yes.** Therapists need health details, but they get them from where the clinic already keeps them: the **intake form and treatment notes in Kneadly** (discovery notes). New clients fill the intake when they first book. The waitlist only decides whom to call; it doesn't need the condition, and the book "sits on the counter". **Gap found:** the parser drops the whole *piece* containing a health word, so `sore neck, Rachel only - 60` loses "Rachel only" and becomes "any therapist", a possible wrong name. Fix: drop the health words only, keep reading the rest; anything unclear → held | §5.1 step 3, §5.3, §13 risk 6; P1 |
| 8 | New factors → script updates, bad for non-technical owners (§5.3) | C | Agreed. Make the common changes settings changes: tags + routing words (#2), a **settings check** that catches typos, a **before/after report** ("these 4 names changed because of your edit"), and a 5-step checklist for Julie in the handover plan. Honest limit: a new *kind* of rule still needs a developer (0–2 times a year, already budgeted) | §5.3 text; P2 |
| 9 | "Parse confidence": what is it? (§6.2) | Q | An early idea: a score for how sure the parser is about a line. Not built and now dropped: a line is either fully read or held for review, so there's no half-sure person to rank | Removed from §6.2 |
| 10 | What's a "switch"; is order the only one? (§6.3) | Q | A switch is a setting changed without code. `--order` only reorders the people who fit (which 3 come first); it never changes who fits. There are about 15 switches: command line (run date, order, declined, files) and settings (defaults, time words, therapists, nicknames) | §6.3 text; new §6.5 table |
| 11 | "Fewer than 3 rather than anyone with a parse flag"? (§6.3) | Q | If any part of a person's notes can't be read, they're held for review and not shown, even if the opening then shows 1–2 names or nobody. A wrong name fails the hard gate; fewer names is fine under the scoring rules. They're listed in the report for the desk to fix | §6.3 text; §7.3 flags |
| 12 | Therapist's say: what about the other 3? (§6.4) | Q + C | Marc is on record: "Just fill it. I don't care who." → `none`. **Amira and Rachel: nothing on record**; `none` is an assumption. It's safe for matching (approval only adds a flag, never removes a name), but it's an **open question for Marc**. Josée's actual concern is new clients at short notice, so a narrower `see_first` would cost Tanya less time | §6.4 evidence table; P3 option |
| 13 | Kneadly as the single source of truth could change if the platform takes voicemail, texts, morning calls (§8) | I | Partly. Split it: **the schedule stays Kneadly only** (two calendars = double bookings). **Cancellation events can start in the platform's inbox.** The desk frees the slot in Kneadly before the first offer. Anything read automatically is only a **suggested** row until a person confirms. Voicemail transcription is an outside service hearing health details → Marc's one-pager | §8 rule 2 rewritten; §11.6 "more channels later" |
| 14 | Ordering: with 15 who fit, different modes show different 3s (§9) | Q | Correct. It doesn't change the Friday score (any 3 who fit count, and the full fit set equals Tanya's on all 44), but it decides who gets the first call, so it's the clinic's choice (Marc: "you and Tanya figure out the order"). The full-set test is what stops a mode from bringing a wrong person into view | §9 ordering row rewritten |
| 15 | Overfitting guard isn't enough (§9) | C | Agreed. Now 8 points: no per-person rules; facts in settings; fail safe on unknowns; settings check; unseen tests written first; Friday's 10 scored once before any fix, then kept as a held-out set; robustness checks (shuffle, run dates, extra therapist); drift alarm when many people are held | §9 guard rewritten |

### 15.1 Your follow-ups (Oct 30, second round)

| On | You said | Answer / decision | Plan change |
|---|---|---|---|
| #3 shared initial | The opening already has its therapist from the cancelled booking, so why would initials matter? | **You're right about the opening side:** its therapist comes from the booking with a full name, and the rule stays "fits if the opening's therapist is on the person's list". **The initials matter on the person side.** The note `M only` decides who is on that person's list. Shown with a temporary settings copy: today `M only` → Marc. Add a "Melissa" with short form `m` and it silently becomes Melissa, so the person is offered Melissa's openings (wrong name) and never Marc's (missed). | §13 risk 7 rewritten; P1 settings check now also covers same first names |
| #6 new shorthand | A log of unknown words is enough for now; the platform's fixed fields will remove these discrepancies | **Agreed, decided.** No phrase book. The parser is only needed until the board replaces the notebook, and once to import it. Three things fixed fields *don't* remove: (1) the **transition**: Bethany and the therapists write in the book too, so the board only works once everyone uses it; (2) **duplicates**, solved by "+ Add" searching by phone first; (3) **matching to Kneadly clients** (A5), solved by linking each card to the Kneadly client when one exists | P2 row changed to unknown-word log; §5.3, §7.3, §9 updated |
| #7 health info | Therapists may not need it, but new rules (point #8) might | **Agreed: rule-making needs evidence, but not a per-person record.** See §16 "Making new rules without keeping health details" | §16 new subsection; P2 row adds anonymous category counts |

---

## 16. Health information: where it may and may not go

**What the clinic actually said:**
- Marc: health details are personal health information under New Brunswick's **PHIPAA**. "None of that goes in a text… and nothing a client can read over the counter."
- Marc, on outside services: "Put it on one page. I'm not signing up for something I don't understand."
- The clinic **already keeps** health information in two places: the notebook, and Kneadly (intake forms, treatment notes, hosted by Kneadly; where exactly is unknown, ask Julie).

So the rule isn't "no system may ever touch health data". It is:
1. Never in a message.
2. Never on a screen or paper a client can see.
3. Nothing to an outside service without Marc's one-page sign-off.

On top of that, our own rule is stricter: **don't keep what matching doesn't need.**

| Setup | Health text read? | Kept? | Leaves the desk PC? | OK? |
|---|---|---|---|---|
| **Present: local script** (built) | Yes, in memory, from the clinic's own file | **No.** Dropped while parsing; only the prenatal routing survives | No | ✅ Adds no new copy. The only health-derived item kept is the prenatal flag in `out/core/people.json` |
| Local script + AI helper on held lines (§5.2, optional) | Only if not removed first | No | **Yes**, to the AI service | Needs Marc's one-pager; health words removed before sending |
| **Future: privately hosted platform** with the waitlist board | **No**: the card has no free-text field | Only the routing tag (`prenatal-trained`) | Yes, to the host | ✅ if Marc signs the one-pager (host, country, who can log in, backups, how long kept, deletion). "Private" and "secured" reduce the risk but don't remove the sign-off |
| Hosted platform that stores the notebook text as-is | Yes | Yes | Yes | ❌ A second copy of everything, outside the clinic, for no matching benefit |

**One decision for Marc:** the prenatal tag is itself health information (it implies pregnancy).
- **(a) Keep it** as a routing tag that's never displayed (current design). It protects the client if the desk ticks "any" by mistake.
- **(b) Don't keep it.** The desk picks "Amira or Kelsey" directly. The system then holds **zero** health data, but the safety net is gone.

Recommendation: (a), written into the one-pager. Not a lawyer's view; Julie has read up on PHIPAA and should check it.

### 16.1 Making new rules without keeping health details (your follow-up, §15.1)

A new routing rule needs two things. Neither needs the system to keep who has which condition.

| Need | How it's met | Health data kept |
|---|---|---|
| **Deciding whether a rule is worth making** ("do we get enough post-op clients to route them?") | (1) The rule is a **clinic decision by Marc**, as the prenatal rule was; it came from training, not from data. (2) If numbers help, the report adds **anonymous category counts** while parsing, e.g. "this month: post-op 4 lines, pregnancy 2, accident claim 3". No names, no line numbers, no dates. (3) For detail, Marc and the therapists look at Kneadly's intake forms, where health records already live | Counts only |
| **Applying the rule once it exists** | The therapist **tag** and the routing words go into the settings (§15 #2). New cards get a routing chip (e.g. `post-op-trained only`); old notebook lines are re-read with the new routing words on the next run | Only the routing tag, never the condition |
| **People already on the list when the rule starts** | Not a stored-data problem: the list turns over within **60 days** (staleness). Meanwhile the desk asks one routing question on the call, before booking | None |

What this rules out: storing each person's condition "in case a rule needs it later". That keeps a second copy of health details for a benefit that the 60-day turnover gets anyway.
