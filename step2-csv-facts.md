# Step 2 — CSV data facts (Kettle & Stone)

Facts and stats from the 4 CSV files only. No solutions or plans. Numbers computed directly from the files (no hand edits). Comparison with the interviews is left for Step 3.

All files: UTF-8, comma-separated, header row, quoted fields where they contain commas.

---

## 0. File inventory

| File | Rows (excl. header) | Columns | One row = | Period / as-of | Key column |
|---|---|---|---|---|---|
| `appointments-2026-09-21-to-2026-10-17.csv` | 595 | 18 | One booked appointment | Mon Sep 21 – Sat Oct 17, 2026 (23 working days) | `appointment_id` (A-24001…A-24595) |
| `late-openings-2026-09-21-to-2026-10-17.csv` | 44 | 15 | One late cancel or no-show | Same 4 weeks | `opening_id` (O01…O44) |
| `waitlist-2026-10-21.csv` | 60 | 5 | One handwritten line of the green book | As of Wed Oct 21 | `line` (1…60) |
| `answer-key-tanya.csv` | 104 | 5 | One opening (44) **or** one waitlist line (60) | Marked Oct 22 against list as of Oct 21 | `id` (O01…O44, W01…W60) |

---

## 1. Appointments file

### 1a. Columns

| Column | Format / values | Blanks |
|---|---|---|
| `appointment_id` | A-24001 … A-24595, unique | 0 |
| `date` | YYYY-MM-DD; 23 distinct dates | 0 |
| `start`, `end` | HH:MM; earliest 09:00, latest end 20:00 (Sat 09:00–15:00) | 0 |
| `length_min` | 30 / 45 / 60 / 90 | 0 |
| `service` | "Massage therapy {30/45/60/90} min" — always matches `length_min` | 0 |
| `therapist` | 6 full names | 0 |
| `client_id` | K-xxxx; 283 distinct | 0 |
| `client_name` | 283 distinct (1 name per id) | 0 |
| `booked_at` | YYYY-MM-DD HH:MM | 0 |
| `booked_via` | online / phone / desk | 0 |
| `confirmation` | text C / phone (Tanya) / none / n/a (same day) | 0 |
| `status` | Completed / Late cancel / Cancelled / No-show | 0 |
| `cancelled_at` | YYYY-MM-DD HH:MM (no-shows = start + 15 min) | 529 |
| `cancel_via` | online (Kneadly) / voicemail (overnight) / phone / text reply / morning call / no-show | 529 |
| `late_fee` | waived / charged $57.50 | 551 |
| `rebooked_into` | appointment_id of the refill booking | 583 (12 filled) |
| `desk_notes` | Free text, 20 distinct values | 551 (44 filled) |

### 1b. Volume

| Measure | Value |
|---|---|
| Appointments total | 595 |
| Per ISO week | Wk39: 156 · Wk40: 161 · Wk41: 158 · Wk42: 120 |
| Missing day | **Mon Oct 12** — no appointments (Canadian Thanksgiving) → Wk42 lower |
| Per working day | min 14 · max 32 · mean 25.9 · median 28 |
| By weekday | Mon 89 · Tue 109 · Wed 116 · Thu 105 · Fri 116 · Sat 60 |
| Distinct clients | 283 · visits per client: min 1, max 6, mean 2.1, median 2 |

### 1c. Lengths

| Length | Count | % |
|---|---|---|
| 60 min | 350 | 58.8% |
| 30 min | 99 | 16.6% |
| 90 min | 83 | 13.9% |
| 45 min | 63 | 10.6% |

### 1d. Therapists — working days (from data)

