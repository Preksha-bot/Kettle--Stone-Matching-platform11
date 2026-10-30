# Step 3 — Combined facts: interviews + data (Kettle & Stone)

Combines [step1-discovery-facts.md](step1-discovery-facts.md) (what people said) and [step2-csv-facts.md](step2-csv-facts.md) (what the CSVs show). Facts only, no solutions or plans. **OPEN** = unknown.

**Verdicts:** ✅ data matches · 🟡 partly / nuance · ❌ data disagrees · ⚪ can't be tested with these files

---

## 1. Claim check — what people said vs. what the data shows

### 1a. Clinic & volume

| Claim | Who | Data (Sep 21 – Oct 17) | Verdict |
|---|---|---|---|
| ~150 appointments/week | Tanya | 156 · 161 · 158 · 120 (wk with Thanksgiving Mon Oct 12 closed) | ✅ |
| Open 9–8 weekdays, 9–3 Sat | Tanya | Earliest 09:00, latest end 20:00; Sat 09:00–15:00 | ✅ |
| Most book 60; some 90, 30, 45 | Tanya | 60: 59% · 30: 17% · 90: 14% · 45: 11% | ✅ |
| Marc works 3 days | Tanya / DN | Tue, Thu, Sat (58 appts) | ✅ |
| Each therapist works set days | DN | Every therapist on exactly 3–4 fixed weekdays | ✅ |
| Prices $115 / $160 / $70 | DN | `booked_value_cad` 115 (60), 160 (90), 70 (30) | ✅ (45 min **OPEN**) |

### 1b. Confirmations

| Claim | Who | Data | Verdict |
|---|---|---|---|
| "A bit more than half" confirm by text | Tanya | text C 53.8% | ✅ |
| Tanya phones the rest | Tanya | phone (Tanya) 17.3% · none 26.9% · same-day n/a 2.0% | ✅ (~27% never confirmed) |
| "Confirming doesn't mean anything" — late cancels are mostly people who said yes | Tanya | Late cancels: 26 of 36 had confirmed | ✅ |
| No-shows are usually the ones I couldn't reach | Tanya | No-shows: 7 of 8 unconfirmed | ✅ |
| "A few" cancel during the morning calls | Tanya | 14 cancels via morning call (5 late, 9 with ≥ 24 h notice) | ✅ |
| ~1/3 pick up; half confirm by text after voicemail | Tanya | No call-outcome data | ⚪ |

### 1c. Cancellations — volume & pattern

| Claim | Who | Data | Verdict |
|---|---|---|---|
| 10–12 late openings/week incl. no-shows | Tanya | Exactly 11 every week | ✅ |
| ~9 late cancels/week | DN | 36 ÷ 4 = 9 | ✅ |
| At least one every day | Tanya | 19 of 23 days; none on 3 Saturdays + Tue Oct 13 (day after Thanksgiving); max 4/day | 🟡 (true for weekdays except 1) |
| Mondays and Fridays are worst | Tanya | Rate: **Thu 10.5%** · Mon 7.9% · Wed 7.8% · Fri 7.8% · Tue 6.4% · Sat 1.7% | ❌ Thursday is worst |
| December is worst ("four in one day. Twice.") | Tanya | December not in sample; Sep/Oct max = 4 in a day (twice) | ⚪ |
| Dave has had the most cancellations this fall | Tanya / DN | Dave 16 of 44 (13.9% of his appts vs 3–7% others) | ✅ |
| Dave's Thursdays are "patchy" / "falling apart" | Tanya | Dave Thu: 6 openings / 28 appts = 21% (his worst day) | ✅ |
| Cancels come "mostly at night" | Tanya | 23 of 36 arrived 21:00–07:59 (6 prev. evening + 17 same-day early) | ✅ |
| …or "an hour before" | Tanya | Under 2 h notice: 3 of 36 | 🟡 (happens, but rare) |
| Online cancels mostly at night | Tanya | All 11 online late cancels arrived between 21:36 and 06:50 | ✅ |
| Overnight voicemails waiting at 8:00 | Tanya | 12 "voicemail (overnight)" late cancels | ✅ |

