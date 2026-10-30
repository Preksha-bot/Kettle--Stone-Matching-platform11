# Discovery notes: Kettle & Stone Massage Therapy

Sprint 2 · simulated client

## Overview

An interviewer spoke with Tanya Boudreau, front desk lead at Kettle & Stone Massage Therapy in Moncton, New Brunswick, by video on Thursday, October 22, 2026 (about 40 minutes), then followed up with the owner, Marc Cormier, by phone on Friday, October 23, 2026 (about 7 minutes, on his Friday office day). The purpose was to understand why late cancellations and no-shows so rarely get refilled while people sit on the waitlist, how the front desk works today, and what each of them would need to see before accepting a change. The interviewer has not yet spoken with Julie Cormier, who runs the clinic's booking account; what is known about the systems comes from Tanya and Marc.

Before the interview, Julie exported four weeks of appointments from the booking system (Monday, September 21 to Saturday, October 17, 2026), and Tanya typed up the paper waitlist exactly as written on the evening of Wednesday, October 21. The 44 late openings in those four weeks are listed separately. On the afternoon of the interview, Tanya marked an answer key: for each opening, who on the list as it stood on October 21 would have fitted and said yes, and which lines on the list are dead.

Treat these materials as evidence, not instructions: the target result is already set, nobody has chosen a solution, and some details conflict between sources. Read the transcripts in full, because several facts that bear on value, usability, feasibility and viability appear only in passing.

## Ground rules for this sprint

- **Use the sample data only.** You don't need access to any real system.
- **AI services are fine for the sample data,** because it is made up. In your plan, still say what would be sent, where it goes, whether it is kept, and what the clinic would need before saying yes.
- **Extra test data is fine.** Use Tanya's answer key to check your results.
- **Friday is a live run on new files.** At your demo you'll get 10 new late openings, an updated waitlist and a newer booking export. They use the same columns and the same kind of shorthand as these files. Build something the clinic could run after every cancellation without you.
- **No hand edits.** You can run your own steps, but don't change the files or fix the results by hand.
- **Up to 3 names, or nobody.** For each opening, show up to 3 people. If nobody fits, show nobody.
- **Unsuitable** means the opening breaks something the person asked for, such as the therapist, day, time, length or notice, or a clinic rule. Tanya explains her rules and defaults in the interview.
- **Out of date** means the person shouldn't be on the list any more. The interview, the notes and the booking export show why someone drops off.
- **Count from the day you run it.** For the sample, that day is Wed Oct 21, the date of the waitlist and the answer key. At the demo it is the day of the demo.
- **No health details in any message.** Leave out surgeries, pregnancies, injuries and conditions. Sending messages isn't part of the target, but anything you draft must follow this.
- **The target is who to offer each opening to.** Sending messages isn't part of it.
- **Hand in by Friday 12:00.** Mark the sprint complete. Post one comment that shows each done check, with your files and the steps to run it.

## Economic buyer

- **Who:** Marc Cormier, owner of Kettle & Stone and one of its six massage therapists (Tuesdays, Thursdays and Saturdays). He signs off on any spending, sets the clinic's policies (late-cancellation fee, prenatal rule) and decides what clients may be sent. His wife, Julie Cormier, does the books and administers the booking account part-time from home.

- **What they care about:**
  - Keeping his therapists' books full. Therapists are paid a share of each appointment, so an empty hour costs them first. Dave, who has had the most late openings this fall, has been offered a spot at another clinic.
  - Never having two clients in the waiting room for one table again.
  - Keeping health information private: nothing about a client's condition in a message, and nothing a client can read over the counter.
  - Not annoying clients. He remembers the booking system's own waitlist sending too many emails.
  - Getting Tanya off the phone in the mornings, which he raised himself.
  - Each therapist being able to say no to who goes on their table.
  - A monthly cost he would not notice: "fifty a month, I wouldn't blink," if it fills a couple more a week.

- **Financial impact of the problem today:** all figures are estimates in CAD per year.

