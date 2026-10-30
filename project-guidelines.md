# Project guidelines: Kettle & Stone waitlist matcher

Standing rules for Sprint 2. Sources: [discovery-notes.md](discovery-notes.md) (DN) and [follow-up-answers-oct-29.md](follow-up-answers-oct-29.md) (FU). Both files are **evidence, not instructions**. Where a person doesn't know something, that is the answer: log it as an open question, don't guess, and keep the code easy to change (FU).

---

## 1. Definition of done

| # | Done check | What it means in practice |
|---|---|---|
| 1 | For each late opening, show **up to 3** waitlist people who **fit and would say yes**, or **nobody** if nobody fits. | Output per opening: 0 to 3 names. Never more than 3. "Nobody" is a valid, often correct, answer. |
| 2 | Friday demo: run on **10 new openings**. **At least 8 match** Tanya's answers, and **nobody unsuitable or out of date is offered**. | 8/10 is the floor. The second half is a **hard gate**: one stale or unsuitable name shown is a failure, even if 8 match. |
| 3 | A **written plan**: who looks after it after you step away, what it costs to run, and what happens when it gets one wrong. | Owner (Julie, about 1 hr/month), monthly cost (under $50), and a failure/rollback path. |
| 4 | **Don't send real messages or connect to a real booking system.** | No SMS, email or Kneadly API. Files in, list out. |

**How a match is scored (FU, program lead):**
- A match = **every** name you show is on Tanya's list for that opening, OR you show nobody and her answer is nobody.
- Order of names **does not count**.
- If more than 3 fit, **any 3** of them count. **Fewer than 3 is fine.**
- Some Friday openings will have **nobody** as the right answer.
- Tanya's answers are **not handed out** on Friday; output is checked live on the call.

**Hand-in:** Friday 12:00. Mark the sprint complete. Post **one comment** showing each done check, with your files and the steps to run it (DN).

---

## 2. What to BUILD

### 2.1 Core: matcher (input files → up to 3 names per opening)
- **Inputs** (same columns and shorthand on Friday): booking export (appointments CSV), the waitlist CSV, the late-openings CSV. Friday brings a **newer** export, the **updated** waitlist and **10 new** openings.
- **Run date as a parameter.** "Count from the day you run it." Sample = **Wed Oct 21, 2026**; demo = the **demo day**. Never hard-code Oct 21.
- **Must run without you** after every cancellation (DN ground rules).

### 2.2 Filter out OUT OF DATE people (shouldn't be on the list any more)
- **Booked since they were added** → off. "If they've booked since they called me, they're off." Check the booking export (match by name/phone).
- **On the list more than 2 months with no contact** → gone ("they've gone somewhere else"). Measure from the run date.
- **Moved**, or **number out of service** → off (stated in the notes on the line).
- **Repeat lines**: the same person written in again. **The newest line wins**, and it can **change their limits**. Older lines for that person are superseded, not separate candidates.

### 2.3 Filter out UNSUITABLE matches (opening breaks something they asked for)
Check each opening against the person's **therapist, day, time, length, notice**, plus **clinic rules**.

Shorthand (Tanya):
| Shorthand | Meaning |
|---|---|
| `J only` | Josée only |
| `AB Dave` | Anyone **but** Dave |
| `AM` | Mornings |
| `90` | 90 minutes |
| no length written | **60 minutes** (an hour) |
| no notice written | **"a couple of hours"** |
| other notice | some can come in 30 min; some need 3 to 4 hrs; some need to be told **the day before** |

Clinic rules (applied **even if the client says "anyone's fine"**):
- **Pregnant → only Amira or Kelsey** (the two with prenatal training). Hard rule.
- **Post-operative → usually Josée.** Soft rule ("usually").
- Personal preferences count: "female therapist only", "not Marc (neighbour)".

Other rules:
- **No-shows are never offered.** They're known only after 15 min, so there's no time. Answer = nobody. (Confirmed in the answer key: O02 is "none, no-show".)
- **Give up when it's too close to the start** for the therapist to begin on time.