| Therapist | Appts | Mon | Tue | Wed | Thu | Fri | Sat | Days worked |
|---|---|---|---|---|---|---|---|---|
| Dave Melanson | 115 | 23 | 33 | – | 28 | 31 | – | Mon Tue Thu Fri |
| Josée Landry | 112 | 21 | – | 29 | 32 | 30 | – | Mon Wed Thu Fri |
| Rachel Thibodeau | 105 | 21 | – | 31 | 28 | 25 | – | Mon Wed Thu Fri |
| Amira Haddad | 103 | 24 | 28 | 29 | – | – | 22 | Mon Tue Wed Sat |
| Kelsey Babineau | 102 | – | 27 | 27 | – | 30 | 18 | Tue Wed Fri Sat |
| Marc Cormier | 58 | – | 21 | – | 17 | – | 20 | Tue Thu Sat |

Saturday therapists: Amira, Kelsey, Marc only.

### 1e. Booking & confirmation

| Measure | Value |
|---|---|
| booked_via | online 342 (57.5%) · phone 137 (23.0%) · desk 116 (19.5%) |
| Lead time (booked → start) | min 0.1 d · max 35.4 d · mean 12.2 d · median 9.7 d |
| Lead time by channel (median) | online 9.6 d · phone 10.2 d · desk 7.2 d |
| confirmation | text C 320 (53.8%) · none 160 (26.9%) · phone (Tanya) 103 (17.3%) · n/a same day 12 (2.0%) |

### 1f. Status & cancellations

| Status | Count | Notice before start (hours) | cancel_via |
|---|---|---|---|
| Completed | 529 (88.9%) | – | – |
| Late cancel (< 24 h) | 36 | min 1.2 · max 19.3 · mean 8.4 · median 8.0 | voicemail (overnight) 12 · online 11 · phone 5 · morning call 5 · text reply 3 |
| Cancelled (≥ 24 h) | 22 | min 29.9 · max 138.9 · mean 80.6 · median 82.1 | morning call 9 · text reply 7 · phone 4 · online 2 |
| No-show | 8 | logged at start + 15 min | no-show 8 |

| Notice band (all 66 non-completed) | Count |
|---|---|
| ≥ 48 h | 17 |
| 24–48 h | 5 |
| 12–24 h | 11 |
| 6–12 h | 14 |
| 2–6 h | 8 |
| < 2 h | 3 |
| No-show | 8 |

| Confirmation vs. status | Completed | Late cancel | Cancelled | No-show |
|---|---|---|---|---|
| text C | 282 | 23 | 14 | 1 |
| phone (Tanya) | 97 | 3 | 3 | 0 |
| none | 138 | 10 | 5 | 7 |
| n/a (same day) | 12 | 0 | 0 | 0 |

### 1g. Late fee

| Status | Waived | Charged $57.50 |
|---|---|---|
| Late cancel (36) | 34 | 2 |
| No-show (8) | 4 | 4 |
| Cancelled ≥ 24 h (22) | blank (no fee) | – |
| **Total charged** | | **6 × $57.50 = $345 in 4 weeks (~$86/week)** |

All 6 charged fees were on 60-min appointments.

### 1h. Refill links & desk notes

| Measure | Value |
|---|---|
| `rebooked_into` filled | 12 rows — all on late openings; each points to the next ID (e.g. A-24038 → A-24039) |
| Refill bookings' desk_notes | "slot reopened online" 3 · "filled from waitlist" 4 · "client called asking for anything today" 5 |
| Other desk_notes | running 10 min late, called (8) · ins direct bill (7) · parking pass given (5) · gift cert (3) · first visit, intake done (3) · wants same time next mo (2) · pd cash (2) · standing Tues (2) |
| Health info in export | None seen in desk_notes |
| ≥ 24 h cancellations refilled? | No `rebooked_into` on any of the 22, and no other booking overlaps the same therapist + time in the export (0 of 22). **OPEN** whether they stayed empty or the export omits it |

---

## 2. Late-openings file

### 2a. Columns

| Column | Format / values |
|---|---|
| `opening_id` | O01…O44 |
| `appointment_id` | Links to appointments file |
| `date`, `day`, `start`, `length_min`, `therapist` | Copied from the appointment |
| `kind` | late cancel (36) / no-show (8) |
| `cancelled_at` | YYYY-MM-DD HH:MM |
| `hours_notice` | Decimal hours from cancel to start (0.0 for no-shows) |
| `heard_via` | Same values as `cancel_via` in appointments |
| `client_had_confirmed` | yes (text) / yes (phone) / no |
| `refilled` | yes / no |
| `refilled_how` | rebooked online / desk called down the waitlist / a client happened to call / blank |
| `booked_value_cad` | 70 / 115 / 160 |