### 1d. Refills

| Claim | Who | Data | Verdict |
|---|---|---|---|
| ~3 refilled/week ("maybe 4 on a good week") | Tanya | 12 in 4 weeks = 3/week | ✅ |
| "I'd have said half" | Marc | 12 / 44 = 27% (33% of late cancels) | ❌ |
| Refills come from the book, luck (regular calls), or online overnight | Tanya | Waitlist 4 · client happened to call 5 · rebooked online 3 | ✅ |
| Online only refills when cancelled the night before | Tanya | All 3 online refills cancelled 21:58 / 00:45 / 03:00 | ✅ |
| No-shows are never offered | DN | 0 of 8 refilled; answer key = "none" for all 8 | ✅ |
| "The mornings, I mostly write off" | Tanya | 4 openings started before 10:30: 2 refilled (O15 by a client call, O23 from waitlist booked 08:28) | 🟡 |
| First real breather ~10:30; "nobody" acts before 10:30 | Tanya / FU | All 4 waitlist refills booked **08:28, 08:42, 09:09, 09:42** | ❌ data shows desk refilling before 10:30 |
| Gives up when too late for therapist to start | Tanya | Shortest refill: booked 1.8 h before start (O23); answer key = nobody for ~1h15 notice (O31, O40) | ✅ |
| Desk links refills ("rebooked into") — "mostly" | Tanya / FU | 12 of 12 refills linked in the sample | ✅ |
| Weekly loss "$1,500 a week" | Marc | Unfilled booked value **$920/week**; total late-opening value only $1,265/week | ❌ |
| ~$920/week unfilled | DN | $3,680 ÷ 4 = $920 | ✅ |

### 1e. Late fee

| Claim | Who | Data | Verdict |
|---|---|---|---|
| "We charge it" | Marc | Charged 6 of 44 (14%) | ❌ |
| Late cancels "hardly ever"; no-shows "more" | Tanya | Late cancels 2 of 36 · No-shows 4 of 8 | ✅ |
| ~$86/week collected | DN | 6 × $57.50 = $345 ÷ 4 = $86 | ✅ |
| Fee = half the appointment | Tanya | All charges $57.50 on 60-min appts | ✅ |

### 1f. Green book (waitlist)

| Claim | Who | Data | Verdict |
|---|---|---|---|
| ~45 people | Tanya | 45 distinct people | ✅ |
| "Sixty names" | Marc | 60 **lines** (15 are repeats) | 🟡 counts lines, not people |
| Some at the top since July | Tanya | 4 lines from July (W01–W04) | ✅ |
| Repeat lines; newest is the right one | Tanya | 10 "duplicate of" verdicts; key: "newer line wins" | ✅ |
| > 2 months with no contact = gone | Tanya | 4 people (5 lines) marked stale for this | ✅ |
| Fellow moved to Halifax (per Kelsey) | Tanya | W23 "moved to Hfx?? Kelsey says" → stale | ✅ |
| Number not in service | Tanya | W50 Kim Belliveau (and her W13) → stale | ✅ |
| Mel got a Dave spot in Sept, never crossed off | Tanya | W15 → Melanie Arsenault, Dave, Sep 24 (O10) → stale | ✅ |
| Booked online → off | Tanya | W25 Steph Poirier → standing Tue with Kelsey (online Oct 2) → stale | ✅ |
| Nobody crosses anyone off | Tanya | All 4 waitlist-refill people still on list | ✅ |
| Fields: date, name, number, notes | Tanya | Columns: line, added, name, phone, notes | ✅ |
| No column for therapist/length/time/notice | Tanya | All of it in free-text `notes` | ✅ |
| Holds health info | Tanya / DN | 15 of 60 lines | ✅ |
| Some are new, not clients | Tanya | W37 "NEW client (intake form)"; no client ID column at all | ✅ |
| "text don't call" | Tanya | W24 "TEXT don't call", W44 "text only" | ✅ |
| "not Marc (neighbour)" | DN | W21 | ✅ |
| "Call his son" | DN | Not in the CSV | ⚪ not found |
| Drives in from Shediac; needs 3–4 h | Tanya | W14 "needs 3h, drives in from Shediac"; W49 "needs 4 hrs (2 kids)" | ✅ |
| Can come in 30 min, across the street | Tanya | W39 "30 min notice ok, works at the bank across the st"; W18 "can come in 30 min" | ✅ |
| Needs the day before (shift work) | Tanya | W27/W55 "next day only (shift work)" | ✅ |

