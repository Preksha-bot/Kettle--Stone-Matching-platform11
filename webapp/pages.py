"""HTML for each screen. Every value from the data goes through esc(), and no screen shows a health detail:
the database doesn't hold any (plan §5), and the names come with the same short reasons as matches.txt."""
import re
from datetime import date, datetime
from html import escape

from kettle.adapters.upload import line_ranges
from kettle.feedback import DECLINE_REASONS
from kettle.output.report import phone_display

CSS = """
:root { --ink: #1d2327; --muted: #5d6870; --line: #d9dcd6; --bg: #f6f5f1; --card: #fff; --accent: #1f5f5b;
        --warn-bg: #fff3dc; --warn-ink: #7a4b00; --err-bg: #fde8e6; --err-ink: #8a1c12; --ok-bg: #e5f2ec; }
* { box-sizing: border-box; }
body { margin: 0; font: 16px/1.45 system-ui, "Segoe UI", sans-serif; color: var(--ink); background: var(--bg); }
nav { background: var(--accent); color: #fff; padding: 0 12px; display: flex; flex-wrap: wrap; gap: 0 2px;
      align-items: center; }
nav .brand { font-weight: 700; margin-right: 14px; padding: 11px 0; white-space: nowrap; }
nav a { color: #fff; text-decoration: none; padding: 11px 9px; border-bottom: 3px solid transparent; white-space: nowrap; }
nav a.on { border-bottom-color: #fff; font-weight: 600; }
main { max-width: 1100px; margin: 0 auto; padding: 20px 16px 48px; }
h1 { font-size: 24px; margin: 0 0 4px; }
.sub { color: var(--muted); margin: 0 0 16px; }
.box { background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: 14px 16px; margin: 0 0 14px; }
.warn { background: var(--warn-bg); color: var(--warn-ink); border-color: #f0d9a8; }
.err { background: var(--err-bg); color: var(--err-ink); border-color: #f2c3bd; }
.ok { background: var(--ok-bg); border-color: #bfdccd; }
.facts { display: flex; flex-wrap: wrap; gap: 6px 22px; margin: 0; padding: 0; list-style: none; }
.facts b { font-weight: 600; }
.files a { margin-right: 14px; }
.opening { background: var(--card); border: 1px solid var(--line); border-left: 6px solid var(--accent);
           border-radius: 8px; padding: 12px 16px; margin: 0 0 12px; }
.opening.nobody { border-left-color: #a9b0b5; }
.op-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 14px; }
.op-when { font-size: 20px; font-weight: 700; }
.op-what { font-size: 18px; }
.op-meta { color: var(--muted); font-size: 14px; }
.names { list-style: none; margin: 10px 0 0; padding: 0; }
.names li { display: grid; grid-template-columns: 28px minmax(170px, 1.2fr) 130px 64px 3fr auto; gap: 10px;
            align-items: baseline; padding: 7px 0; border-top: 1px solid #eef0ec; }
.rank { font-weight: 700; color: var(--accent); }
.name { font-weight: 600; font-size: 17px; }
.phone { font-variant-numeric: tabular-nums; font-size: 17px; }
.lineno { color: var(--muted); font-size: 14px; }
.flag { display: inline-block; background: var(--warn-bg); color: var(--warn-ink); border-radius: 4px;
        padding: 0 6px; margin-left: 6px; font-size: 14px; white-space: nowrap; }
.nobody-note { margin: 10px 0 0; font-weight: 600; }
.closest { margin: 8px 0 0; color: var(--muted); font-size: 14px; }
form .field { margin: 0 0 16px; }
form label { display: block; font-weight: 600; margin-bottom: 4px; }
form .hint { color: var(--muted); font-size: 14px; margin: 2px 0 6px; }
input[type=file], input[type=date] { font-size: 16px; }
button { font-size: 16px; padding: 9px 18px; border-radius: 6px; border: 1px solid var(--accent); cursor: pointer; }
button.primary { background: var(--accent); color: #fff; }
button.plain { background: #fff; color: var(--accent); }
.actions { display: flex; gap: 10px; margin-top: 6px; }
table { border-collapse: collapse; width: 100%; background: var(--card); }
th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--line); vertical-align: top; font-size: 15px; }
th { color: var(--muted); font-weight: 600; }
ul.plain { margin: 6px 0 0; padding-left: 20px; }
h2 { font-size: 19px; margin: 24px 0 8px; }
.held { border-left-color: #c58a1a; }
.decide { margin-top: 10px; }
.decide .actions { flex-wrap: wrap; align-items: center; margin-top: 8px; }
.who { font-weight: 600; display: inline-block; margin-bottom: 8px; }
.who input, .field > input, .num { font-size: 16px; padding: 5px 8px; border: 1px solid var(--line); border-radius: 4px; }
.num { width: 80px; }
.pair { font-weight: 600; }
.tick { display: inline-block; margin: 2px 14px 2px 0; font-weight: 400; }
a.button { display: inline-block; font-size: 16px; padding: 9px 18px; border-radius: 6px; border: 1px solid var(--accent);
           text-decoration: none; }
a.button.primary { background: var(--accent); color: #fff; }
a.button.plain { background: #fff; color: var(--accent); }
select { font-size: 16px; padding: 5px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 0 18px; }
.grid input { font-size: 16px; padding: 5px 8px; border: 1px solid var(--line); border-radius: 4px; width: 100%; }
input.wide { font-size: 15px; padding: 5px 8px; border: 1px solid var(--line); border-radius: 4px; width: 100%; }
textarea { width: 100%; font: 15px/1.4 ui-monospace, Consolas, monospace; padding: 8px;
           border: 1px solid var(--line); border-radius: 4px; }
.columns { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; }
.columns ol { margin: 6px 0 0; padding-left: 22px; }
.paused-banner { background: var(--err-bg); color: var(--err-ink); padding: 10px 16px; font-weight: 600; }
.chip { display: inline-block; border-radius: 4px; padding: 2px 8px; font-size: 14px; font-weight: 600; }
.chip.live { background: #fde3c4; color: #7a3e00; }
.chip.held { background: #e3eef6; color: #1d4a6b; }
.chip.done { background: var(--ok-bg); color: #1f5133; }
.names li .act { grid-column: auto; }
.outcome { color: var(--muted); font-size: 14px; white-space: nowrap; }
form.inline { display: inline-flex; gap: 8px; align-items: center; margin: 0; }
.desk-step { margin-top: 10px; padding-top: 10px; border-top: 1px dashed var(--line); }
.desk-step p { margin: 0 0 6px; }
.desk-note { margin: 10px 0 0; color: var(--muted); font-size: 14px; }
.box.desk { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.box.desk .hint { flex-basis: 100%; margin: 0; }
form.box.inline { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
details > summary { cursor: pointer; margin: 18px 0 8px; }
.call-row { background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: 10px 14px; margin: 0 0 8px; }
.call { display: flex; flex-wrap: wrap; gap: 6px 16px; align-items: center; }
.call .op-when { font-size: 17px; }
.call .act { margin-left: auto; display: flex; gap: 8px; flex-wrap: wrap; }
.after { margin-top: 10px; padding-top: 8px; border-top: 1px dashed var(--line); }
.plain-names { list-style: none; margin: 6px 0 0; padding: 0; }
.plain-names li { padding: 3px 0; }
.plain-names .rank { display: inline-block; width: 22px; }
@media (max-width: 720px) { .names li { grid-template-columns: 24px 1fr; } .names li > :nth-child(n+3) { grid-column: 2; } }
"""

NAV = (("/", "Openings"), ("/calls", "Calls"), ("/inbox", "Inbox"), ("/board", "Waitlist"), ("/review", "Needs review"),
       ("/upload", "Upload"),
       ("/settings", "Settings"), ("/rules", "Rules"), ("/report", "Report"), ("/log", "Sync log"))


def esc(value):
    return escape("" if value is None else str(value))


def count(n, word):
    """count(1, 'opening') -> '1 opening'; count(3, 'opening') -> '3 openings'"""
    return f"{n} {word}{'' if n == 1 else 's'}"


def people_count(n):
    return "1 person" if n == 1 else f"{n} people"


def layout(title, body, here, held=None):
    """`held`: how many people are held for review, shown in the menu on every screen."""
    def label(href, text):
        return f"{text} ({held})" if href == "/review" and held else text
    links = "".join(f'<a href="{href}"{" class=on" if href == here else ""}>{label(href, text)}</a>' for href, text in NAV)
    return (f"<!doctype html><html lang=en><head><meta charset=utf-8>"
            f"<meta name=viewport content='width=device-width, initial-scale=1'><title>{esc(title)} · Kettle &amp; Stone</title>"
            f"<style>{CSS}</style></head><body><nav><span class=brand>Kettle &amp; Stone</span>{links}</nav>"
            f"<main>{body}</main></body></html>")


def _day(text):
    return f"{date.fromisoformat(text):%a %b %d}"


def _short(when):
    """'2026-10-30 10:02' -> 'Fri Oct 30, 10:02'"""
    return f"{datetime.strptime(when, '%Y-%m-%d %H:%M'):%a %b %d, %H:%M}"


def drift_box(people):
    """More than 1 in 10 people held: the notebook's style may have changed (plan §7.4, the drift alarm)."""
    held = sum(p["status"] == "review" for p in people)
    if not people or held * 10 <= len(people):
        return ""
    return (f"<div class='box warn'><b>{held} of {len(people)} people are held for review.</b> That's more than 1 in "
            f"10: the way the book is written may have changed. Check before trusting short lists.</div>")


def gap_box(gaps):
    if not gaps:
        return ""
    items = "".join(f"<li>no booking data for visits on {g[0]:%b %d}"
                    + ("" if g[0] == g[1] else f" to {g[1]:%b %d}") + "</li>" for g in gaps)
    return (f"<div class='box warn'><b>Gap in the booking history.</b> Anyone who booked a visit in these days may "
            f"still be listed. Check Kneadly before calling.<ul class=plain>{items}</ul></div>")


# ---------- openings ----------