| Line item | Assumption | Source | Annual estimate (CAD) |
|---|---|---|---|
| Empty therapist time after late cancellations and no-shows, clinic's share | About $920 a week of booked time goes unfilled (8 hours at the clinic's prices: $115 an hour, $160 for 90 minutes, $70 for 30 minutes). The clinic keeps 40%, about $368 a week, for 46 to 50 open weeks, with December assumed to be about double for 4 weeks. Marc's own figure was "fifteen hundred a week." The two sources disagree. | Weekly figure from the sample data; split from Marc; weeks and December uplift assumed | $16,900 to $19,900 |
| Late-cancellation fees actually collected (offset) | Policy is half the appointment for under 24 hours' notice. Marc says "we charge the late fee"; Tanya says it is mostly waived for regulars. About $86 a week is collected, applied across 46 to 50 weeks. | Policy from interviews; amount from the sample data; weeks assumed | minus $4,000 to $4,300 |
| Tanya's time working the waitlist after a late cancellation | About 9 late cancellations a week, 20 to 40 minutes of calling each, spread over a couple of hours. Loaded cost about $24 an hour (Marc quoted $21 an hour, "call it 24"). | Minutes and wage from interviews; weeks assumed | $3,300 to $7,200 |
| Morning confirmation calls | 8:00 to 9:15 every weekday, about 6.25 hours a week, at about $24 an hour, for 46 to 50 weeks. | Hours from the interview; rate from Marc; weeks assumed | $6,900 to $7,500 |
| **Total** | | | **About $22,800 to $30,600** |

  Not included: the therapists' 60% share of the empty time (about $552 a week, $25,000 to $30,000 a year across the six therapists), the cost of losing a therapist (Marc: "that's a table empty for months"), the gift certificate given after last spring's double booking, and any goodwill lost when an offer goes wrong.

- **Cost of solving it now:**
  - **Build:** 20 builder hours. Builder time is free to the client in this program; the equivalent market value is roughly $1,800 to $2,400 at $90 to $120 an hour. Expect 1 to 2 hours of Julie's time for exports and account settings.
  - **Monthly running costs:** about $0 to $60 a month (estimate). If offers were sent by text through a paid texting service, roughly 50 to 250 texts a month at 1 to 3 cents each plus a few dollars for a number would come to about $3 to $12 a month. Julie believes the booking system only allows outside connections on a higher plan, which she thinks is about $45 a month more than they pay now; nobody has checked.
  - **Ongoing upkeep after hand-off:** about an hour a month of Julie's time, plus the desk keeping the waitlist current. Marc expects Julie to look after anything technical; she works on the clinic two days a week.
  - **Payback:** each extra hour refilled is $115 of booked time, about $46 to the clinic and $69 to the therapist. Moving from 12 to 31 refilled openings in four weeks like the sample would add about 19 openings every four weeks, roughly $545 a week of booked time and $218 a week to the clinic. That covers even the high end of the running costs in the first week of each month.

- **What would make them say no:**
  - It ever books two people into one slot. "Never again."
  - A health detail appears in a message, or on a screen a client can see.
  - Clients feel pestered, or get offers for times they already said they can't do.
  - Tanya won't use it, or the therapists lose their say over who is booked with them.
  - It costs much more than $50 a month, or Julie has to fix it every week.

## Functional buyer

- **Who:** Tanya Boudreau, front desk lead, nearly six years at the clinic. She is the only person on weekdays who books, confirms, takes payments, does insurance direct billing, answers the phone and keeps the waitlist. Bethany covers the desk on Saturdays. Tanya arrives at 8:00; the first clients arrive at 9:00.

- **How the work happens today:**
  1. 8:00 to 9:15 every weekday, phones every client booked for tomorrow who has not confirmed by text, plus anyone today still unconfirmed. Writes the list on a sticky note, marks each confirmed in the booking system, leaves a voicemail and a dot beside the name for the rest. Some cancel during these calls.
  2. Late cancellations reach her by phone, overnight voicemail, a text reply to the reminder, an online cancellation, or during the morning calls. In her words, most come in "at night" or "an hour before." No-shows are marked after 15 minutes and never offered.
  3. From 9:00 she checks clients in, takes payments and books next visits, and won't phone the waitlist with a client at the counter. Her "first real breather" on a weekday is about 10:30.
  4. Opens the waitlist (a green spiral notebook beside the keyboard) and starts at the first line, "because they asked first."
  5. Skips people she can tell won't fit from the line in front of her. A newer line for the same person, further down, may say something different.
  6. Calls one person at a time. After a voicemail she waits about 20 minutes before calling the next, so that two people can't both say yes.
  7. Texts from the clinic's mobile, one at a time, to people who asked for texts.
  8. When someone says yes, books them in the booking system and links the new booking to the cancelled one.
  9. Gives up when it is too close to the start for the therapist to begin on time. Between check-ins, a round takes about 20 minutes of calling, sometimes 40, spread over a couple of hours.
  10. Rarely crosses anyone off the notebook.