### 1g. Matching rules & defaults

| Claim | Who | Answer-key evidence | Verdict |
|---|---|---|---|
| No length written = 1 hour | Tanya | Key reads unstated length as "1 hour" | ✅ |
| No notice written = "a couple of hours" | Tanya | O31 & O40 (~1h15 notice) → nobody, though people with no notice limit fit therapist/day | ✅ consistent |
| Pregnant → Amira or Kelsey only, even if "anyone" | Tanya / Marc | W10 "female" → Amira/Kelsey; W40 "Amira pref" → Amira or Kelsey; "Rachel doesn't take prenatal" | ✅ |
| Post-op usually Josée | Tanya | W14 post-op shoulder: "Josée only" | ✅ |
| "AB Dave" = anyone but Dave | Tanya | W33 → "anyone but Dave" | ✅ |
| "AM" = mornings | Tanya | W60, W33, W48 → "mornings" | ✅ |
| Order of offers: first come | Tanya | Key lists names "in list order" but a match ignores order | ⚪ order **OPEN** |

### 1h. Tanya's stories

| Story | Opening | Data | Verdict |
|---|---|---|---|
| Thu Oct 15, Dave 2:00, cancelled 10:40 by phone (fever), not filled | O39 | Thu, 14:00, Dave, 10:40, phone, 3.3 h, not refilled | ✅ |
| Gisèle (90), Pauline (Mon/Wed), Terry (Dave, landline), Normand (after 4), Mel (already placed) | W01, W02/W51, W03, W04/W47, W15 | All match notes; key: Gisèle, Terry, Mel stale | ✅ |
| "People further down… on page three" would have taken it | O39 key | W46 Shawn Duguay, W53 Luc Bernard, W57 Lise Gautreau | ✅ |
| End-Sept Tuesday, Dave 11:00, voicemail 1:15 a.m., found at 10:50 | O16 | Tue Sep 29, 11:00, Dave, 01:16, voicemail, not refilled; key: W46, W60 | ✅ |

---

## 2. Combined fact tables

### 2a. Therapists

| Therapist | Days (data) | Appts (4 wk) | Late openings | Rate | Refilled | Training / preferences (interviews) |
|---|---|---|---|---|---|---|
| Dave Melanson | Mon Tue Thu Fri | 115 | 16 (Thu 6) | **13.9%** | 5 | Deep tissue; fan club + "AB Dave"; takes anyone; offered job elsewhere |
| Josée Landry | Mon Wed Thu Fri | 112 | 7 | 6.2% | 2 | Post-op training; wants to see who it is first |
| Rachel Thibodeau | Mon Wed Thu Fri | 105 | 7 | 6.7% | 1 | No prenatal (answer key) |
| Amira Haddad | Mon Tue Wed Sat | 103 | 7 | 6.8% | 2 | Prenatal training |
| Kelsey Babineau | Tue Wed Fri Sat | 102 | 5 | 4.9% | 1 | Prenatal training; takes anyone |
| Marc Cormier | Tue Thu Sat | 58 | 2 | 3.4% | 1 | Owner; has regulars (W18 Marcel Bujold) |

### 2b. Cancellations by timing