### 2b. Stats

| Measure | Value |
|---|---|
| Openings | 44 = 36 late cancels + 8 no-shows |
| Per week | 11 · 11 · 11 · 11 |
| Refilled | **12 of 44 (27.3%)**; of late cancels only: 12 of 36 (33.3%); no-shows refilled: 0 of 8 |
| refilled_how | client happened to call 5 · desk called down the waitlist 4 · rebooked online 3 |
| Lengths | 60 min 40 · 90 min 2 · 30 min 2 · 45 min 0 |
| Booked value | Total $5,060 (~$1,265/week) · unfilled $3,680 (**~$920/week**) · refilled $1,380 |
| hours_notice (late cancels) | min 1.2 · max 19.3 · mean 8.4 · median 8.0 |
| hours_notice refilled vs not | refilled: median 10.8 (min 3.4) · not refilled: median 7.5 (min 1.2) |
| Confirmed before cancelling | Late cancels: 26 of 36 confirmed (yes text/phone) · No-shows: 1 of 8 confirmed |

### 2c. By therapist

| Therapist | Openings | Refilled | Openings ÷ their appts |
|---|---|---|---|
| Dave Melanson | 16 (36%) | 5 | **13.9%** |
| Josée Landry | 7 | 2 | 6.2% |
| Amira Haddad | 7 | 2 | 6.8% |
| Rachel Thibodeau | 7 | 1 | 6.7% |
| Kelsey Babineau | 5 | 1 | 4.9% |
| Marc Cormier | 2 | 1 | 3.4% |

### 2d. By weekday

| Day | Openings | Openings ÷ appts that day |
|---|---|---|
| Thu | 11 | **10.5%** |
| Wed | 9 | 7.8% |
| Fri | 9 | 7.8% |
| Mon | 7 | 7.9% |
| Tue | 7 | 6.4% |
| Sat | 1 | 1.7% |

### 2e. Timing

| Measure | Value |
|---|---|
| Opening start time | 09h:1 · 10h:3 · 11h:9 · 12h:6 · 13h:7 · 14h:5 · 15h:6 · 16h:3 · 17h:2 · 18h:2 — 22 of 44 between 11:00–13:59 |
| Openings starting before 10:30 / before 12:00 | 4 / 13 |
| When late cancels arrived (36) | previous evening/night: 7 · same day 00:00–07:59: 17 · same day 08:00–10:29: 7 · same day 10:30+: 5 |
| Arrived before 10:30 (incl. overnight) | **31 of 36 (86%)** |
| Refilled by arrival time | previous day 4/7 · 00:00–07:59 5/17 · 08:00–10:29 2/7 · 10:30+ 1/5 |
| heard_via × refilled | voicemail (overnight) 4/12 · online 4/11 · morning call 2/5 · text reply 1/3 · phone 1/5 · no-show 0/8 |
| "rebooked online" refills | 3 — all cancelled overnight (21:58, 00:45, 03:00) |

### 2f. Refills — time from cancel to new booking

| Opening | How | Cancel → refill booked (h) | Refill booked → start (h) |
|---|---|---|---|
| O04 | online | 4.3 | 4.9 |
| O10 | waitlist | 3.9 | 4.3 |
| O11 | client called | 8.3 | 4.4 |
| O12 | online | 3.1 | 10.5 |
| O15 | client called | 0.3 | 18.9 |
| O22 | waitlist | 11.1 | 4.5 |
| O23 | waitlist | 4.9 | 1.8 |
| O25 | client called | 9.2 | 3.4 |
| O33 | client called | 0.5 | 3.0 |
| O35 | waitlist | 0.8 | 5.3 |
| O42 | client called | 0.7 | 4.4 |
| O44 | online | 4.3 | 8.9 |