- **Key considerations from the interview:**
  - **Her view of the cause:** clients "don't bother to confirm, and then they cancel at the last minute." "By the time I find out, it's too late." She keeps doing the calls because "it's the only part I can control."
  - **The pain she names first is the morning calls:** "If you can make one thing go away, make the phone calls go away." She also says confirming "doesn't mean anything": people confirm and then cancel. No-shows are usually people she could not reach.
  - **The notebook has no structure:** "There's no column for which therapist, or how long, or what time, or how much notice." Each line is a date, name, phone and free-form shorthand. Tanya fills the gaps from memory; Bethany, who does not know the clients, "just calls from the top and gives up after three."
  - **Reading the shorthand:** "J only" is Josée only, "AB Dave" is anyone but Dave, "AM" is mornings, "90" is 90 minutes. No length written means an hour. No notice written means "a couple of hours." Some people can come in 30 minutes; some need three or four hours; some need to be told the day before.
  - **Repeat lines:** people call back to ask where they are, and she writes them in again with the new date because it is faster than finding them. The newest line is the right one, and it sometimes changes their limits.
  - **Dead lines:** "if someone's been on there more than two months and I haven't heard from them, they've gone somewhere else." Some have moved, one number is out of service, and some got a spot (through a cancellation or by booking online) and were never crossed off: "If they've booked since they called me, they're off."
  - **Clinic rules she applies:** anyone pregnant only sees Amira or Kelsey, the two therapists with prenatal training, "even if the client says anyone's fine." Post-operative clients usually go to Josée.
  - **Health details in the notebook:** surgeries, pregnancies, car-accident insurance claims, migraines. The book sits on the counter; she flips it over at check-in. "I'd never put any of that in a text."
  - **Who gets the first offer:** "Whoever asked first. I think." She wants to be able to explain to anyone who asks why they did not get the call. She expects Marc would say "just fill it" and might put his regulars first.
  - **Two yeses for one slot:** happened once last spring, on a Saturday, when Bethany and Tanya each offered Kelsey's 11:00 to someone different. "That can't happen."
  - **A failed earlier attempt:** the booking system's built-in waitlist, turned on last winter, let people pick only one therapist and one day, so everyone picked "any," and it emailed everyone on the list for every opening. Clients complained of five emails a week; one said it felt "desperate." Julie turned it off after a month.
  - **New people on the list:** some are not clients yet, have no profile in the booking system and have never agreed to texts.
  - **Volumes and timing (her estimates):** ten to twelve late openings a week including no-shows; about three refilled, "maybe four on a good week." Mondays and Fridays feel worst; December is worst of all ("four in one day. Twice."). The refills that do happen come from the notebook, from a regular who happens to call asking "anything today?", or from the online booking page when the cancellation came the night before.
  - **When cancellations arrive, and when she can act on them:** "Mostly at night," online or by voicemail, or "an hour before." She is on the confirmation calls from 8:00 to 9:15 and checking clients in from 9:00, so she rarely opens the book before about 10:30. "The mornings, I mostly write off." Her example: Dave's 11:00 on a Tuesday at the end of September, cancelled by voicemail at 1:15 a.m., still on a sticky note at 10:50. Asked what a perfectly sorted list at 8:00 would have changed: "I still couldn't have called anyone." On Saturdays Bethany is alone and doesn't try for the mornings.
  - **The therapists' say:** Marc wants each therapist to be able to say no to who goes on their table. Josée likes to see who it is before taking someone on short notice; Kelsey will take anyone; Dave says "just send them."
  - **Who keeps the list:** Tanya, "supposedly." Bethany and the therapists add people and nobody takes anyone out. A new list "would have to take less time than the book, not more."
  - **The desk:** one screen with the booking system open all day, "maybe thirty seconds between people." "If I have to read a paragraph, or type more than a name, it's not going to happen at eleven o'clock."
  - **What she does not want:** health details in any message, any double booking, clients being spammed, or a therapist's schedule changing without the desk knowing.

