"""The feedback loop (platform-plan.md §11, technical plan §11.7): what happened to past offers informs later ones,
always through a person, and never decides who is offered that same opening. The matcher never learns by itself.

- Anti-pestering: someone offered `max_offers_per_week` times in the last 7 days rests until the oldest of those
  offers is a week old (the limit is Marc's; 0 = no limit).
- Three no's in a row: their card says "ask if still interested".
- Marc's numbers: refills by channel, time from hearing about a cancellation to filling it, offer outcomes, the
  reasons people gave for no, possible wrong offers, and how the booking export says slots were refilled.
"""
from datetime import datetime, timedelta
from statistics import median

from kettle import store

WEEK = timedelta(days=7)
DECLINE_REASONS = ("the time", "the day", "too short notice", "the therapist", "the length",
                   "our mistake: they'd said they can't")
MISTAKE = DECLINE_REASONS[-1]


def _at(text):
    return datetime.strptime(text, "%Y-%m-%d %H:%M")


def offers_by_person(con, people):
    """Each person's offers, oldest first, found through any of their lines. `people`: records or Person objects."""
    owner = {}
    for p in people:
        lines = p["lines"] if isinstance(p, dict) else p.line_ids
        for line in lines:
            owner[line] = lines[0]
    out = {}
    for r in con.execute("SELECT * FROM offers ORDER BY offered_at, id"):
        if r["line"] in owner:
            out.setdefault(owner[r["line"]], []).append(dict(r))
    return out


def resting(con, people, limit, now):
    """People at the weekly limit: first line -> {"count", "until"}. Empty when there's no limit."""
    if not limit:
        return {}
    out = {}
    for first, offers in offers_by_person(con, people).items():
        recent = [_at(o["offered_at"]) for o in offers if now - WEEK < _at(o["offered_at"]) <= now]
        if len(recent) >= limit:
            out[first] = {"count": len(recent), "until": recent[-limit] + WEEK}
    return out


def three_nos(con, people):
    """First lines of people whose last three answers were no or no answer: ask if they're still interested."""
    return {first for first, offers in offers_by_person(con, people).items()
            if len(answered := [o for o in offers if o["outcome"] in ("yes", "no", "no answer")]) >= 3
            and all(o["outcome"] in ("no", "no answer") for o in answered[-3:])}


def report(con, since, until):
    """Marc's numbers for openings starting between `since` and `until` (dates, inclusive)."""
    openings = [dict(r) for r in con.execute("SELECT * FROM openings WHERE date BETWEEN ? AND ? ORDER BY date, start",
                                             (since.isoformat(), until.isoformat()))]
    late = [o for o in openings if "no-show" not in o["kind"].lower()]
    state = store.desk_state(con)
    heard = {r["appointment_id"]: r["recorded_at"] for r in con.execute("SELECT appointment_id, recorded_at FROM cancellations")}
    outcome, minutes, by_channel = {}, [], {}
    for o in late:
        s = state.get(o["appointment_id"], {})
        if s.get("status") == "filled" and s.get("rebooking"):
            how = "refilled from the waitlist"
            start = _at(heard.get(o["appointment_id"]) or o["cancelled_at"])
            minutes.append((_at(s["rebooking"]["made_at"]) - start).total_seconds() / 60)
        elif s.get("status") == "taken":
            how = f"filled another way: {s['closed_how']}"
        elif s.get("status") == "released":
            how = f"released: {s['closed_how']}"
        elif s.get("offers"):
            how = "offered, not filled"
        else:
            how = "no offer recorded"
        outcome[how] = outcome.get(how, 0) + 1
        channel = o["heard_via"] or "not known"
        row = by_channel.setdefault(channel, {"openings": 0, "refilled": 0})
        row["openings"] += 1
        row["refilled"] += how == "refilled from the waitlist"
    ids = {o["appointment_id"] for o in openings}
    offers = [dict(r) for r in con.execute("SELECT * FROM offers ORDER BY offered_at") if r["appointment_id"] in ids]
    outcomes, reasons = {}, {}
    for x in offers:
        key = x["outcome"] or "waiting"
        outcomes[key] = outcomes.get(key, 0) + 1
        if x["outcome"] in ("no", "no answer") and x["reason"]:
            reasons[x["reason"]] = reasons.get(x["reason"], 0) + 1
    labels = {o["appointment_id"]: f"{o['opening_id']} {o['date']} {o['start']}" for o in openings}
    mistakes = [{"opening": labels[x["appointment_id"]], "person": x["person"], "line": x["line"],
                 "at": x["outcome_at"]} for x in offers if x["reason"] == MISTAKE]
    export = {}  # how the booking export says slots were refilled: the refill booking's booked_via
    for r in con.execute("SELECT b.appointment_id, n.booked_via FROM bookings b JOIN bookings n "
                         "ON n.appointment_id = b.rebooked_into WHERE b.rebooked_into != '' AND b.date BETWEEN ? AND ?",
                         (since.isoformat(), until.isoformat())):
        via = {"online": "booked online", "phone": "the client phoned", "desk": "the desk called"}.get(r[1], r[1] or "?")
        export[via] = export.get(via, 0) + 1
    return {"since": since, "until": until, "openings": len(late), "no_shows": len(openings) - len(late),
            "outcome": outcome, "by_channel": by_channel,
            "median_minutes": round(median(minutes)) if minutes else None, "refilled": len(minutes),
            "offers": len(offers), "offer_outcomes": outcomes, "reasons": reasons, "mistakes": mistakes,
            "export": export}


def outcomes_rows(con):
    """Every opening the desk worked on, with each offer and its answer: raw material for new test cases (plan §11:
    each week's real openings and who said yes). Lines and answers only, no desk names."""
    state = store.desk_state(con)
    rows = []
    for o in con.execute("SELECT * FROM openings ORDER BY date, start"):
        s = state.get(o["appointment_id"])
        if not s or not s.get("offers"):
            continue
        offered = "; ".join(f"W{x['line']} {x['outcome'] or 'waiting'}" + (f" ({x['reason']})" if x["reason"] else "")
                            for x in s["offers"])
        filled = s["rebooking"]["line"] if s.get("rebooking") else ""
        rows.append([o["opening_id"], o["appointment_id"], o["date"], o["start"], o["therapist"], o["length_min"],
                     f"{o['hours_notice']:g}", offered, f"W{filled}" if filled else "", s.get("status", "")])
    return rows