def opening_card(o, rows, people_by_line, first_name, desk=None, now=None, desk_name=None):
    """One opening: when, who it fits (up to 3), why the closest others don't, and the desk's next step.
    `desk`: the opening's offers, hold and refill (store.desk_state); `desk_name`: who's at the desk."""
    shown = [r for r in rows if r["rank"] > 0]
    nobody = next((r for r in rows if r["rank"] == 0), None)
    closest = [r for r in rows if r["rank"] < 0]
    no_show = "no-show" in o["kind"].lower() or "no show" in o["kind"].lower()
    meta = [esc(o["opening_id"])]
    if o["cancelled_at"]:
        when = datetime.strptime(o["cancelled_at"], "%Y-%m-%d %H:%M")
        label = "no-show" if no_show else "cancelled"
        meta.append(f"{label} {when:%H:%M}" if when.date().isoformat() == o["date"] else f"{label} {when:%a %H:%M}")
    if o.get("heard_via") and not no_show:
        meta.append(f"heard via {esc(o['heard_via'])}")
    if shown:
        meta.append(f"<a href='/compare?opening={esc(o['appointment_id'])}'>compare orders</a>")
    state = desk or {"status": "new", "offers": [], "live": None, "rebooking": None}
    head = (f"<div class=op-head><span class=op-when>{_day(o['date'])} · {esc(o['start'])}</span>"
            f"<span class=op-what>{esc(first_name(o['therapist']))} · {o['length_min']} min · "
            f"{o['hours_notice']:g} h notice</span><span class=op-meta>{' · '.join(meta)}</span>"
            f"{status_chip(state, now)}</div>")
    closed = state["status"] in ("filled", "taken", "released")
    offered = {x["line"]: x for x in state["offers"]}
    can_offer = state["status"] == "held" and not state["live"] and desk_name and not no_show
    items = ""
    for r in shown:
        person = people_by_line.get(r["line"], {})
        flags = "".join(f"<span class=flag>{esc(f)}</span>" for f in r["flags"].split("; ") if f)
        if r["line"] in offered:
            act = f"<span class=outcome>{esc(outcome_words(offered[r['line']]))}</span>"
        elif can_offer:
            act = (f"<form method=post action='/opening' class=inline>{_hidden(o['appointment_id'], 'offer')}"
                   f"<input type=hidden name=line value={r['line']}><button class=primary>Offer</button></form>")
        else:
            act = ""
        items += (f"<li><span class=rank>{r['rank']}</span><span class=name>{esc(r['person'])}</span>"
                  f"<span class=phone>{esc(phone_display(person.get('phone')))}</span>"
                  f"<span class=lineno>line {r['line']}</span><span>{esc(r['can_take'])}{flags}</span>"
                  f"<span class=act>{act}</span></li>")
    body = f"<ol class=names>{items}</ol>" if items and not closed else ""
    earlier = [x for x in state["offers"] if x["line"] not in {r["line"] for r in shown} and x["outcome"] != "yes"]
    if earlier and not closed:
        body += ("<p class=closest>Already offered: "
                 + " · ".join(f"<b>{esc(x['person'])}</b> ({esc(outcome_words(x))})" for x in earlier) + "</p>")
    if nobody and not closed:
        text = "No-show: never offered" if no_show else "Nobody on the list fits"
        body += f"<p class=nobody-note>{text}</p>"
    if closest and not no_show and not closed:
        body += ("<p class=closest>Not offered: "
                 + " · ".join(f"<b>{esc(r['person'])}</b> ({esc(r['can_take'])})" for r in closest) + "</p>")
    if not no_show and (shown or state["status"] != "new"):
        body += desk_panel(o, state, now, desk_name)
    return (f"<section id='o-{esc(o['appointment_id'])}' class='opening{' nobody' if not shown or closed else ''}'>"
            f"{head}{body}</section>")


def _hidden(appointment_id, do):
    return f"<input type=hidden name=opening value='{esc(appointment_id)}'><input type=hidden name=do value='{do}'>"