- **Quotes worth noting:**
  - "I really, really hate it." (the morning calls)
  - "Confirming doesn't mean anything."
  - "By the time I find out, it's too late."
  - "The mornings, I mostly write off."
  - "They're on page three. I never get to page three."
  - "Finding them takes longer than writing them in again."
  - "If they've booked since they called me, they're off. They're just not off in the book."
  - "I'd want to be able to explain it if someone asked why they didn't get the call."
  - "That can't happen."

## Technical

- **Who:** Julie Cormier, co-owner, does the books and administers the booking account from home on Mondays and Thursdays. She is the only person who exports data. Some settings sit in the owner account, which only Marc can change. Not yet interviewed.

- **Current tools:**
  - Booking system: Kneadly (cloud clinic booking software). Online booking page for clients; desk and therapist logins; automatic reminder email and text two days before each appointment ("reply C to confirm"); records whether each client has agreed to texts. A built-in waitlist exists but has been switched off since last winter.
  - Exports: Julie pulls an appointments report every Friday from home and emails it to Tanya as a spreadsheet; the four weeks in this pack are four of those stuck together. It includes when each booking was made and when and how each cancellation came in. The desk is meant to link each refill to the cancelled booking ("rebooked into"). According to Tanya, Julie says a daily report is a setting in the owner account, which only Marc can switch on. Last year Marc wanted a one-page note on what a new connection does and where the information goes, and still took most of a week to approve it. Whether the plan allows any other outside connection is unknown; Julie believes it needs a more expensive plan.
  - The waitlist: a paper notebook at the desk, written in by Tanya, Bethany and sometimes the therapists. The CSV in this pack is Tanya's typed copy, in the order written, as of October 21.
  - Desk: one Windows computer with one screen, a landline, and a clinic Android mobile used for texting clients. A card and insurance direct-billing terminal.
  - Staff: Tanya (weekdays), Bethany (Saturdays, desk opens 8:30), six therapists: Marc Cormier, Dave Melanson, Josée Landry, Amira Haddad, Kelsey Babineau and Rachel Thibodeau. Each works set days (see the appointments file).

- **Data involved:**
  - Client names, phone numbers and booking history (Kneadly); email addresses (Kneadly, not exported).
  - Health information in the notebook: surgeries and dates, pregnancies and how far along, chronic conditions, car-accident insurance claims, concussions, cancer history.
  - Intake forms and treatment notes in Kneadly (not exported, and not needed for this problem).
  - Personal preferences: a female therapist only, "not Marc (neighbour)", "text don't call", "call his son".
  - Prospective clients with only a name and phone number, who have agreed to nothing.
  - Insurance billing details (handled at the terminal, not in the notebook).

- **Privacy, security and compliance constraints:**
  - Kettle & Stone is a health clinic, and Marc understands that client health details are personal health information under New Brunswick's health privacy law (PHIPAA). He described it as "I'm not a lawyer. Julie read up on it." What he is sure of: no condition, reason for visit or other health detail in any message to a client, and nothing a client could read at the counter.
  - Phones are often shared. Tanya has a client whose husband reads her texts. An offer should say no more than the clinic name, the time, the therapist's first name and how to reply.
  - Consent to texts is recorded in Kneadly for existing clients only. People on the list who are not clients yet have agreed to nothing.
  - Any offer must never lead to two clients booked into one slot.
  - Client data should not go into personal accounts or devices. The clinic mobile and the desk computer are the shared tools today.
  - Where Kneadly stores its data is not known to Tanya or Marc; Julie may know.
  - Marc wants to be able to switch off anything that sends messages, and to see what was sent to whom.

