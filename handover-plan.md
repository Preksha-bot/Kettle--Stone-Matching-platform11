# Handover plan: Kettle & Stone waitlist matcher

**Done check 3:** who looks after it after the builder steps away, what it costs to run, and what happens when it gets one wrong.
For Marc (owner), Julie (looks after it), Tanya and Bethany (use it).

**In one paragraph.** When a client cancels late, the desk runs the matcher on the desk computer. In a few seconds it shows up to 3 people from the waitlist who fit that opening, or "nobody". Each name comes with a phone number, the notebook line, and a one-line reason ("Josée or Rachel · 60 min · mornings"). It never phones, texts, emails or books anyone, and never connects to Kneadly. The desk still makes the call and books the yes in Kneadly, as today. It costs **$0 a month** to run. The notebook keeps working as a backup at all times.

---

## 1. Who looks after it

| Who | What they do | Time |
|---|---|---|
| **Tanya** (weekdays), **Bethany** (Saturdays) | Use it after each late cancellation; keep the waitlist current | ~1 min per cancellation |
| **Julie** | Owner of the tool: monthly check, settings, first person to call if it stops | **~1 hour a month** |
| **Marc** | Decides the rules: offer order, each therapist's say, any outside connection | A few minutes when something changes |
| **Therapists** | Josée is marked "ask Josée first"; Kelsey and Dave take anyone | none |