Waitlist refills were booked at 08:28 (O23), 08:42 (O22), 09:09 (O10), 09:42 (O35) — all before 10:30.

---

## 3. Waitlist file

### 3a. Columns

| Column | Format / values |
|---|---|
| `line` | 1–60, order written |
| `added` | Two formats, alternating: "Jul 6" (30) and "7/14" (30); **no year**; range Jul 6 – Oct 19 |
| `name` | Full or short ("Lynn S.", "Pauline B.", "Tina S"); nicknames ("Mel", "Bob", "Jen", "Steph"); accents dropped (Gisele, Hebert, Joel, Helene) |
| `phone` | 6 formats: 999-999-9999 (52), 999 999 9999 (3), "same #" (2), (999) 999-9999, (999)999-9999, 9999999999 |
| `notes` | Free text shorthand: therapist, length, day, time, notice, health, contact preference, temporary dates |

### 3b. Stats

| Measure | Value |
|---|---|
| Lines | 60 |
| Distinct people | **45** (60 lines − 15 repeat lines) |
| Phone numbers used on 2 lines | 12 numbers + 2 "same #" lines |
| Lines by month added | Jul 4 · Aug 12 · Sep 26 · Oct 18 |
| Lines with health details | 15 (sciatica, low back ×2, knee replacement, hip replacement, pregnant ×2, post-op shoulder, fibro, MVA claim, TMJ, migraines, concussion (MVA), hamstring, cancer survivor) |
| Lines naming a specific therapist / "only" | e.g. "Dave only" ×3, "J only", "Marc only", "Kelsey only", "Amira only", "Rachel only" |
| Lines with "female" | 5 |
| Lines with "AB Dave" / "anyone but Dave" / "any but Dave" | 3 |
| Contact preference | "TEXT don't call" (W24), "text only" (W44), "landline" (W03) |
| Explicitly new client | W37 Greg Wilson ("NEW client (intake form)") |
| Temporary limits in notes | until end of Sept (W11), until Oct 10 (W32), away until Oct 9 (W22), wedding Oct 3 (W17/W34) |
| Lines saying "take off" / gone | W29 ("going to someone in Dieppe now, take off"), W23 ("moved to Hfx??"), W50 ("# not in service??") |

---

## 4. Answer-key file

### 4a. Structure

| Column | Values |
|---|---|
| `id` | O01–O44 (openings) then W01–W60 (waitlist lines) |
| `type` | "opening" (44) / "waitlist line" (60) |
| `answer` | Openings: "Wnn Name; Wnn Name…" in list order, or "none". Lines: active / stale / duplicate of Wnn |
| `marked_by` | Tanya Boudreau (all 104) |
| `note` | Openings: count + "Careful: not X (reason)". Lines: reason + what they can take |

### 4b. Opening answers

| Measure | Value |
|---|---|
| Openings with "none" | **10** = 8 no-shows ("no time to offer it") + 2 late cancels with ~1h15 notice (O31, O40: nobody could take it) |
| Openings with names | 34 |
| Names per opening | min 1 · max 8 · mean 4.1 · median 4 |
| Distribution (names → openings) | 0→10 · 1→2 · 2→5 · 3→6 · 4→7 · 5→6 · 6→4 · 7→3 · 8→1 |
| Openings with ≤ 3 names | 13 (plus 10 "none") |
| Most frequent names | W46 Shawn Duguay 13 · W42 Amanda Bourgeois 11 · W57 Lise Gautreau 11 · W49 Andrea Pitre 10 · W40 Vanessa Caissie 9 |
| Common "Careful" exclusions | Pauline Bastarache (day/AM limits), Ray Daigle (stale), Terry Hébert (stale), Normand Vienneau (only from 4:00), Claudette Richard (stale), Sarah Collette (pregnant → not Rachel) |
| Already filled at the time by a now-stale line | O10 Melanie Arsenault, O22 Robert Gaudet, O23 Jennifer Leblanc, O35 Claudette Richard |

### 4c. Waitlist line verdicts