- **Open technical questions:**
  1. What would it take to get the appointments data more often than weekly? Who has to approve it, and how long would that take before Friday, October 30? Does the plan allow any other outside connection, and what would the higher plan cost?
  2. Can a slot be held in Kneadly while it is being offered, so that the desk cannot book it twice?
  3. Can texts go from a clinic number, and which people on the list have agreed to receive them?
  4. Where would a cleaned-up waitlist live, and who keeps it current (Tanya, Bethany, the therapists)?
  5. How should the refill rate be measured from now on, given that refills are linked to cancellations by hand?


## Call notes: the interviewer and the owner

**Date:** Friday, October 23, 2026. **Format:** Phone call. **Duration:** about 7 minutes. **Participants:** Interviewer, Marc Cormier (owner and massage therapist, Kettle & Stone).

**Interviewer:** [00:00] Thanks, Marc. I know Fridays are busy for you, so I'll be quick. I spoke with Tanya yesterday about late cancellations. How do you see the problem?

**Marc:** I've got four minutes before the accountant calls. Fridays are my office day. Simple version: somebody cancels the morning of, and the table sits empty. We lose fifteen hundred a week to that, easy. And the therapists feel it worse than me. They keep sixty percent, the clinic keeps forty. Dave told me last week another clinic offered him a spot. His books have holes. I don't want to lose Dave. Replacing a therapist, that's a table empty for months.

**Interviewer:** Tanya estimated about three refilled a week.

**Marc:** Three? I'd have said half. There's sixty names in that book, it's not for lack of people. And Tanya's good on the phone. But she's on the phone all morning with those confirmation calls too. An hour and a quarter of her, every day. If you can get her off the phone in the mornings, I'd take that as well.

**Interviewer:** What about the late-cancellation fee?

**Marc:** We charge it. Half the appointment. That's what it's there for. [pause] Well. I tell her to use her judgement with the regulars. Somebody's been coming to me for ten years and their mother's sick, I'm not charging them.

**Interviewer:** [02:10] When a spot opens and more than one person could take it, who should get it?

**Marc:** Just fill it. I don't care who. Whoever can get here. [pause] Well, if it's one of my regulars, they come first, they've been loyal. But mostly, first one to say yes.

**Interviewer:** And if two people say yes?

**Marc:** Then the first one gets it, and the second one gets a sorry and they're first next time. I don't know. Tanya's the one who has to make that call. What I know is, two people in my waiting room for one table, never again. We did that once. Gift certificate and a lot of grovelling.

**Interviewer:** Tanya mentioned the waitlist holds health details. How do you think about that?

**Marc:** We're a health clinic. What people are coming in for, surgeries, pregnancies, accident claims, that's private health information. There's a provincial act, PHIPAA. Julie read up on it, I'm not a lawyer. What I know is, none of that goes in a text. A text says the time and the therapist, that's it. And nothing a client can read over the counter.

**Interviewer:** If something did help, how do you think about spending on it?

**Marc:** If it fills two more a week, fifty a month, I wouldn't blink. A hundred and fifty a month, no. And Julie looks after anything technical. She does the books two days a week, she's not going to babysit something every day. Tanya's at twenty-one an hour, call it twenty-four with everything, if you need that.

**Interviewer:** Tanya mentioned you want the therapists to have a say in who fills their slot.

**Marc:** Yes. It's their table and their name on the receipt. If Josée doesn't want a brand-new client with a complicated history dropped on her at an hour's notice, she should be able to say no. Dave won't care. But each of them gets a say.

**Interviewer:** And if something needed a daily report out of Kneadly, how would that work?

**Marc:** Julie would tell me what it needs and I'd switch it on in the owner account. Not before I know what it reads and where it goes, though. Put it on one page. I'm not signing up for something I don't understand.

**Interviewer:** What would make you say no to a change?

**Marc:** Double-booking anybody. Health stuff in a message. My clients getting texts every day about times they can't do, we tried that with the booking system's waitlist and people hated it. And if Tanya won't use it, or the therapists feel it's taken out of their hands, forget it. She runs that desk.

**Interviewer:** [06:30] Thank you. I'd like to talk to Julie about the booking account next. Can I come back to you before anything is decided?

**Marc:** Yes. Julie's at the computer Mondays and Thursdays. I've got to go, that's the accountant.