### 1.1 Daily use at the desk
1. A late cancellation comes in. Add **one row** to `openings.csv`: opening ID, appointment ID, date, start, length, therapist, "late cancel", time it was cancelled. (No-shows aren't worth adding: they're never offered.)
2. Double-click the **"Waitlist matches"** shortcut (Julie sets this up once; it runs `run.py` with the clinic's file names, today's date and the desk's `reviewed.csv`).
3. Read `out/matches.txt`. Call **#1**. If no, or no answer after ~20 min, call #2, then #3.
4. **Yes** → check in Kneadly that the slot is still empty, book it, and link it ("rebooked into").
5. All three say no → run again with `--declined O12:39,42,45` to get the next names.

**Keeping the waitlist current:** keep it as a spreadsheet on the desk computer with the same five columns as the notebook (`line, added, name, phone, notes`) and the same shorthand. Add a new row at the bottom; never edit old rows. The matcher already takes care of:
- newest line wins (for the things it mentions)
- 60 days without contact → off the list
- booked since → off the list
- "moved", "not in service", "take off" → off the list

**When someone's needs have changed completely**, start their new line with **`start over`**, then all their details: `start over - Rachel only - 60 - mornings`. Everything their older lines said is then ignored, but they keep their place in the queue. A line that says only "start over" is held back, so it can't turn someone into "anyone, any time".

**Privacy habit:** don't write conditions in the notes. Write only what changes who can treat them, e.g. "prenatal" (that routes them to Amira or Kelsey). The matcher doesn't need anything else, and the list stops carrying health details.

### 1.2 Julie's monthly check (~1 hour)
1. Open `mistakes-log.csv` (the desk notes any wrong offer there). Look for the same problem twice.
2. Open `out/preprocess-report.txt`:
   - **Held for review: a note it can't read** ("can't read 'weekends'", "scheduling words mixed with a private detail"). Ask the desk to add a new line for that person that starts with `start over`, followed by all their details in the usual shorthand. A plain new line isn't enough: the old unreadable words would still hold them back.
   - **Held for review: "check identity"** (one phone under two names, one name with two phones, a `same #` that matches nobody). Check the notebook or call, then add a row to **`reviewed.csv`**:

     | line | decision | other_line | checked_by |
     |---|---|---|---|
     | 42 | same person | 26 | Tanya, Nov 3 |
     | 57 | different people | 12 | Julie |
     | 33 | ignore | | Tanya |

     `same person`: one client (e.g. a new number); the newest number is used. `different people`: e.g. a parent and child sharing a phone; both are released. `ignore`: leave that line out entirely. A row that's unclear or contradicts another row is skipped with a warning, and those lines stay held. Never write a reason or a health detail in `checked_by`.
   - **Desk decisions:** lists what `reviewed.csv` did on this run.
   - **Warnings:** should say "none".
3. A therapist joined, left, or changed what they take? Edit `config/clinic.json` (name, short forms, female, prenatal-trained, "see_first").
4. After any change to `config/clinic.json`, run `python run.py --check-settings`. It names each mistake (a short form used for two therapists, a misspelled setting, a time that isn't HH:MM), and the matcher won't run until they're fixed. Then run `python -m pytest`. All tests must pass. If any fail, undo the change.
5. Count refills: the "rebooked into" links in her Friday report. Compare month to month.

### 1.3 Setup, once (~1 hour of Julie's time)
- Install Python 3 (free) on the desk computer and copy the project folder there.
- Make the desktop shortcut. It runs `run.py` with the clinic's file names, today's date and `--reviewed reviewed.csv`, so the desk's decisions apply on every run.
- Show Tanya and Bethany steps 1–5 (15 minutes).
- Run `python -m pytest` once to confirm it works on that computer.

### 1.4 When a developer is needed (rare)
- Kneadly changes its export columns: the matcher stops with "missing column …".
- The desk starts using shorthand that can't be standardised.
- Marc wants the future platform (cancellation inbox, one-tap call outcomes).

Expect this 0–2 times a year, 1–3 hours each at about $90–120 an hour.

---

## 2. What it costs to run

| Item | Cost |
|---|---|
| Software, hosting, subscriptions | **$0/month**. Python is free; it runs on the existing desk computer; no internet, no AI service, no texting service |
| Julie's upkeep | ~1 hour/month |
| Desk time | ~1 minute per cancellation to add the row and run it (9–12 a week ≈ 10 min/week). Today a round of calling takes 20–40 minutes, mostly on people who don't fit |
| One-time setup | ~1 hour of Julie's time + 15 min training |
| **Total now** | **$0/month**, well under Marc's $50 line |

**Optional later, each needing Marc's OK first:**
- **Daily export instead of weekly:** free. It's a setting in the owner account; Julie gives Marc a one-page note first. Keeps "booked since" fresher.
- **Higher Kneadly plan:** about $45/month more, unconfirmed. Only needed for the future platform's live cancellation feed. Together with everything else it must stay under $50.
- **Texting from a clinic number:** about $3–12/month. Not part of this tool.

**What it's worth (from the sample's four weeks):**
- 36 late cancellations; the desk refilled 12.
- The matcher finds at least one person who fits for **34 of the 36**.
- If the desk can only start calling at 10:30 (as today), **24 of 36** still have someone who can make it.

Not everyone says yes, so 24 is a ceiling, not a forecast. Each refilled hour is about **$116 of booked time: ~$46 to the clinic, ~$70 to the therapist**. Marc's bar of "two more a week" would be worth about **$400 a month to the clinic** (and more to the therapists), against a running cost of $0.

---

## 3. What happens when it gets one wrong

The matcher is advice. The person on the phone decides, and nothing reaches a client unless the desk calls them. It is built to **leave someone out rather than guess**: a note it can't read, or a name/phone mix-up, puts that person on hold instead of on the list.

| What went wrong | How you'd notice | What the desk does | How it gets fixed |
|---|---|---|---|
| **Offered someone who can't take it** (wrong day, time, therapist) | They say "I can't do Tuesdays" | Say sorry, call #2. Add a row to `mistakes-log.csv` | Julie, monthly: usually an unclear notebook line, so the desk rewrites it as a new line. Otherwise a settings fix |
| **Offered someone who already got in, or left** | "I already booked" / "I go somewhere else now" | Add a new line for them saying "take off"; the next run removes them | Usually the booking export is old (weekly). Run with the newest export; the daily export would fix this |
| **Shows nobody, but the desk knows someone who'd fit** | Desk knowledge | Call them as before; the notebook still works | Check the "held for review" list: a `start over` line for a note it can't read, or a row in `reviewed.csv` for a phone/name mix-up (§1.2) |
| **Two people say yes** | — | Can't come from the matcher: it never books. One offer at a time, ~20 min wait, check Kneadly before booking | Marc's rule: the first yes gets it, the second gets a sorry and goes first next time |
| **A health detail on screen or in a message** | — | The matcher never keeps or prints health text (tested on every output file). Any text the desk writes by hand: clinic name, time, therapist's first name, how to reply. Nothing else | — |
| **It stops with an error** | "Stopped: …" message | Use the notebook as before | Julie: usually a renamed file or column; the message says which |

**Built-in safety nets:**
- at most 3 names
- a reason next to every name
- a "not offered" line explaining who was skipped and why (so Tanya can explain to anyone who asks)
- input files are only read, never changed
- a settings check that stops the run if `config/clinic.json` has a mistake
- held people are released only by a desk decision (`start over` line or `reviewed.csv`), never by a guess
- 148 automatic tests, including one that checks the outputs for health words

**Off switch:** there's nothing to switch off, because it sends nothing. Stop using it and the clinic is back to the notebook.

---

## 4. What is read, sent and kept (for Marc's one page)

| | |
|---|---|
| **Reads** | The waitlist file (names, phones, notes), Julie's booking export (names, times, therapists, when booked and cancelled), the openings file |
| **Sends** | **Nothing.** No internet connection, no AI service, no Kneadly connection, no messages |
| **Keeps** | Files in the `out` folder on the desk computer, overwritten on every run: names, phone numbers, notebook line numbers, what each person can take. **No health text.** Pregnancy appears only as the therapists offered (Amira or Kelsey) and as a yes/no routing flag in `out/core/people.json` |
| **Who can see it** | Anyone using the desk computer. `matches.txt` has names and phone numbers (no health details); keep it off screen while a client is at the counter |

**Before the clinic says yes:** nothing for this version beyond installing Python on the desk computer. A daily export, a higher Kneadly plan, or any texting each needs its own one-page note to Marc first: what it reads, where the data goes, how long it's kept, what it costs.

---

## 5. Known limits

1. **The desk still types each opening** (one row). The planned cancellation inbox (technical plan §11.6) makes this one tap.
2. **"Booked since" is only as fresh as the export.** With a weekly export, someone who booked this week can still be offered. A small next step: warn when the export is more than 7 days old.
3. **Overnight cancellations:** with calling starting at 10:30, 24 of 36 openings are still reachable instead of 34. The planned "call outcome → instant match" (technical plan §11.5) would let the 8:00–9:15 call block reach the rest.
4. **Offer order** is "whoever asked first" until Marc and Tanya decide otherwise. Other orders can be switched on (`--order shortest-notice`, `--order regulars-first`).
5. **Josée's say** is a flag ("ask Josée first"), not a step that holds up the list.
6. **Tested on four weeks of autumn data** (44 openings, 60 waitlist lines), no December. Watch the first month closely through the mistakes log.
7. **Matching waitlist names to bookings** uses a nickname table (Bob/Robert, Mel/Melanie, …). A nickname that isn't in the table means a "booked since" can be missed. Add it to `config/clinic.json`.