| Verdict | Lines | People |
|---|---|---|
| Active | 30 | 30 |
| Duplicate of a newer line (newer wins) | 10 | (merged into active) |
| Stale | 20 | 15 |
| **Total** | **60** | **45** |

| Stale reason | People (lines) |
|---|---|
| > 2 months, no call back (added Jul 6 / Jul 20 / Aug 4+11 / Aug 15) | 4 (5) |
| Got in via a late opening, never crossed off | 4 (6) — Claudette Richard, Mel Arsenault, Jen Leblanc, Bob Gaudet |
| Booked themselves online (standing Tues with Kelsey) | 1 (1) — Steph Poirier |
| Moved / went elsewhere (Halifax, Dieppe) | 2 (2) |
| Time-limited need passed (end Sept, Oct 10, wedding Oct 3) | 3 (4) |
| Number not in service | 1 (2) |

| Active lines that fit **no** opening | W28 (90 only, Sat), W54 (90 only, after 4, not Dave), W58 (Dave, 90 only, Tue/Fri), W59 (45, Mon/Tue after 5) |
|---|---|

Readings Tanya applied (from key notes): no length → 1 hour; "pregnant" → Amira or Kelsey only (even "Amira pref"); "after 4" → starting 4:00 or later; "lunch 12-1" + 30 min → starts 12:00–12:30; "2-3 hrs" notice → 3 hours.

---

## 5. How the files relate to each other

| Link | Key | Check result |
|---|---|---|
| Late openings → Appointments | `appointment_id` | All 44 match; date, start, length, therapist, cancelled_at identical (0 mismatches) |
| Appointments "Late cancel" + "No-show" | `status` | 36 + 8 = 44 = all rows in late-openings file |
| Appointments "Cancelled" (≥ 24 h) | `status` | 22 rows, **not** in late-openings file |
| Late openings `refilled = yes` → refill booking | `rebooked_into` | 12 of 12 have a link; desk_notes on the new booking match `refilled_how` |
| Answer key O-rows → Late openings | `opening_id` | 44 of 44 |
| Answer key W-rows → Waitlist | `line` (Wnn = line nn) | 60 of 60 |
| Waitlist → Appointments | Name (no shared ID; waitlist has no client_id) | Matches only by name/nickname: W15 Mel → Melanie Arsenault (O10 refill, Sep 24, Dave) · W21 Bob → Robert Gaudet (O22 refill, Oct 2, Dave) · W19/W35 Jen → Jennifer Leblanc (O23 refill, Oct 5, Amira) · W09/W31 → Claudette Richard (O35 refill, Oct 14, Rachel) · W25 Steph → Stephanie Poirier (online Oct 2, standing Tue with Kelsey from Oct 6) · W18 Marcel Bujold (completed with Marc Sep 26, booked Aug 22 — still active) |
| Waitlist → Appointments | Phone | Appointments file has **no phone column** |
| All 4 refill-from-waitlist people | – | Now marked **stale** in answer key (never crossed off) |
| Story check: Oct 15 Dave 14:00 | O39 | Phone, 10:40, 3.3 h notice, not refilled. Key: W46, W53, W57 (lines on the last page) |
| Story check: late-Sept Tue Dave 11:00 voicemail 1:15 a.m. | O16 | Tue Sep 29, cancelled 01:16, voicemail, not refilled. Key: W46, W60 |

---

## 6. Data gaps (not in any CSV)

| Missing | Note |
|---|---|
| Client phone / email / text consent | Not in appointments export |
| Client ID on waitlist | Waitlist ↔ appointments only joinable by name |
| Year on waitlist dates | Implied 2026 |
| Who answered yes/no to past offers | No column anywhere |
| Whether ≥ 24 h cancellations were rebooked | No link used and no overlapping booking found (0 of 22) |
| Therapist accept/decline preferences | Not in any file |
| Price for 45 min | `booked_value_cad` has no 45-min opening |
| Regular-client flag | Not a column (visit count derivable: max 6 in 4 weeks) |