| Timing | Count (4 wk) | Typical channel | Refilled | Fee | Notes |
|---|---|---|---|---|---|
| ≥ 48 h | 17 | morning call 6, text reply 5, phone 4, online 2 | 0 — no other booking in that therapist's slot in the export | None | Not a "late opening" |
| 24–48 h | 5 | morning call 3, text reply 2 | 0 — same | None | Not a "late opening" |
| 12–24 h | 11 | online, overnight voicemail, text reply | — | Policy yes (rarely charged) | Slot can reopen online overnight |
| 6–12 h | 14 | overnight voicemail, online, morning call | — | Policy yes | Most early-morning arrivals |
| 2–6 h | 8 | phone, morning call | — | Policy yes | |
| < 2 h | 3 | phone, text reply | — | Policy yes | O31 & O40 → nobody could take it |
| No-show | 8 | — (marked at +15 min) | 0 of 8 | 4 charged / 4 waived | Never offered |
| **Late cancels refilled** | 12 of 36 | | median notice refilled 10.8 h vs not 7.5 h | | |

### 2c. Cancellations by channel (late openings only)

| Channel | Count | Refilled | When it arrives (interviews + data) |
|---|---|---|---|
| Voicemail (overnight) | 12 | 4 | Night/early morning; heard at 8:00 |
| Online (Kneadly) | 11 | 4 | Night; slot reopens online automatically |
| No-show | 8 | 0 | At start + 15 min |
| Phone | 5 | 1 | During the day, often < 4 h before |
| Morning call | 5 | 2 | 8:00–9:15 during confirmation calls |
| Text reply | 3 | 1 | Reply to reminder / clinic mobile |

### 2d. How refills happen

| Route | Count | Interview description | Data detail |
|---|---|---|---|
| Client happened to call | 5 | "A regular calls asking 'anything today?'" | Booked 0.3–9.2 h after cancel |
| Desk called down the waitlist | 4 | Green book, top down, one at a time | Booked 08:28–09:42; all 4 people still on list, now stale |
| Rebooked online | 3 | "Somebody grabs it overnight" | All overnight cancels |

### 2e. Green book — combined

| Item | Fact |
|---|---|
| Lines / people | 60 lines / 45 people (Tanya's 45 ✅, Marc's 60 = lines) |
| Status (answer key) | 30 active · 15 stale people (20 lines) · 10 duplicate lines |
| Stale reasons | > 2 months silent 4 · got in via late opening 4 · booked online 1 · moved/elsewhere 2 · need expired 3 · number dead 1 |
| Writers | Tanya, Bethany, therapists (pencil from Dave) |
| Formats | 2 date styles, no year · 6 phone styles + "same #" · short names & nicknames · accents dropped |
| Health details | 15 lines; book sits on counter |
| Link to Kneadly | None: no client ID, no phone in export → name match only |
| Active but fits no sample opening | W28, W54, W58 (90 only), W59 (45, Mon/Tue after 5) |
| Answer key names per opening | 0–8; median 4; 10 openings = nobody |

### 2f. Matching factors — with evidence

| Factor | Interview rule | Answer-key / data evidence |
|---|---|---|
| Therapist | "J only", "Dave only", "AB Dave", "female" | Key restricts by these; female = Amira, Josée, Kelsey, Rachel |
| Day | "not Thurs", "Mon or Wed", "Sat only" | Pauline excluded on Tue/Thu/Fri/Sat |
| Time | "AM", "after 4", "after 5", "lunch 12–1", "done by 2:30" | Normand excluded before 4:00 |
| Length | 60 default; "90", "45", "30 or 45" | 90-only people fit no 60-min opening |
| Notice | Default ~2 h; 30 min to day before | ~1h15 notice → nobody (O31, O40) |
| Clinic rule — pregnant | Amira or Kelsey only | Applied even to "Amira pref" and "female" |
| Clinic rule — post-op | Usually Josée | W14 Josée only |
| Out of date | > 2 months, moved, got a spot, booked online, need expired, dead number | 20 stale lines |
| Repeat lines | Newest wins | 10 duplicates merged |
| Therapist's say | Each can refuse (Marc); Josée wants to see | No data — **OPEN** |
| Who first | First asked (Tanya) / regulars / first to say yes (Marc) | Not decided — **OPEN** |

### 2g. Kneadly — combined