def _minutes(since, now):
    return int((now - datetime.strptime(since, "%Y-%m-%d %H:%M")).total_seconds() // 60) if now else 0


def outcome_words(offer):
    at = offer["outcome_at"][11:] if offer["outcome_at"] else ""
    return {None: "offered now", "yes": f"said yes {at}", "no": f"said no {at}", "no answer": f"no answer {at}",
            "withdrawn": f"offer withdrawn {at}"}[offer["outcome"]]


def status_chip(state, now):
    status, live = state["status"], state["live"]
    if status == "held" and live:
        return (f"<span class='chip live'>Offering to {esc(live['person'])} · {esc(live['offered_by'])} · "
                f"{_minutes(live['offered_at'], now)} min</span>")
    if status == "held":
        return f"<span class='chip held'>Held in Kneadly since {esc(state['hold_placed_at'][11:])}</span>"
    if status == "filled" and state["rebooking"]:
        return f"<span class='chip done'>Filled: {esc(state['rebooking']['person'])}</span>"
    if status == "taken":
        return f"<span class='chip done'>Taken: {esc(state['closed_how'])}</span>"
    if status == "released":
        return f"<span class='chip done'>Released: {esc(state['closed_how'])}</span>"
    return ""


def desk_panel(o, state, now, desk_name):
    """The next step for this opening (plan §10.1): hold, offer one at a time, answer, close."""
    aid, status, live = o["appointment_id"], state["status"], state["live"]
    if not desk_name and status in ("new", "held"):
        return "<p class=desk-note>Say who's at the desk (top of the page) to start offering.</p>"
    if status == "new":
        return (f"<form method=post action='/opening' class='desk-step'>"
                f"<input type=hidden name=opening value='{esc(aid)}'><input type=hidden name=how value='booked online'>"
                f"<p><b>Before the first call:</b> check in Kneadly that this slot is still free, then block the time "
                f"there so the online page can't give it away.</p><div class=actions>"
                f"<label class=tick><input type=checkbox name=checked value=yes required> It's still free, and I "
                f"blocked it</label><button class=primary name=do value=hold>Hold placed</button>"
                f"<button class=plain name=do value=taken formnovalidate>Already taken in Kneadly</button></div></form>")
    if status == "held" and live:
        mins = _minutes(live["offered_at"], now)
        late = "<span class=hint> · 20 minutes: if there's no answer, move on.</span>" if mins >= 20 else ""
        return (f"<form method=post action='/opening' class='desk-step'>{_hidden(aid, 'answer')}"
                f"<input type=hidden name=offer value={live['id']}><p><b>Offered to {esc(live['person'])}</b> by "
                f"{esc(live['offered_by'])} at {esc(live['offered_at'][11:])} ({mins} min){late}</p>"
                f"<div class=actions><button class=primary name=answer value=yes>Yes</button>"
                f"<label class=tick>Why not, if they said <select name=why><option></option>"
                + "".join(f"<option>{esc(r)}</option>" for r in DECLINE_REASONS) + "</select></label>"
                f"<button class=plain name=answer value=no>No</button>"
                f"<button class=plain name=answer value='no, keep me on'>No, keep me on</button>"
                f"<button class=plain name=answer value='no answer'>No answer</button></div></form>")
    if status == "held":
        how = "".join(f"<option>{esc(h)}</option>" for h in ("a client called in", "booked online", "another way"))
        return (f"<div class='desk-step actions'><span class=hint>Offer one at a time, from the top.</span>"
                f"<form method=post action='/opening' class=inline>{_hidden(aid, 'taken')}<select name=how>{how}</select>"
                f"<button class=plain>Filled another way</button></form>"
                f"<form method=post action='/opening' class=inline>{_hidden(aid, 'release')}<label class=tick>"
                f"<input type=checkbox name=checked value=yes required> I removed the block in Kneadly</label>"
                f"<button class=plain>Nobody left: release</button></form></div>")
    if status == "filled" and state["rebooking"]:
        r = state["rebooking"]
        where = (f"booked in Kneadly{' (' + esc(r['kneadly_id']) + ')' if r['kneadly_id'] else ''}" if r["in_kneadly"]
                 else "hold kept with their name; book it in Kneadly at check-in" if r["how"] == "book at check-in"
                 else "new client: create the profile in Kneadly when they arrive")
        return (f"<form method=post action='/opening' class='desk-step'>{_hidden(aid, 'undo_yes')}"
                f"<input type=hidden name=rebooking value={r['id']}><p><b>Filled:</b> {esc(r['person'])} · "
                f"{r['length_min']} min · {where}</p><button class=plain>Undo: not filled</button></form>")
    if status in ("taken", "released"):
        return (f"<form method=post action='/opening' class='desk-step'>{_hidden(aid, 'reopen')}"
                f"<button class=plain>Reopen</button></form>")
    return ""


def desk_box(desk_name):
    """Who's at the desk: remembered by this browser, shown next to offers so two people can't both call."""
    if desk_name:
        return (f"<form method=post action='/desk' class='box desk'>At the desk: <b>{esc(desk_name)}</b> "
                f"<input type=hidden name=name value=''><button class=plain>Change</button></form>")
    return ("<form method=post action='/desk' class='box desk warn'><label class=who>Who's at the desk? "
            "<input name=name required maxlength=40 autocomplete=name></label> <button class=primary>Start</button>"
            "<p class=hint>Shown next to each offer, so two people at the desk never call about the same slot.</p></form>")


def resting_box(resting, limit):
    """People at the weekly offer limit (anti-pestering): skipped until the date shown, so others are called first."""
    if not resting:
        return ""
    names = " · ".join(f"<b>{esc(name)}</b> until {until:%a %b %d}" for name, until in resting)
    return (f"<div class=box><b>Resting this week</b> (offered {limit} times in 7 days, the clinic's limit): "
            f"{names}. They aren't offered anything else until then.</div>")


def queue_page(view, gaps, saved, first_name, desk_name=None, now=None, todo=0, resting=(), limit=0, held=None):
    if view is None:
        return layout("Openings", "<h1>Openings</h1><div class=box>Nothing has been uploaded yet. "
                                  "<a href='/upload'>Upload the files</a> to fill the database.</div>", "/", held)
    run, sync, people = view["run"], view["sync"], view["people"]
    people_by_line = {line: p for p in people for line in p["lines"]}
    counts = {s: sum(p["status"] == s for p in people) for s in ("active", "stale", "review")}
    def upcoming_first(o):  # the next opening to work on at the top; past ones after, still soonest first
        starts = datetime.strptime(f"{o['date']} {o['start']}", "%Y-%m-%d %H:%M")
        return (bool(now) and starts < now, o["date"], o["start"])
    openings = sorted(view["openings"], key=upcoming_first)
    named = sum(1 for o in openings if any(r["rank"] > 0 for r in view["rows"][o["appointment_id"]]))
    files = ", ".join(esc(f) for f in (sync["waitlist_file"], sync["appointments_file"], sync["openings_file"]) if f)
    warnings = view["summary"].get("run_warnings", [])
    out = [f"<h1>Openings</h1><p class=sub>Run date {_day(run['run_date'])} · order: {esc(run['order_mode'])} · "
           f"call #1 first, one offer at a time</p>"]
    if saved:
        out.append(f"<div class='box ok'>Saved sync #{esc(saved)}. The openings below are from it.</div>")
    out.append(desk_box(desk_name))
    if todo:
        out.append(f"<div class='box warn'><b>Daily check:</b> {count(todo, 'thing')} to finish. "
                   f"<a href='/check'>See what</a>.</div>")
    out.append(gap_box(gaps))
    out.append(drift_box(people))
    out.append(resting_box(resting, limit))
    out.append(f"<div class=box><ul class=facts><li><b>Last sync:</b> #{sync['id']}, {_short(sync['synced_at'])}"
               f"{' (' + files + ')' if files else ''}</li>"
               f"<li><b>Bookings:</b> {view['bookings']['count']} (visits {esc(view['bookings']['first'])} to "
               f"{esc(view['bookings']['last'])})</li>"
               f"<li><b>Waitlist:</b> {len(people)} people: {counts['active']} active, {counts['stale']} out of date, "
               f"{counts['review']} held for review</li></ul>")
    if counts["review"]:
        out.append(f"<p class=sub style='margin:8px 0 0'>People held for review are never offered: "
                   f"<a href='/review'>check {people_count(counts['review'])}</a>.</p>")
    out.append("<p class=files style='margin:10px 0 0'><b>Files from this sync:</b> "
               + "".join(f"<a href='/files/{n}'>{n}</a>" for n in
                         ("matches.txt", "matches.csv", "preprocess-report.txt", "line-verdicts.csv", "sync-log.txt"))
               + "</p></div>")
    if warnings:
        out.append(f"<details class='box warn'><summary><b>{len(warnings)} warning(s)</b></summary><ul class=plain>"
                   + "".join(f"<li>{esc(w)}</li>" for w in warnings) + "</ul></details>")
    out.append(f"<p class=sub>{count(len(openings), 'opening')}: {named} with names, {len(openings) - named} with nobody. "
               f"Coming up first, soonest at the top; past ones after.</p>")
    desk = view.get("desk", {})
    out += [opening_card(o, view["rows"][o["appointment_id"]], people_by_line, first_name, desk.get(o["appointment_id"]),
                         now, desk_name) for o in openings]
    return layout("Openings", "".join(out), "/", held)


# ---------- offers: the booking card and the daily check ----------

def booking_page(o, offer, person, lengths, first_name, error=None, held=None):
    """On a yes, before telling the client "you're booked" (plan §10.1 step 5, §10.3): how this refill goes
    into Kneadly. `lengths`: what the person can take that fits the opening, longest first."""
    new_client = bool(person.get("new_client"))
    choices = (("booked now", "I've booked it in Kneadly now", "Kneadly appointment number (optional) "
                "<input name=kneadly_id maxlength=20 class=num>"),
               ("book at check-in", "Keep the hold with their name; book it in Kneadly at check-in",
                "For a visit within about 2 hours."),
               ("new client", "New client: keep the hold with their name; profile and intake form when they arrive",
                "No Kneadly profile yet, so no text consent."))
    default = "new client" if new_client else "booked now"
    radios = "".join(f"<label class=tick style='display:block;margin:6px 0'><input type=radio name=how value='{v}'"
                     f"{' checked' if v == default else ''} required> <b>{esc(text)}</b> <span class=hint>{hint}</span>"
                     f"</label>" for v, text, hint in choices)
    err = f"<div class='box err'><b>Not saved.</b> {esc(error)}</div>" if error else ""
    body = (f"<h1>Confirm the refill</h1><p class=sub>{esc(o['opening_id'])} · {_day(o['date'])} {esc(o['start'])} · "
            f"{esc(first_name(o['therapist']))} · {o['length_min']} min · rebooked into {esc(o['appointment_id'])}</p>{err}"
            f"<form class=box method=post action='/opening'>{_hidden(o['appointment_id'], 'book')}"
            f"<input type=hidden name=offer value={offer['id']}>"
            f"<p><b>{esc(offer['person'])}</b> · {esc(phone_display(offer['phone']))} · line {offer['line']}"
            f"{' · <span class=flag>new client, phone only</span>' if new_client else ''}</p>"
            f"<div class=field><label for=length>Length</label><select id=length name=length>"
            + "".join(f"<option>{n}</option>" for n in lengths) + "</select></div>"
            f"<div class=field><label>How it goes into Kneadly</label>{radios}</div>"
            f"<div class=field><label class=tick><input type=checkbox name=checked value=yes required> I checked "
            f"Kneadly: our hold is still there, so the slot is theirs</label></div>"
            f"<div class=actions><button class=primary>Save: filled</button>"
            f"<a class='button plain' href='/#o-{esc(o['appointment_id'])}'>Back</a></div></form>"
            f"<p class=hint>Only tell them they're booked after this is saved.</p>")
    return layout("Confirm the refill", body, "/", held)


def check_page(not_in_kneadly, passed_holds, waiting, now, held=None):
    """The daily check (plan §10.3): what still has to be finished in Kneadly."""
    out = ["<h1>Daily check</h1><p class=sub>Refills that aren't in Kneadly yet, and slots still blocked. "
           "Every refill has to be in Kneadly by the end of the visit.</p>"]
    if not (not_in_kneadly or passed_holds or waiting):
        out.append("<div class='box ok'>Nothing to finish.</div>")
    if not_in_kneadly:
        rows = "".join(
            f"<tr><td>{esc(r['label'])}</td><td>{esc(r['person'])}</td><td>{esc(r['how'])}</td><td>"
            f"<form method=post action='/opening' class=inline>{_hidden(r['appointment_id'], 'in_kneadly')}"
            f"<input type=hidden name=rebooking value={r['id']}><input name=kneadly_id maxlength=20 class=num "
            f"placeholder='number'> <button class=plain>It's in Kneadly now</button></form></td></tr>"
            for r in not_in_kneadly)
        out.append(f"<h2>Refills not in Kneadly yet</h2><table><tr><th>Opening</th><th>Client</th><th>How</th><th></th>"
                   f"</tr>{rows}</table>")
    if passed_holds:
        rows = "".join(
            f"<tr><td>{esc(o['opening_id'])} · {_day(o['date'])} {esc(o['start'])}</td><td>blocked since "
            f"{esc(s['hold_placed_at'][11:])}, never filled or released</td><td>"
            f"<form method=post action='/opening' class=inline>{_hidden(o['appointment_id'], 'release')}"
            f"<input type=hidden name=how value='passed'><label class=tick><input type=checkbox name=checked "
            f"value=yes required> I removed the block in Kneadly</label><button class=plain>Done</button></form>"
            f"</td></tr>" for o, s in passed_holds)
        out.append(f"<h2>Slots still blocked after their start time</h2><table><tr><th>Opening</th><th></th><th></th>"
                   f"</tr>{rows}</table>")
    if waiting:
        rows = "".join(f"<tr><td><a href='/#o-{esc(o['appointment_id'])}'>{esc(o['opening_id'])} · {_day(o['date'])} "
                       f"{esc(o['start'])}</a></td><td>{esc(s['live']['person'])}</td>"
                       f"<td>{_minutes(s['live']['offered_at'], now)} min without an answer</td></tr>"
                       for o, s in waiting)
        out.append(f"<h2>Offers waiting more than 20 minutes</h2><table>{rows}</table>")
    return layout("Daily check", "".join(out), "/", held)


# ---------- upload ----------

def upload_page(today, empty_db, error=None, held=None):
    first = ("<div class=box>This is the first upload: the waitlist file is needed. Appointments and late "
             "openings too, if you have them.</div>") if empty_db else ""
    err = f"<div class='box err'><b>Nothing was saved.</b> {esc(error)}</div>" if error else ""
    fields = [
        ("waitlist", "Waitlist (the green book)",
         "The whole book every time. Only lines with new numbers are added; a changed old line is held for review."),
        ("appointments", "Appointments (booking export)",
         "Any period. Added to the booking history, never swapped in."),
        ("openings", "Late openings",
         "These are the openings that get matched. Leave it out to match every opening already saved."),
    ]
    inputs = "".join(f"<div class=field><label for={k}>{label}</label><p class=hint>{hint}</p>"
                     f"<input type=file id={k} name={k} accept='.csv,text/csv'></div>" for k, label, hint in fields)
    body = (f"<h1>Upload</h1><p class=sub>Nothing is saved until you've checked what will change.</p>{err}{first}"
            f"<form class=box method=post action='/upload/check' enctype='multipart/form-data'>{inputs}"
            f"<div class=field><label for=run_date>Run date</label><p class=hint>The day to count from: "
            f"today, or the day the files are from.</p><input type=date id=run_date name=run_date "
            f"value='{today.isoformat()}' required></div>"
            f"<div class=actions><button class=primary type=submit>Check files</button></div></form>")
    return layout("Upload", body, "/upload", held)


def preview_page(token, names, check, held=None):
    s = check["summary"]
    rows = []
    if "waitlist" in s:
        w = s["waitlist"]
        changed = (f"<b>{line_ranges(w['changed'])}</b> (those people are held until someone checks the book)"
                   if w["changed"] else "none")
        rows.append(f"<tr><th>Waitlist</th><td>{esc(names['waitlist'])}</td><td>{w['lines']} lines · new lines: "
                    f"{line_ranges(w['new'])} · changed: {changed} · already saved: {w['unchanged']}"
                    + (f" · not in this file: {line_ranges(w['missing'])}" if w["missing"] else "") + "</td></tr>")
    if "appointments" in s:
        a = s["appointments"]
        rows.append(f"<tr><th>Appointments</th><td>{esc(names['appointments'])}</td><td>{a['rows']} rows, visits "
                    f"{_day(a['visits'][0])} to {_day(a['visits'][1])} · new: {a['new']} · already saved: "
                    f"{a['updated']} · status changes: {a['status_changes']}</td></tr>")
    if "openings" in s:
        o = s["openings"]
        rows.append(f"<tr><th>Late openings</th><td>{esc(names['openings'])}</td><td>{count(o['rows'], 'opening')} · new: "
                    f"{o['new']} · already saved: {o['rows'] - o['new']}</td></tr>")
    p = check["people"]
    after = (f"<ul class=facts><li><b>Waitlist after saving:</b> {p['total']} people: {p['active']} active, "
             f"{p['stale']} out of date, {p['review']} held for review</li>"
             f"<li><b>Openings to match:</b> {check['openings']} ({check['named']} with names)</li></ul>")
    warnings = check["warnings"]
    warn = (f"<div class='box warn'><b>{len(warnings)} warning(s)</b><ul class=plain>"
            + "".join(f"<li>{esc(w)}</li>" for w in warnings) + "</ul></div>") if warnings else ""
    body = (f"<h1>Check before saving</h1><p class=sub>Run date {_day(check['run_date'])}. Nothing has been saved "
            f"yet.</p><table><tr><th>File</th><th>Name</th><th>What will change</th></tr>{''.join(rows)}</table>"
            f"<div class=box style='margin-top:14px'>{after}</div>{gap_box(check['gaps'])}{warn}"
            f"<div class=actions><form method=post action='/upload/save'><input type=hidden name=token value='{esc(token)}'>"
            f"<button class=primary type=submit>Save and match</button></form>"
            f"<form method=post action='/upload/cancel'><input type=hidden name=token value='{esc(token)}'>"
            f"<button class=plain type=submit>Cancel</button></form></div>")
    return layout("Check before saving", body, "/upload", held)


# ---------- sync log ----------

def log_page(history, held=None):
    if not history:
        return layout("Sync log", "<h1>Sync log</h1><div class=box>No syncs yet.</div>", "/log", held)
    rows = []
    for h in reversed(history):
        s = h["summary"]
        parts = []
        if "waitlist" in s:
            w = s["waitlist"]
            parts.append(f"waitlist {esc(h['waitlist_file'])}: {w['lines']} lines, new {line_ranges(w['new'])}, "
                         f"changed {line_ranges(w['changed'])}")
        if "appointments" in s:
            a = s["appointments"]
            parts.append(f"appointments {esc(h['appointments_file'])}: visits {_day(a['visits'][0])} to "
                         f"{_day(a['visits'][1])}, {a['new']} new, {a['status_changes']} status changes")
        if "openings" in s:
            parts.append(f"openings {esc(h['openings_file'])}: {s['openings']['rows']}, {s['openings']['new']} new")
        warnings = s.get("warnings", [])
        rows.append(f"<tr><td>#{h['id']}</td><td>{_short(h['synced_at'])}</td><td>{_day(h['run_date'])}</td>"
                    f"<td>{'<br>'.join(parts) or 'matched again: ' + esc(s.get('note') or 'no files')}</td>"
                    f"<td>{'<br>'.join(esc(w) for w in warnings) or 'none'}</td></tr>")
    body = ("<h1>Sync log</h1><p class=sub>Every upload, newest first. File names only: the files themselves "
            "aren't kept.</p><table><tr><th>#</th><th>When</th><th>Run date</th><th>What changed</th>"
            f"<th>Warnings</th></tr>{''.join(rows)}</table>")
    return layout("Sync log", body, "/log", held)


def message_page(title, text, held=None):
    return layout(title, f"<h1>{esc(title)}</h1><div class=box>{esc(text)}</div>", "", held)


# ---------- needs review ----------

IDENTITY_RE = re.compile(r"^check identity: line (\d+) (.*)$")
LINE_RE = re.compile(r"line (\d+)")
DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat")
NOTICE_CHOICES = (("", "Not said (2 h)"), ("0.5", "30 min"), ("1", "1 h"), ("2", "2 h"), ("3", "3 h"), ("4", "4 h"),
                  ("day", "The day before"))
CONTACT_CHOICES = (("", "Not said"), ("text only", "Text only"), ("call (landline)", "Call (landline)"))


def review_actions(person):
    """Which decisions fit this person's reasons for being held."""
    pairs, single, changed = [], [], []
    fill = regular = False
    for reason in person["reasons"]:
        m = IDENTITY_RE.match(reason)
        if m:
            own, others = int(m.group(1)), [int(x) for x in LINE_RE.findall(m.group(2))]
            if others and others[0] not in {other for _, other in pairs}:  # one question per other line
                pairs.append((own, others[0]))
            elif not others and own not in single:
                single.append(own)
        elif reason.startswith("regular who wanted an extra visit"):
            regular = True
        elif re.match(r"^line \d+: ", reason):
            fill = True
            if "changed since it was first saved" in reason:
                changed.append(int(LINE_RE.match(reason).group(1)))
    return {"pairs": pairs, "single": single, "fill": fill, "changed": changed, "regular": regular}


def describe(d):
    kind, line, other = d["kind"], d["line"], d["other_line"]
    return {"same person": f"Lines {line} and {other}: same person",
            "different people": f"Lines {line} and {other}: different people",
            "ignore": f"Line {line} left out",
            "start over": f"{esc(d['name'])}: filled in what they can take (entry {d['desk_line']})",
            "still wants it": f"{esc(d['name'])}: still wants an extra visit (entry {d['desk_line']})",
            "take off": f"{esc(d['name'])}: taken off the list (entry {d['desk_line']})",
            "keep new text": f"Line {line}: new text kept",
            "card edit": f"{esc(d['name'])}: card changed ({esc(d.get('summary') or '')}) (entry {d['desk_line']})",
            "still interested": f"{esc(d['name'])}: still interested (entry {d['desk_line']})",
            "add": f"{esc(d['name'])}: added on the board (entry {d['desk_line']})"}.get(kind, esc(kind))


def held_card(person):
    a = review_actions(person)
    first = person["lines"][0]
    rows = []  # one row per question, so each set of buttons reads on its own
    for x, y in a["pairs"]:
        rows.append(f"<span class=pair>Line {y} and this person:</span>"
                    f"<button class=primary name=choice value='same person|{y}|{x}'>Same person</button>"
                    f"<button class=primary name=choice value='different people|{y}|{x}'>Different people</button>"
                    f"<button class=plain name=choice value='ignore|{y}|'>Leave line {y} out</button>")
    for x in a["single"]:
        rows.append(f"<span class=pair>Line {x} is the same person as line</span><input type=number name=other_{x} "
                    f"min=1 class=num><button class=primary name=choice value='same person|{x}|?'>Same person</button>"
                    f"<button class=plain name=choice value='ignore|{x}|'>Leave line {x} out</button>")
    for x in a["changed"]:
        rows.append(f"<span class=pair>Line {x} changed in the book:</span>"
                    f"<button class=primary name=choice value='keep new text|{x}|'>Keep the new text</button>")
    last = []
    if a["regular"]:
        last.append(f"<button class=primary name=choice value='still wants it|{first}|'>Still wants an extra visit</button>")
    if a["fill"]:
        last.append(f"<a class='button primary' href='/review/fill?line={first}'>Fill in what they can take</a>")
    last.append(f"<button class=plain name=choice value='take off|{first}|'>Take off the list</button>")
    rows.append("".join(last))
    reasons = "".join(f"<li>{esc(r)}</li>" for r in person["reasons"])
    lines = ("line " if len(person["lines"]) == 1 else "lines ") + ", ".join(str(n) for n in person["lines"])
    asked = f" · asked {_day(person['first_asked'])}" if person["first_asked"] else ""
    return (f"<section class='opening held'><div class=op-head><span class=op-when>{esc(person['name'])}</span>"
            f"<span class=phone>{esc(phone_display(person['phone']))}</span><span class=op-meta>{lines}{asked}"
            f"</span></div><ul class=plain>{reasons}</ul>"
            f"<form method=post action='/review/decide' class=decide><input type=hidden name=person value={first}>"
            f"<label class=who>Your name <input name=checked_by required maxlength=40 autocomplete=name></label>"
            + "".join(f"<div class=actions>{r}</div>" for r in rows) + "</form></section>")


def review_page(people, decisions, warnings, done=False, error=None, held=None):
    held_people = [p for p in people if p["status"] == "review"]
    out = ["<h1>Needs review</h1><p class=sub>These people are never offered until someone checks the book and "
           "decides. Nothing is released by itself, and every decision can be undone.</p>"]
    if done:
        out.append("<div class='box ok'>Saved. The openings were matched again.</div>")
    if error:
        out.append(f"<div class='box err'><b>Not saved.</b> {esc(error)}</div>")
    out.append(drift_box(people))
    if not people:
        out.append("<div class=box>Nothing has been uploaded yet.</div>")
    elif not held_people:
        out.append("<div class=box>Nobody is held for review.</div>")
    out += [held_card(p) for p in held_people]
    if decisions:
        rows = "".join(
            f"<tr><td>{_short(d['made_at'])}</td><td>{describe(d)}</td><td>"
            + (f"undone {_short(d['undone_at'])}" if d["undone_at"] else
               f"<form method=post action='/review/undo'><input type=hidden name=id value={d['id']}>"
               f"<button class=plain type=submit>Undo</button></form>")
            + "</td></tr>" for d in decisions)
        out.append(f"<h2>Recent decisions</h2><table><tr><th>When</th><th>Decision</th><th></th></tr>{rows}</table>")
    if warnings:
        out.append("<h2>Warnings from the last run</h2><div class='box warn'><ul class=plain>"
                   + "".join(f"<li>{esc(w)}</li>" for w in warnings) + "</ul></div>")
    return layout("Needs review", "".join(out), "/review", held)


def fill_page(person, therapists, prefill, rules=(), error=None, mode="review", values=None, held=None):
    """The card: what a person can take. Saving it is a 'start over': their older lines stop counting for what they
    can take, but they keep their place in the queue. `mode`: "review" (a held person, filled in from the book),
    "board" (Edit card on the waitlist board) or "add" (a new person, `person` None; `values` = name and phone).
    `therapists`: (full name, first name) pairs; `rules`: (tag, chip label) per routing rule."""
    p = prefill

    def checked(on):
        return " checked" if on else ""

    def box(name, value, label, on):
        return (f"<label class=tick><input type=checkbox name={name} value='{esc(value)}'{checked(on)}> "
                f"{esc(label)}</label>")

    def radio(value, label):
        return f"<label class=tick><input type=radio name=who value={value}{checked(p['who'] == value)}> {label}</label>"

    def select(name, choices, current):
        options = "".join(f"<option value='{esc(v)}'{' selected' if v == current else ''}>{esc(t)}</option>"
                          for v, t in choices)
        return f"<select name={name} id={name}>{options}</select>"

    def time_input(name, label):
        return f"<label class=tick>{label} <input type=time name={name} value='{esc(p.get(name) or '')}'></label>"

    def date_input(name, label):
        return f"<label class=tick>{label} <input type=date name={name} value='{esc(p.get(name) or '')}'></label>"

    v = values or {}
    first = person["lines"][0] if person else None
    err = f"<div class='box err'><b>Not saved.</b> {esc(error)}</div>" if error else ""
    if mode == "add":
        top = ("<h1>Add someone to the waitlist</h1><p class=sub>A card instead of a line in the book. No notes box: "
               "only what decides who to call.</p>")
        start = (f"<form class=box method=post action='/board'><input type=hidden name=do value=add><div class=grid>"
                 f"<div class=field><label for=name>Name</label><input id=name name=name required maxlength=60 "
                 f"value='{esc(v.get('name', ''))}'></div><div class=field><label for=phone>Phone</label><input id=phone "
                 f"name=phone required maxlength=20 value='{esc(v.get('phone', ''))}'></div></div>")
    elif mode == "board":
        top = (f"<h1>Card: {esc(person['name'])}</h1><p class=sub>Lines {', '.join(str(n) for n in person['lines'])}. "
               f"Change what they can take; saving replaces the whole card, and they keep their place in the queue. "
               f"A newer line in the book still overrides it.</p>")
        start = (f"<form class=box method=post action='/board'><input type=hidden name=do value=card>"
                 f"<input type=hidden name=line value={first}>")
    else:
        top = (f"<h1>Fill in: {esc(person['name'])}</h1><p class=sub>Lines {', '.join(str(n) for n in person['lines'])}. "
               f"Check every field against the book: these are only what could be read. Saving replaces what their "
               f"older lines say they can take; they keep their place in the queue.</p>")
        start = (f"<form class=box method=post action='/review/decide'><input type=hidden name=person value={first}>"
                 f"<input type=hidden name=choice value='start over|{first}|'>")
    name_field = ("<div class=field><label for=checked_by>Your name</label><input id=checked_by name=checked_by "
                  "required maxlength=40 autocomplete=name></div>") if mode == "review" else ""
    back = "/review" if mode == "review" else (f"/board#p-{first}" if first else "/board")
    body = (
        top + err + start
        + f"<div class=field><label>Therapist</label>{radio('any', 'Any therapist')}<br>{radio('only', 'Only:')}"
        + "".join(box("only", full, short, full in p["only"]) for full, short in therapists)
        + f"<br>{radio('but', 'Anyone but:')}"
        + "".join(box("but", full, short, full in p["but"]) for full, short in therapists)
        + f"<br>{box('female', 'yes', 'Female therapist only', p['female'])}"
        + "".join(box("needs", tag, f"{chip} (desk only, never shown to clients)", tag in p["needs"]) for tag, chip in rules)
        + f"</div><div class=field><label>Length</label><p class=hint>None ticked = 60 min.</p>"
        + "".join(box("length", str(n), f"{n} min", n in p["lengths"]) for n in (30, 45, 60, 90)) + "</div>"
        f"<div class=field><label>Days</label><p class=hint>None ticked = any day.</p>"
        + "".join(box("day", d, d, d in p["days"]) for d in DAYS) + "</div>"
        f"<div class=field><label>Time</label><p class=hint>Leave empty for any time.</p>"
        f"{time_input('from', 'Starts from')}{time_input('before', 'Starts before')}{time_input('done_by', 'Done by')}"
        f"</div><div class=field><label for=notice>Notice needed</label>{select('notice', NOTICE_CHOICES, p['notice'])}"
        f"</div><div class=field><label>Dates</label>{date_input('available_from', 'Available from')}"
        f"{date_input('available_until', 'Available until')}</div>"
        f"<div class=field><label for=contact>Contact</label>{select('contact', CONTACT_CHOICES, p['contact'])} "
        f"{box('new_client', 'yes', 'New client (no Kneadly profile: phone only)', p['new_client'])}</div>"
        f"{name_field}<div class=actions><button class=primary type=submit>Save</button>"
        f"<a class='button plain' href='{back}'>Cancel</a></div></form>")
    title = {"add": "Add someone", "board": "Card"}.get(mode, "Fill in")
    return layout(title, body, "/review" if mode == "review" else "/board", held)


# ---------- settings ----------

def problems_box(problems, title="Nothing was saved."):
    if not problems:
        return ""
    return (f"<div class='box err'><b>{esc(title)}</b> Fix these first:<ul class=plain>"
            + "".join(f"<li>{esc(p)}</li>" for p in problems) + "</ul></div>")


def settings_page(raw, orders, versions, paused, file_note=None, problems=(), saved=False, notice=None, held=None):
    """The settings form, the owner's pause switch and the saved versions. `raw`: the settings as in
    config/clinic.json (or as just sent, when there are problems to fix)."""
    d, tw = raw.get("defaults", {}), raw.get("time_words", {})

    def field(name, label, value, kind="number", step="1", hint=""):
        hint = f"<p class=hint>{hint}</p>" if hint else ""
        return (f"<div class=field><label for={name}>{label}</label>{hint}<input type={kind} id={name} name={name} "
                f"value='{esc(value)}' step={step} required></div>")

    def opt(value, current, text):
        return f"<option value='{esc(value)}'{' selected' if str(value) == str(current) else ''}>{esc(text)}</option>"
    order_radios = "".join(
        f"<label class=tick><input type=radio name=order value='{o}'{' checked' if d.get('order') == o else ''}> "
        f"<b>{esc(o)}</b>: {esc(words)}</label><br>" for o, words in orders)
    rows = ""
    for i, (name, t) in enumerate(raw.get("therapists", {}).items()):
        rows += (f"<tr><td><input type=hidden name=t{i}_name value='{esc(name)}'><b>{esc(name)}</b></td>"
                 f"<td><input name=t{i}_aliases value='{esc(', '.join(t.get('aliases', [])))}' class=wide></td>"
                 f"<td><input type=checkbox name=t{i}_female value=yes{' checked' if t.get('female') else ''} "
                 f"aria-label='{esc(name)} female'></td>"
                 f"<td><input type=checkbox name=t{i}_prenatal value=yes{' checked' if t.get('prenatal_trained') else ''} "
                 f"aria-label='{esc(name)} prenatal-trained'></td>"
                 f"<td><input name=t{i}_tags value='{esc(', '.join(sorted(set(t.get('tags', [])) - {'female', 'prenatal-trained'})))}' "
                 f"class=wide aria-label='{esc(name)} other tags'></td>"
                 f"<td><select name=t{i}_approval>{opt('none', t.get('approval'), 'takes anyone')}"
                 f"{opt('see_first', t.get('approval'), 'ask first')}</select></td>"
                 f"<td><input type=checkbox name=t{i}_remove value=yes aria-label='remove {esc(name)}'></td></tr>")
    rows += ("<tr><td><input name=new_name placeholder='New therapist: first and last name' class=wide></td>"
             "<td><input name=new_aliases placeholder='e.g. sophie, s' class=wide></td>"
             "<td><input type=checkbox name=new_female value=yes aria-label='new therapist female'></td>"
             "<td><input type=checkbox name=new_prenatal value=yes aria-label='new therapist prenatal-trained'></td>"
             "<td><input name=new_tags class=wide aria-label='new therapist other tags'></td>"
             f"<td><select name=new_approval>{opt('none', 'none', 'takes anyone')}{opt('see_first', '', 'ask first')}"
             "</select></td><td></td></tr>")
    nicknames = "\n".join(f"{k} = {v}" for k, v in raw.get("nicknames", {}).items())
    out = ["<h1>Settings</h1><p class=sub>The clinic's settings the matcher reads (config/clinic.json). "
           "Nothing changes until you've checked what it does to the names shown.</p>"]
    if saved:
        out.append("<div class='box ok'>Saved. The openings were matched again with the new settings.</div>")
    if file_note:
        out.append(f"<div class='box warn'>{esc(file_note)}</div>")
    if notice:
        out.append(f"<div class=box>{esc(notice)}</div>")
    out.append(problems_box(problems))
    out.append(
        "<form method=post action='/settings/check'>"
        f"<div class=box><h2 style='margin-top:0'>Who gets the first call</h2><p class=hint>The order changes which "
        f"people are shown first, never who fits. Marc and Tanya decide it.</p>{order_radios}"
        f"<div class=field style='margin-top:10px'><label for=max_names>Names shown per opening</label>"
        f"<select id=max_names name=max_names>{''.join(opt(n, d.get('max_names'), str(n)) for n in (1, 2, 3))}"
        f"</select></div></div>"
        "<div class=box><h2 style='margin-top:0'>When a note doesn't say</h2><div class=grid>"
        f"<div class=field><label for=length_min>Length (min)</label><select id=length_min name=length_min>"
        f"{''.join(opt(n, d.get('length_min'), str(n)) for n in (30, 45, 60, 90))}</select></div>"
        + field("notice_hours", "Notice (hours)", d.get("notice_hours"), step="0.5")
        + field("stale_after_days", "Out of date after (days)", d.get("stale_after_days"),
                hint="No contact for longer than this: off the list.")
        + field("regular_min_visits", "Regular after (visits)", d.get("regular_min_visits", 3),
                hint="Visits with one therapist, for 'regulars first'.")
        + "</div></div>"
        "<div class=box><h2 style='margin-top:0'>Not pestering clients</h2><p class=hint>How many offers one person "
        "can get in 7 days before they rest, so others are called first. 0 = no limit. Marc decides.</p><div class=grid>"
        + field("max_offers_per_week", "Offers per person per week", d.get("max_offers_per_week", 0))
        + "</div></div>"
        "<div class=box><h2 style='margin-top:0'>What the time words mean</h2><div class=grid>"
        + field("mornings_before", "'Mornings' start before", tw.get("mornings_before"), kind="time", step="60")
        + field("afternoons_from", "'Afternoons' start from", tw.get("afternoons_from"), kind="time", step="60")
        + field("evenings_from", "'Evenings' start from", tw.get("evenings_from"), kind="time", step="60")
        + field("lunch_from", "'Lunch' from", tw.get("lunch_from"), kind="time", step="60")
        + field("lunch_until", "'Lunch' until", tw.get("lunch_until"), kind="time", step="60")
        + field("quick_notice_hours", "'Can come quick' (hours)", tw.get("quick_notice_hours"), step="0.25")
        + "</div></div>"
        "<div class=box><h2 style='margin-top:0'>Therapists</h2><p class=hint>Short forms are how the book names "
        "them (\"J only\", \"Jos\"). A short form can belong to one therapist only. Removing a therapist means "
        "their openings get nobody, and anyone who asked for them by name is held for review.</p>"
        "<table><tr><th>Name</th><th>Short forms</th><th>Female</th>"
        f"<th>Prenatal-trained</th><th>Other tags</th><th>Their say</th><th>Remove</th></tr>{rows}</table>"
        f"<p class=hint>Tags are what the <a href='/rules'>health routing rules</a> send people by.</p></div>"
        "<div class=box><h2 style='margin-top:0'>Nicknames</h2><p class=hint>For matching waitlist names to the "
        "booking export (\"Bob\" booked as \"Robert\"). One per line: short = full.</p>"
        f"<textarea name=nicknames rows=8>{esc(nicknames)}</textarea></div>"
        "<div class=actions><button class=primary type=submit>Check changes</button>"
        "<a class='button plain' href='/settings'>Start again</a></div></form>")
    state = ("<b>Paused.</b> Nothing is uploaded and no review decision is saved. Use the notebook."
             if paused else "<b>On.</b>")
    out.append(f"<h2>Owner's switch</h2><form class=box method=post action='/settings/pause'>{state} "
               f"<p class=hint>Marc's off switch. It stops uploads and review decisions; nothing is sent anywhere "
               f"either way.</p><label class=who>Your name <input name=checked_by required maxlength=40></label> "
               + (f"<button class=primary name=action value=resume>Switch back on</button>" if paused else
                  f"<button class=plain name=action value=pause>Pause the platform</button>") + "</form>")
    if versions:
        vrows = "".join(
            f"<tr><td>{_short(v['saved_at'])}</td><td>{'<br>'.join(esc(c) for c in v['changes']) or 'first version'}"
            f"</td><td><form method=post action='/settings/restore'><input type=hidden name=id value={v['id']}>"
            f"<button class=plain type=submit>Put this version back</button></form></td></tr>" for v in versions)
        out.append(f"<h2>Saved versions</h2><table><tr><th>Saved</th><th>What changed</th><th></th></tr>{vrows}</table>")
    return layout("Settings", "".join(out), "/settings", held)


def settings_preview_page(token, change_list, name_changes, people_before, people_after, note=None, approval=False,
                          back="/settings", held=None):
    """What the new settings change: the settings themselves, and the names shown on the last run's openings."""
    changes_html = "".join(f"<li>{esc(c)}</li>" for c in change_list)
    if name_changes:
        rows = "".join(f"<tr><td>{esc(c['opening'])}</td><td>{esc(', '.join(c['before']) or 'nobody')}</td>"
                       f"<td>{esc(', '.join(c['after']) or 'nobody')}</td></tr>" for c in name_changes)
        names = (f"<p>{count(len(name_changes), 'opening')} would show different names:</p><table><tr><th>Opening"
                 f"</th><th>Now</th><th>With the new settings</th></tr>{rows}</table>")
    else:
        names = "<p>The names shown on the last run's openings stay the same.</p>"
    people = ""
    if people_before != people_after:
        people = (f"<p>Waitlist: {people_before['active']} active, {people_before['stale']} out of date, "
                  f"{people_before['review']} held → {people_after['active']} active, {people_after['stale']} out of "
                  f"date, {people_after['review']} held.</p>")
    body = (f"<h1>Check before saving</h1><p class=sub>Nothing has been saved yet.</p>"
            f"<div class=box><b>Settings that change</b><ul class=plain>{changes_html}</ul></div>"
            f"<div class=box>{names}{people}</div>"
            + (f"<div class='box warn'>{esc(note)}</div>" if note else "")
            + f"<form method=post action='/settings/save' class=box><input type=hidden name=token value='{esc(token)}'>"
            f"<label class=who>Your name <input name=checked_by required maxlength=40 autocomplete=name></label>"
            + ("<p><label class=tick><input type=checkbox name=approved value=yes required> Marc has approved this "
               "change to the health routing rules</label></p>" if approval else "")
            + f"<div class=actions><button class=primary type=submit>Save</button>"
            f"<a class='button plain' href='{esc(back)}'>Cancel</a></div></form>")
    return layout("Check before saving", body, "/settings", held)


def compare_page(header, columns, everyone, held=None):
    """One opening under each order: the 3 shown first, and why. `columns`: [(order, words, [(name, basis)])]."""
    cols = "".join(f"<div class=box><b>{esc(order)}</b><p class=hint>{esc(words)}</p><ol>"
                   + "".join(f"<li><b>{esc(name)}</b> <span class=hint>({esc(basis)})</span></li>" for name, basis in picks)
                   + "</ol></div>" for order, words, picks in columns)
    fits = ", ".join(esc(n) for n in everyone)
    body = (f"<h1>Compare orders</h1><p class=sub>{esc(header)}</p>"
            f"<div class=box><b>{people_count(len(everyone))} fit this opening</b> in every order: {fits}. "
            f"The order only decides who is shown first.</div><div class=columns>{cols}</div>"
            f"<p><a href='/'>Back to the openings</a> · <a href='/settings'>Change the order</a></p>")
    return layout("Compare orders", body, "/", held)


# ---------- the cancellation inbox ----------

def short_client(name):
    """'Gabriel Morin' -> 'G. Morin': enough to find the booking, no more on a screen a client might see."""
    parts = (name or "").split()
    return f"{parts[0][0]}. {' '.join(parts[1:])}" if len(parts) > 1 else (name or "")


def inbox_rows_table(rows):
    if not rows:
        return "<p class=hint>None.</p>"
    body = ""
    for r in rows:
        slot = f"{_day(r['date'])} {esc(r['start'])} · {esc(r['therapist'])} · {r['length_min']} min"
        if r["in_run"]:
            slot = f"<a href='/#o-{esc(r['appointment_id'])}'>{slot}</a>"
        heard = f"{esc(r['cancelled_at'][5:])} · {esc(r['heard_via'] or '')}" if r["cancelled_at"] else ""
        notice = f"{r['notice']:g} h" if r["notice"] is not None else ""
        names = esc(", ".join(r["names"])) if r["names"] else ("—" if r["late"] else "")
        body += (f"<tr><td>{slot}<br><span class=hint>{esc(r['opening_id'] or r['appointment_id'])}</span></td>"
                 f"<td>{heard}</td><td>{notice}</td><td>{esc(r['status'])}</td><td>{names}</td></tr>")
    return (f"<table><tr><th>Slot</th><th>Cancelled · how heard</th><th>Notice left</th><th>Status</th><th>Names</th>"
            f"</tr>{body}</table>")


def inbox_page(day, day_bookings, upcoming, earlier, message=None, desk_name=None, held=None):
    """Every cancellation, however it was heard, one row per appointment (plan §9.4), and the day's bookings to
    enter a new one from."""
    out = ["<h1>Cancellation inbox</h1><p class=sub>Every cancellation, however it came in: voicemail, phone, a text "
           "reply, the morning calls, online. One row per appointment, soonest first.</p>"]
    if message:
        out.append(f"<div class='box ok'>{esc(message)}</div>")
    if not desk_name:
        out.append("<div class='box warn'>Say who's at the desk on the <a href='/'>Openings</a> page to enter "
                   "cancellations.</div>")
    rows = "".join(
        f"<tr><td>{esc(b['start'])}</td><td>{esc(b['therapist'])}</td><td>{b['length_min']} min</td>"
        f"<td>{esc(short_client(b['client_name']))}</td><td><a class='button plain' "
        f"href='/inbox/cancel?appointment={esc(b['appointment_id'])}'>Cancelled</a></td></tr>" for b in day_bookings)
    bookings = (f"<table><tr><th>Start</th><th>Therapist</th><th>Length</th><th>Client</th><th></th></tr>{rows}</table>"
                if day_bookings else f"<p class=hint>No bookings on {day:%a %b %d} in the uploaded files.</p>")
    out.append(f"<div class=box><h2 style='margin-top:0'>Enter a cancellation</h2>"
               f"<form method=get action='/inbox' class=inline>Bookings on <input type=date name=day "
               f"value='{day.isoformat()}'> <button class=plain>Show</button></form>{bookings}"
               f"<p class=hint>Not in the list (booked after the last upload)? <a href='/inbox/cancel?manual=1'>Enter it "
               f"with its Kneadly appointment number</a>.</p></div>")
    out.append("<form method=post action='/inbox/rematch' class='box inline'><span>Openings entered here count their "
               "notice from now, so the names change as the start gets closer.</span>"
               "<button class=plain>Match again now</button></form>")
    out.append(f"<h2>Coming up</h2>{inbox_rows_table(upcoming)}")
    out.append(f"<details><summary><b>Earlier ({len(earlier)})</b></summary>{inbox_rows_table(earlier)}</details>")
    return layout("Inbox", "".join(out), "/inbox", held)


def cancel_page(slot, therapists, channels, default_when, error=None, values=None, held=None):
    """Enter one cancellation: the booking (or a manual slot), how it came in, and when. No reason is asked for."""
    v = values or {}
    err = f"<div class='box err'><b>Not saved.</b> {esc(error)}</div>" if error else ""

    def opt(value, current):
        return f"<option{' selected' if str(value) == str(current) else ''}>{esc(value)}</option>"
    if slot:
        what = (f"<p><b>{_day(slot['date'])} {esc(slot['start'])} · {esc(slot['therapist'])} · {slot['length_min']} "
                f"min</b> · {esc(short_client(slot.get('client_name')))} · {esc(slot['appointment_id'])}</p>"
                f"<input type=hidden name=appointment value='{esc(slot['appointment_id'])}'>")
    else:
        what = (f"<input type=hidden name=manual value=yes><div class=grid>"
                f"<div class=field><label for=appointment>Kneadly appointment number</label><input id=appointment "
                f"name=appointment required maxlength=20 value='{esc(v.get('appointment', ''))}'></div>"
                f"<div class=field><label for=date>Date</label><input type=date id=date name=date required "
                f"value='{esc(v.get('date', ''))}'></div>"
                f"<div class=field><label for=start>Start</label><input type=time id=start name=start required "
                f"value='{esc(v.get('start', ''))}'></div>"
                f"<div class=field><label for=therapist>Therapist</label><select id=therapist name=therapist>"
                + "".join(opt(t, v.get("therapist")) for t in therapists) + "</select></div>"
                f"<div class=field><label for=length>Length</label><select id=length name=length>"
                + "".join(opt(n, v.get("length", 60)) for n in (30, 45, 60, 90)) + "</select></div></div>")
    body = (f"<h1>Enter a cancellation</h1><p class=sub>Under 24 hours before the start, it becomes an opening with "
            f"names straight away. Further ahead, it's only recorded: Kneadly's online page offers it.</p>{err}"
            f"<form class=box method=post action='/inbox/cancel'>{what}"
            f"<div class=field><label for=heard_via>How it came in</label><select id=heard_via name=heard_via>"
            + "".join(opt(c, v.get("heard_via")) for c in channels) + "</select></div>"
            f"<div class=field><label for=cancelled_at>When they cancelled</label><p class=hint>For a voicemail, the time "
            f"it was left (the phone shows it). This decides whether it's a late cancellation. No reason is asked for "
            f"or kept.</p><input type=datetime-local id=cancelled_at name=cancelled_at required "
            f"value='{esc(v.get('cancelled_at', default_when))}'></div>"
            f"<div class=actions><button class=primary>Save</button><a class='button plain' href='/inbox'>Back</a></div>"
            f"</form>")
    return layout("Enter a cancellation", body, "/inbox", held)


# ---------- the morning call list ----------

def call_row(b, first_day, desk_name, after=""):
    """One booking on the call list, with its taps. `after`: HTML for what a cancellation led to."""
    aid = b["appointment_id"]
    voicemails = [c for c in b["calls"] if c["outcome"] == "voicemail"]
    done = {"confirmed": "confirmed", "cancelled": "cancelled"}.get(b["state"])
    last = b["calls"][-1] if b["calls"] else None
    state = (f"<span class=outcome>{done} {esc(last['at'][11:])}</span>" if done else
             "<span class=outcome>voicemail " + " ".join(esc(c["at"][11:]) for c in voicemails)
             + " " + "●" * len(voicemails) + "</span>" if voicemails else "")

    def tap(do, label, cls="plain"):
        return (f"<form method=post action='/calls' class=inline><input type=hidden name=appointment value='{esc(aid)}'>"
                f"<input type=hidden name=from value='{first_day.isoformat()}'>"
                f"<button class={cls} name=do value='{do}'>{label}</button></form>")
    if not desk_name:
        taps = ""
    elif b["state"] in ("to call", "voicemail"):
        taps = (tap("confirmed", "Confirmed", "primary") + tap("voicemail", "Voicemail") + tap("cancelled", "Cancelled")
                + (tap("undo", "Undo") if b["state"] == "voicemail" else ""))
    elif b["state"] == "confirmed":
        taps = tap("undo", "Undo")
    else:
        taps = ""
    head = (f"<div class=call><span class=op-when>{_day(b['date'])[:3]} {esc(b['start'])}</span>"
            f"<span>{esc(b['therapist'])} · {b['length_min']} min</span><b>{esc(short_client(b['client_name']))}</b>"
            f"<span class=hint>{esc(aid)}</span>{state}<span class=act>{taps}</span></div>")
    return f"<div id='c-{esc(aid)}' class=call-row>{head}{after}</div>"


def cancelled_after(info):
    """Under a booking cancelled on the call list: its opening's names (the next calls), or why there's none."""
    if info is None:
        return ""
    if info.get("note"):
        return f"<p class=desk-note>{esc(info['note'])}</p>"
    names = "".join(f"<li><span class=rank>{n['rank']}</span><b>{esc(n['person'])}</b> {esc(phone_display(n['phone']))}"
                    f" <span class=hint>line {n['line']} · {esc(n['can_take'])}</span></li>" for n in info["names"])
    names = f"<ol class=plain-names>{names}</ol>" if names else "<p class=desk-note>Nobody on the list fits.</p>"
    return (f"<div class=after><b>{esc(info['opening_id'])}</b> · {esc(info['notice'])} h notice left · "
            f"<a href='/#o-{esc(info['appointment_id'])}'>hold and offer on the Openings page</a>{names}</div>")


def calls_page(first_day, is_today, rows, after, message=None, desk_name=None, held=None):
    """Today's (still to come) and tomorrow's bookings not confirmed in the last upload (plan §9.4): one tap per
    call. It replaces the sticky note and the dots."""
    days = f"{first_day:%a %b %d} and the day after"
    sections = (("To call", [b for b in rows if b["state"] == "to call"]),
                ("Try again (voicemail left)", [b for b in rows if b["state"] == "voicemail"]),
                ("Cancelled", [b for b in rows if b["state"] == "cancelled"]))
    out = [f"<h1>Morning calls</h1><p class=sub>{'Today (still to come)' if is_today else first_day.strftime('%a %b %d')}"
           f" and {'tomorrow' if is_today else 'the day after'}: the bookings that weren't confirmed in the last "
           f"upload. One tap per call; still mark it in Kneadly, as today.</p>"]
    if message:
        out.append(f"<div class='box ok'>{esc(message)}</div>")
    if not desk_name:
        out.append("<div class='box warn'>Say who's at the desk on the <a href='/'>Openings</a> page to tap calls.</div>")
    out.append(f"<form method=get action='/calls' class='box inline'>Calls for <input type=date name=from "
               f"value='{first_day.isoformat()}'> and the day after <button class=plain>Show</button>"
               f"<span class=hint>Phone numbers: in Kneadly (the booking export has none).</span></form>")
    if not rows:
        out.append(f"<div class=box>No unconfirmed bookings for {days} in the uploaded files.</div>")
    for title, items in sections:
        if items:
            out.append(f"<h2>{esc(title)} ({len(items)})</h2>"
                       + "".join(call_row(b, first_day, desk_name, cancelled_after(after.get(b["appointment_id"])))
                                 for b in items))
    confirmed = [b for b in rows if b["state"] == "confirmed"]
    if confirmed:
        out.append(f"<details><summary><b>Confirmed ({len(confirmed)})</b></summary>"
                   + "".join(call_row(b, first_day, desk_name) for b in confirmed) + "</details>")
    return layout("Morning calls", "".join(out), "/calls", held)


# ---------- health routing rules ----------

def rules_page(raw, routing, therapists, problems=(), saved=False, held=None):
    """The clinic's health routing rules (plan §7.2): who each rule sends people to, and the words in the book that
    set it. A change is checked, shows the names it changes, and needs Marc's approval before it's saved.
    `routing`: rule name -> {tag, words, chip}; `therapists`: name -> settings, as in config/clinic.json."""
    def ticks(prefix, tag):
        return "".join(
            f"<label class=tick><input type=checkbox name={prefix}_therapists value='{esc(n)}'"
            f"{' checked' if tag and tag in _tags_of(t) else ''}> {esc(n.split()[0])}</label>" for n, t in therapists.items())
    cards = ""
    for i, (name, r) in enumerate(routing.items()):
        cards += (f"<div class=box><input type=hidden name=r{i}_name value='{esc(name)}'>"
                  f"<input type=hidden name=r{i}_tag value='{esc(r['tag'])}'><h2 style='margin-top:0'>{esc(name)}</h2>"
                  f"<p class=hint>People whose notes use one of these words only see therapists tagged "
                  f"<b>{esc(r['tag'])}</b>, even if they said \"any\". The reason is never kept, only the tag.</p>"
                  f"<div class=field><label>Therapists with the tag</label>{ticks(f'r{i}', r['tag'])}</div>"
                  f"<div class=field><label for=r{i}_words>Words in the book that set it</label><p class=hint>Comma "
                  f"between words. A word ending in * matches the start of a word: pregnan* matches pregnant.</p>"
                  f"<input id=r{i}_words name=r{i}_words class=wide value='{esc(', '.join(r['words']))}'></div>"
                  f"<div class=field><label for=r{i}_chip>Label on the fill-in card</label><input id=r{i}_chip "
                  f"name=r{i}_chip class=wide value='{esc(r['chip'])}'></div>"
                  f"<label class=tick><input type=checkbox name=r{i}_remove value=yes> Remove this rule</label></div>")
    new = ("<div class=box><h2 style='margin-top:0'>New rule</h2><p class=hint>A rule of the same kind: \"people with "
           "these words only see therapists with this tag\". A different kind of rule needs a developer.</p><div class=grid>"
           "<div class=field><label for=new_name>Name</label><input id=new_name name=new_name placeholder='Post-op'></div>"
           "<div class=field><label for=new_tag>Tag</label><input id=new_tag name=new_tag placeholder='post-op-trained'></div>"
           "<div class=field><label for=new_chip>Label on the card</label><input id=new_chip name=new_chip "
           "placeholder='Post-op-trained only'></div></div><div class=field><label for=new_words>Words in the book that "
           "set it</label><input id=new_words name=new_words class=wide placeholder='post-op, post op, surger*'></div>"
           f"<div class=field><label>Therapists with the tag</label>{ticks('new', None)}</div></div>")
    words = ", ".join(raw.get("health_words", [])) or "none yet"
    private = ("<div class=box><h2 style='margin-top:0'>More private words</h2><p class=hint>Words that mark a health "
               "detail in a note, besides the built-in list: the piece is dropped, never kept, and never quoted. Add a "
               "word the review queue keeps showing as unreadable when it's a condition. Removing one needs a developer."
               f"</p><p>Added so far: {esc(words)}</p><input name=health_add class=wide placeholder='shingles, vertigo'></div>")
    out = ["<h1>Health routing rules</h1><p class=sub>Clinic decisions by Marc. Nothing changes until you've checked "
           "what it does to the names shown, and Marc has approved it.</p>"]
    if saved:
        out.append("<div class='box ok'>Saved. The openings were matched again.</div>")
    out.append(problems_box(problems))
    out.append(f"<form method=post action='/rules/check'>{cards}{new}{private}"
               "<div class=actions><button class=primary type=submit>Check changes</button>"
               "<a class='button plain' href='/rules'>Start again</a></div></form>"
               "<p class=hint>New words apply to the book's lines on its next upload; tag changes apply straight away. "
               "Earlier versions can be put back on the <a href='/settings'>Settings</a> screen.</p>")
    return layout("Health routing rules", "".join(out), "/rules", held)


def _tags_of(t):
    tags = set(t.get("tags", []))
    if t.get("female"):
        tags.add("female")
    if t.get("prenatal_trained"):
        tags.add("prenatal-trained")
    return tags


# ---------- the waitlist board ----------

TAKE_OFF_REASONS = ("booked", "moved", "not interested", "going to another clinic")


def card_chips(rec, everyone, first_name):
    """What a person can take, as chips: the same facts as the card, short. No routing reason: a pregnant client
    shows as "Amira or Kelsey"."""
    allowed, excluded = set(rec["therapists_allowed"]), set(rec["excluded"])
    if allowed == set(everyone):
        who = "any therapist"
    elif excluded and allowed == set(everyone) - excluded and not rec["female_only"]:
        who = "anyone but " + " or ".join(sorted(first_name(n) for n in excluded))
    else:
        who = " or ".join(sorted(first_name(n) for n in allowed)) or "no therapist fits"
    chips = [who, "/".join(str(n) for n in rec["lengths"]) + " min"]
    if rec["days"]:
        chips.append("/".join(d for d in DAYS if d in rec["days"]))
    elif rec["days_excluded"]:
        chips.append("not " + "/".join(rec["days_excluded"]))
    else:
        chips.append("any day")
    times = [label + " " + rec[key] for key, label in (("earliest_start", "from"), ("start_before", "starts before"),
                                                        ("latest_end", "done by")) if rec[key]]
    chips.append(", ".join(times) or "any time")
    chips.append("the day before" if rec["day_before"] else f"{rec['notice_hours']:g} h notice")
    if rec["available_from"]:
        chips.append(f"from {_day(rec['available_from'])}")
    if rec["available_until"]:
        chips.append(f"until {_day(rec['available_until'])}")
    chips.append(rec["contact"] or "call")
    if rec["new_client"]:
        chips.append("new client, phone only")
    return chips


def board_card(rec, everyone, first_name, desk_name, flags=()):
    first = rec["lines"][0]
    status = {"stale": "<span class='chip done'>out of date</span>",
              "review": "<span class='chip live'>held for review</span>"}.get(rec["status"], "")
    chips = "".join(f"<span class='chip held'>{esc(c)}</span> " for c in card_chips(rec, everyone, first_name))
    reasons = (f"<ul class=plain>" + "".join(f"<li>{esc(r)}</li>" for r in rec["reasons"]) + "</ul>"
               if rec["status"] != "active" else "")
    lines = ("line " if len(rec["lines"]) == 1 else "lines ") + ", ".join(str(n) for n in rec["lines"])
    asked = f"asked {_day(rec['first_asked'])} · " if rec["first_asked"] else ""
    contact = f"last contact {_day(rec['last_contact'])} · " if rec["last_contact"] else ""
    if desk_name:
        reasons_opts = "".join(f"<option>{esc(r)}</option>" for r in TAKE_OFF_REASONS)
        actions = (f"<div class=actions><a class='button plain' href='/board/card?line={first}'>Edit card</a>"
                   f"<form method=post action='/board' class=inline><input type=hidden name=do value=still>"
                   f"<input type=hidden name=line value={first}><button class=plain>Still interested ✓</button></form>"
                   f"<form method=post action='/board' class=inline><input type=hidden name=do value=takeoff>"
                   f"<input type=hidden name=line value={first}><select name=reason>{reasons_opts}</select>"
                   f"<button class=plain>Take off</button></form>"
                   f"<a href='/board/history?line={first}'>History</a></div>")
    else:
        actions = f"<p class=desk-note>Say who's at the desk on the Openings page to change cards.</p>"
    return (f"<section id='p-{first}' class='opening{' nobody' if rec['status'] != 'active' else ''}'>"
            f"<div class=op-head><span class=op-when>{esc(rec['name'])}</span><span class=phone>"
            f"{esc(phone_display(rec['phone']))}</span><span class=op-meta>{asked}{contact}{lines}</span>{status}</div>"
            f"<p style='margin:8px 0 0'>{chips}" + "".join(f"<span class=flag>{esc(f)}</span>" for f in flags)
            + f"</p>{reasons}{actions}</section>")


def board_page(people, counts, show, query, everyone, first_name, board_only, message=None, desk_name=None,
               flags=None, held=None):
    """The waitlist as cards (plan §6): one per person, kept up to date on screen instead of in the book."""
    out = ["<h1>Waitlist</h1><p class=sub>One card per person: the book's lines and the desk's changes, merged. "
           "No notes box: only what decides who to call.</p>"]
    if message:
        out.append(f"<div class='box ok'>{esc(message)}</div>")
    tabs = " · ".join((f"<b>{label} ({counts[key]})</b>" if key == show else
                       f"<a href='/board?show={key}'>{label} ({counts[key]})</a>")
                      for key, label in (("active", "active"), ("review", "held"), ("stale", "out of date"),
                                         ("all", "all")))
    out.append(f"<form method=get action='/board' class='box inline'><input type=hidden name=show value='{esc(show)}'>"
               f"<span>Show: {tabs}</span><input name=q value='{esc(query)}' placeholder='name or phone'> "
               f"<button class=plain>Find</button>"
               + ("<a class='button primary' href='/board/add'>+ Add someone</a>" if desk_name else "") + "</form>")
    out += [board_card(rec, everyone, first_name, desk_name, (flags or {}).get(rec["lines"][0], ())) for rec in people] \
        or ["<div class=box>Nobody here.</div>"]
    mode = (f"<b>Board only</b> since {esc(board_only)}: the book is retired, and waitlist uploads are refused."
            if board_only else "<b>Book and board.</b> New lines in the book are still uploaded and merged; a newer "
                               "book line overrides a card.")
    switch = ("<form method=post action='/board' class=inline><input type=hidden name=do value=mode>"
              + ("<input type=hidden name=on value=no><button class=plain>Go back to book and board</button>" if board_only
                 else "<label class=tick><input type=checkbox name=agreed value=yes required> Agreed with Tanya, Bethany "
                      "and the therapists, from today</label><input type=hidden name=on value=yes>"
                      "<button class=plain>Retire the book: board only</button>") + "</form>")
    out.append(f"<h2>The book and the board</h2><div class=box>{mode}<p class=hint>Retire the book for everyone at once, "
               f"on an agreed date, so there are never two lists (plan §6.3).</p>{switch if desk_name else ''}</div>")
    return layout("Waitlist", "".join(out), "/board", held)


def history_page(rec, book_lines, decisions, held=None):
    """A card's history: the book's lines (date only, never the note) and every change made on screen."""
    lines = "".join(f"<tr><td>line {l['line']}</td><td>{esc(l['added_raw'])}</td><td>from the book</td><td></td></tr>"
                    for l in book_lines)
    rows = "".join(
        f"<tr><td>{_short(d['made_at'])}</td><td>{describe(d)}</td><td>"
        + (f"undone {_short(d['undone_at'])}" if d["undone_at"] else
           f"<form method=post action='/review/undo'><input type=hidden name=id value={d['id']}>"
           f"<button class=plain>Undo</button></form>") + "</td></tr>" for d in decisions)
    body = (f"<h1>History: {esc(rec['name'])}</h1><p class=sub>The book's lines (the notes themselves aren't kept) and "
            f"every change made on screen, newest first.</p><h2>Changes on screen</h2>"
            + (f"<table>{rows}</table>" if rows else "<p class=hint>None.</p>")
            + f"<h2>Lines in the book</h2><table>{lines or '<tr><td>None.</td></tr>'}</table>"
            f"<p><a href='/board#p-{rec['lines'][0]}'>Back to the waitlist</a></p>")
    return layout("History", body, "/board", held)


# ---------- the feedback report (plan §11) ----------

def report_page(r, held=None):
    """Marc's numbers: what happened to the openings, by channel, how fast, and what people said."""
    def table(counts):
        if not counts:
            return "<p>None.</p>"
        return "<table>" + "".join(f"<tr><td>{esc(k)}</td><td>{v}</td></tr>"
                                   for k, v in sorted(counts.items(), key=lambda x: -x[1])) + "</table>"
    channel = "".join(f"<tr><td>{esc(k)}</td><td>{v['openings']}</td><td>{v['refilled']}</td></tr>"
                      for k, v in sorted(r["by_channel"].items(), key=lambda x: -x[1]["openings"]))
    mistakes = "".join(f"<tr><td>{esc(m['opening'])}</td><td>{esc(m['person'])} (line {m['line']})</td>"
                       f"<td>{esc(m['at'] or '')}</td></tr>" for m in r["mistakes"])
    speed = (f"{r['median_minutes']} minutes (median of {r['refilled']})" if r["median_minutes"] is not None
             else "no refills from the waitlist yet")
    body = (
        f"<h1>Report</h1><form method=get action='/report' class='box inline'>Openings from <input type=date name=since "
        f"value='{r['since'].isoformat()}'> to <input type=date name=until value='{r['until'].isoformat()}'> "
        f"<button class=plain>Show</button><a href='/report?since=2000-01-01&until=2100-01-01'>all</a>"
        f"<a href='/files/outcomes.csv'>outcomes.csv</a><a href='/files/rebookings.csv'>rebookings.csv</a></form>"
        f"<div class=box><ul class=facts><li><b>Late openings:</b> {r['openings']}</li><li><b>No-shows</b> (never "
        f"offered): {r['no_shows']}</li><li><b>Refilled from the waitlist:</b> {r['refilled']}</li>"
        f"<li><b>Time from hearing to filled:</b> {speed}</li><li><b>Offers made:</b> {r['offers']}</li></ul></div>"
        f"<h2>What happened to the openings</h2>{table(r['outcome'])}"
        f"<h2>By how the cancellation was heard</h2>"
        + (f"<table><tr><th>Channel</th><th>Openings</th><th>Refilled from the waitlist</th></tr>{channel}</table>"
           if channel else "<p>None.</p>")
        + f"<h2>Answers to offers</h2>{table(r['offer_outcomes'])}"
        f"<h2>Why people said no</h2><p class=hint>For the monthly check: a reason that keeps coming back may mean a "
        f"default is wrong (Julie with Marc). The opening's own outcome never picks names for it.</p>"
        f"{table(r['reasons'])}"
        f"<h2>Possible wrong offers</h2><p class=hint>\"They'd said they can't\": each one becomes a test case.</p>"
        + (f"<table><tr><th>Opening</th><th>Offered to</th><th>When</th></tr>{mistakes}</table>" if mistakes
           else "<p>None.</p>")
        + f"<h2>How the booking export says slots were refilled</h2><p class=hint>From \"rebooked into\" and how the "
        f"new booking was made: shows whether the waitlist is what fills slots.</p>{table(r['export'])}")
    return layout("Report", body, "/report", held)