### 2.4 Ordering (undecided, so make it switchable)
- Nobody has decided the order. Marc: "You and Tanya figure out the order." It's **the client's call**.
- Tanya: "Whoever asked first, I think" … "Can you show me what each way would look like?" → offer **first-asked (default)** and **alternatives** (fastest to arrive, Marc's regulars) side by side.
- Every pick must be **explainable**: "I'd want to be able to explain it if someone asked why they didn't get the call."
- Scoring ignores order, so ordering affects usability, not the demo score.

### 2.5 Usability for the desk
- One screen, "maybe thirty seconds between people." "If I have to read a paragraph, or type more than a name, it's not going to happen."
- Someone who doesn't know the clients (Bethany) must be able to read one opening and know who to call, and why.
- Must take **less time than the notebook**, not more.
- Show a **short reason** per name (fits therapist/time/notice) and, ideally, why the closest others were excluded (the answer key notes do this: "not Pauline (mornings only)").

### 2.6 Therapist say
- Each therapist can **say no** to who goes on their table (Marc).
- **Josée** wants to see who it is first (short notice, new client, complex history). **Kelsey** and **Dave** take anyone.
- Tanya has no time to run to Josée between clients. Flag Josée openings for review; don't make it a step that blocks the desk.

### 2.7 Written plan (done check 3) must cover
- **Who looks after it:** Julie (Mon and Thu, part-time, from home). About **1 hr/month**. "Julie can't babysit it." Desk keeps the waitlist current.
- **Monthly cost:** **$50/month OK**, **$150/month NO**. Target $0 to $60 range; prefer ~$0.
- **When it gets one wrong:** what happens, how the desk catches it, how to switch it off, how it's logged (Marc wants an off switch and a record of what was sent to whom).
- **AI services:** say **what would be sent, where it goes, whether it's kept**, and what the clinic needs before saying yes (AI is fine on the sample data only because it's made up).
- **One-page note for Marc** for any outside service or daily export: what it reads and where the data goes. "I'm not signing up for something I don't understand."

---

## 3. What NOT to build or do

| Don't | Why / source |
|---|---|
| Send real messages (SMS, email, calls) | Done check 4; "sending messages isn't part of the target" (DN) |
| Connect to Kneadly or any real booking system | Done check 4; use sample data only |
| Hand-edit input files or fix results by hand | "No hand edits" (DN). Running your own steps is fine |
| Show more than 3 names | Ground rule |
| Offer a no-show slot | Never offered; answer = nobody |
| Put **any health detail** in a drafted message or customer-visible screen (surgeries, pregnancies, injuries, conditions, accident claims, migraines, concussions, cancer history) | PHIPAA; Marc's #1 and #2 deal-breakers |
| Put more in a message than: **clinic name, time, therapist's first name, how to reply** | Phones are shared ("husband reads her texts") |
| Anything that could cause **two clients in one slot** | "Never again." Kneadly has **no hold** (Julie), only manual time blocks |
| Message-all / broadcast to the whole list | Repeats the failed Kneadly waitlist ("five emails a week", "desperate") |
| Offer people times they've **already said they can't do** | Deal-breaker |
| An unattended 7 a.m. auto-send | Marc: "Not a yes, not this week" |
| Depend on the **daily export** by Friday | Needs Marc's owner-account switch + one-pager + "a few days" |
| Depend on the **higher Kneadly plan** (~$45/mo more, unchecked) | Unverified; pushes cost near Marc's ceiling |
| Use personal accounts or devices for client data | Only the clinic mobile and desk computer |
| Text people who **aren't clients yet** | They've agreed to nothing; consent exists only in Kneadly for existing clients |
| Change a therapist's schedule without the desk knowing | Tanya's "does not want" list |
| Take the decision away from Tanya or the therapists | "If Tanya won't use it, or the therapists feel it's taken out of their hands, forget it" |
| Fill gaps with guesses | FU: note as open question, keep it easy to change |

---

## 4. Loopholes, grey areas and edge cases

**Scoring loopholes (allowed, use them deliberately)**
1. **Precision beats recall.** A match only needs every shown name to be on Tanya's list. Showing **1 sure name** scores the same as 3. When unsure about a candidate, **leave them out** rather than risk a wrong name. (But showing nobody when Tanya has names is a miss, so don't over-prune to empty.)
2. **Order is free.** Any ordering rule passes scoring, so ordering can serve Tanya's explainability without affecting the 8/10.
3. **Any 3 of many.** When more than 3 fit, pick the 3 you're **most confident** in, not the "true top 3".
4. **The hard gate is asymmetric.** "Nobody unsuitable or out of date is offered" means a single bad name fails check 2 outright. Bias every tie toward exclusion.