| Item | Interviews | Data |
|---|---|---|
| Online booking | Clients book & cancel online | 57.5% of bookings online; 11 online late cancels |
| Reminders "reply C" 2 days before | Yes | `confirmation` = text C for 53.8% |
| Weekly export content | When booked, cancelled, how, rebooked into | 18 columns incl. `booked_at`, `cancelled_at`, `cancel_via`, `late_fee`, `rebooked_into`, `desk_notes` |
| Not exported | Emails, intake, treatment notes | Also no phone, no text-consent flag |
| Built-in waitlist | OFF; 1 therapist + 1 day; emailed everyone every opening | No data |
| Daily report | Setting in owner account, Marc only | – |
| Slot hold | No; can block time by hand | – |
| Higher plan | ~+$45/month (unchecked) | – |
| API / AI tools / cancel alert / data location | **OPEN** | – |

### 2h. Money

| Item | Value | Source |
|---|---|---|
| Late-opening booked value | $5,060 / 4 wk ($1,265/wk) | Data |
| Unfilled | $3,680 / 4 wk (**$920/wk**) | Data |
| Refilled | $1,380 / 4 wk | Data |
| Split | Clinic 40% / therapist 60% | Marc |
| Clinic share of unfilled | ~$368/wk | Data × split |
| Fees collected | $345 / 4 wk ($86/wk) | Data |
| Tanya's cost | $21/h ($24 loaded) | Marc |
| Budget | $50/month fine · $150 no | Marc |
| Kneadly now | "a hundred and something"/month | Tanya |
| Target | 70% refilled ≈ 31 of 44 (now 12) | FU / DN |

---

## 3. Conflicts — status after combining

| Topic | Said | Data | Status |
|---|---|---|---|
| Refills | Tanya 3/wk vs Marc "half" | 3/wk (27%) | Resolved → Tanya |
| Weekly loss | Marc $1,500 | $920 unfilled | Resolved → data; Marc's figure exceeds even total late-opening value |
| Waitlist size | Tanya 45 vs Marc 60 | 45 people, 60 lines | Resolved → both, different units |
| Late fee | Marc "we charge it" vs Tanya "hardly ever" | 2/36 late cancels charged | Resolved → Tanya |
| Worst days | Tanya Mon & Fri | Thursday (driven by Dave: 6) | Resolved → data disagrees |
| Desk can't act before 10:30 | Tanya / FU | 4 waitlist refills booked 08:28–09:42 | **Unresolved** |
| "Or an hour before" | Tanya | 3 of 36 under 2 h | Partly — rare in sample |
| Offer order | Tanya first-asked vs Marc regulars/first yes | – | **Unresolved — client's call** |

## 4. Facts found in only one source

| Fact | Only in |
|---|---|
| "Call his son" preference | DN (not in waitlist CSV) |
| Mon Oct 12 closed (Thanksgiving) | Data |
| Therapists' exact working days | Data |
| 22 cancellations with ≥ 24 h notice (not late openings) | Data |
| Lead time median 9.7 days | Data |
| Double booking last spring | Interviews |
| Kneadly waitlist behaviour | Interviews |
| Call outcomes (1/3 pick up) | Interviews |
| December peak | Interviews |
| Desk notes: running late, ins direct bill, parking pass, gift cert | Data |

## 5. Open questions (combined)

| # | Question | Who / where |
|---|---|---|
| 1 | Kneadly API, AI tools, cancel alert, data location, desk browser | Julie / Kneadly |
| 2 | Exact higher-plan cost (est. +$45/mo) and whether needed | Julie |
| 3 | Daily export: approval time | Marc (needs 1-page note) |
| 4 | Offer order when several fit | Marc + Tanya |
| 5 | How therapists' say works in practice | Therapists / Marc |
| 6 | Text consent for waitlist people; phone/consent not in export | Julie |
| 7 | The 22 ≥ 24 h cancellations show no `rebooked_into` link and no other booking in the same therapist + time slot. Did those slots really stay empty, or does the export leave such rebookings out? | Julie / export |
| 8 | How desk refilled before 10:30 despite "nobody before 10:30" | Tanya |
| 9 | Price of 45-min session | Clinic |
| 10 | Record of past offer yes/no | None known |
| 11 | December and other months (sample = 4 weeks only) | More exports |
| 12 | Who keeps a cleaned-up list current | Clinic |