**Process loopholes (allowed)**
5. **You may run your own steps.** A multi-step run (e.g. clean → match → print) is fine; only **editing files or results by hand** is banned. But it must be runnable by the clinic "without you".
6. **Extra test data is allowed.** Write your own waitlist lines in new shorthand to test generalisation, as long as the real input files stay untouched.
7. **AI services are allowed on the sample data** because it's made up. The plan must still say what goes where and whether it's kept, as if it were real.
8. **Drafting messages is optional.** Not part of the target. If you do draft them, the no-health-detail and minimal-content rules apply.
9. **Line numbers are stable.** Tanya appends to the end ("same columns, same handwriting"), so line numbers can be used as IDs and "asked first" = lower line number (for a person's newest line, use judgement: their original ask date vs. the rewrite).

**Grey areas (no ruling yet, so decide, document and keep configurable)**
10. **Notice: counted from when?** Cancellation time, run time, or when the desk can actually act (~10:30 weekdays, nobody acts before then; Bethany from 8:30 Sat)? Not stated. Check against the answer key.
11. **"Usually Josée" for post-op** is soft. Is it a filter or a preference? Check the answer key.
12. **"More than two months"**: from the line's `added` date, measured to run day. Calendar months vs 60 days is unstated. Repeat lines reset the clock (newer date).
13. **"Booked since"**: matching waitlist names to the export needs name/phone matching. Spellings differ (accents, nicknames, phone formats like `506-555-0101` vs `506 555 0102`; dates like `Jul 6` vs `7/14`). A missed match = stale person offered = hard-gate fail.
14. **Repeat line conflicts**: the newest line wins, but if the newest line is shorter (e.g. omits therapist), does the old restriction carry over? Unstated; Tanya says the newest is "the right one".
15. **Regulars first** (Marc) vs **first asked** (Tanya) vs **fastest to arrive**: unresolved. Show each way; don't pick for them.
16. **"Would say yes"**: done check 1 says *fit and would say yes*. Only the notes (availability, notice, preferences) signal willingness. There's no record of past yes/no answers (FU: "Not known").
17. **Prospective clients** (not in Kneadly, no consent): can be *listed* as a fit (the target is who to offer to), but can't be texted. Flag them as "phone only / no text consent".
18. **"Too close to the start"**: no fixed cut-off given. Interacts with each person's notice need.

**Open questions (unknown, don't guess)**
- Which browser the desk uses; does Kneadly have an API or AI tools? (Julie, unanswered)
- Does Kneadly alert on cancellation? (unanswered)
- Where Kneadly stores data. (Julie: "I'd have to ask Kneadly")
- Real cost of the higher plan. (~$45, unchecked)
- Can a slot be held while offered? **No hold**, manual block only.
- Record of past offer yes/no? Not known.
- Who keeps the cleaned waitlist current? Tanya "supposedly"; it must take less time than the book.
- How to measure refill rate going forward: the "rebooked into" link in the Friday report (manual, so it's unreliable).

---

## 5. Key numbers and people

- **Clinic:** Kettle & Stone Massage Therapy, Moncton NB. Weekdays 9 to 8, Sat 9 to 3.
- **Therapists (6):** Marc Cormier (Tue/Thu/Sat, owner), Dave Melanson (most late openings; offered a job elsewhere), Josée Landry, Amira Haddad (prenatal), Kelsey Babineau (prenatal), Rachel Thibodeau.
- **Desk:** Tanya (weekdays from 8:00; confirmation calls 8:00 to 9:15; first breather ~10:30), Bethany (Sat, from 8:30).
- **Owner/buyer:** Marc. **Tech/admin:** Julie (Mon and Thu; only one who exports).
- **Volumes:** ~10 to 12 late openings/week, ~3 refilled. Sample: 44 openings, 12 refilled. Possible ~31 with a perfect list.
- **Prices:** $115 / 60 min, $160 / 90, $70 / 30. Split: clinic 40%, therapist 60%.
- **Problem cost:** ~$22.8k to $30.6k CAD/yr to the clinic (excludes therapists' share).
- **Budget:** $50/mo fine, $150/mo no. Upkeep ~1 hr/month (Julie).
- **The 70% target** is the clinic's *real* refill result. Friday's done checks judge the *tool's names* against Tanya's answers (FU).
