"""The platform's screens (platform-plan.md §4.1, §7.4, §8): upload with a check before anything is saved, the
opening queue, the review queue for held people, downloads and the sync log. Start it with: python serve.py

Only Python's standard library, like the rest of the project, so nothing has to be installed. It answers only
requests made on this computer (localhost). Uploaded files stay in memory until they're saved or cancelled:
they're written to a temporary folder only while a sync reads them, then deleted. The check runs the real sync
on a temporary copy of the database, so it shows exactly what saving will do. Every desk decision on the review
screen is saved with who made it, can be undone, and the openings are matched again straight after.
"""
import csv
import io
import json
import re
import secrets
import shutil
import tempfile
import threading
import time as clock
from dataclasses import replace
from datetime import date, datetime, timedelta
from email.parser import BytesParser
from email.policy import HTTP
from pathlib import Path
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, quote, unquote

from kettle import feedback, store
from kettle.adapters.csv_in import InputError
from kettle.adapters.upload import history_gaps, people_from_db, sync
from kettle.config import DEFAULT_CONFIG, load_config
from kettle.core.match import match_opening, visits_with
from kettle.core.parse_notes import LineSpec
from webapp import pages
from webapp import settings as settings_logic
from kettle.core.normalise import fold, normalise_phone
from webapp.cards import EMPTY_CARD, CardError, card_changes, card_spec, prefill_from_form, prefill_from_record

PAUSED_BANNER = ("<div class=paused-banner>The platform is paused (the owner's switch in Settings). Use the "
                 "notebook: uploads and review decisions are off.</div>")

KINDS = ("waitlist", "appointments", "openings")
DOWNLOADS = {"matches.txt": "text/plain", "matches.csv": "text/csv", "preprocess-report.txt": "text/plain",
             "line-verdicts.csv": "text/csv", "sync-log.txt": "text/plain"}
LOCAL_HOSTS = {"localhost", "127.0.0.1", "[::1]"}
MAX_UPLOAD = 20 * 1024 * 1024
MAX_FORM = 64 * 1024
PENDING_SECONDS = 30 * 60


class Response:
    def __init__(self, body="", status="200 OK", content_type="text/html; charset=utf-8", headers=()):
        self.body = body.encode("utf-8") if isinstance(body, str) else body
        self.status = status
        self.headers = [("Content-Type", content_type), ("Cache-Control", "no-store"), *headers]


def redirect(location):
    return Response("", "303 See Other", headers=[("Location", location)])


def parse_multipart(body, content_type):
    """multipart/form-data -> ({field: text}, {field: (filename, bytes)}); empty file inputs are left out."""
    message = BytesParser(policy=HTTP).parsebytes(b"Content-Type: " + content_type.encode("latin-1") + b"\r\n\r\n" + body)
    fields, files = {}, {}
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        payload = part.get_payload(decode=True) or b""
        filename = part.get_filename()
        if filename is None:
            fields[name] = payload.decode("utf-8", errors="replace")
        elif filename and payload:
            files[name] = (filename, payload)
    return fields, files


def desk_name(environ):
    """Who's at the desk, as this browser was told (a cookie), or "" if nobody said."""
    cookie = SimpleCookie(environ.get("HTTP_COOKIE", ""))
    return unquote(cookie["kettle_desk"].value).strip()[:40] if "kettle_desk" in cookie else ""


def _host(value):
    value = (value or "").strip().lower()
    if value.startswith("["):
        return value.split("]")[0] + "]"
    return value.split(":")[0]


class Platform:
    def __init__(self, db_path="data/kettle.db", out_dir="out", config_path=DEFAULT_CONFIG, today=date.today,
                 now=datetime.now):
        self.db_path = Path(db_path)
        self.out_dir = Path(out_dir)
        self.config_path = config_path
        self.today = today
        self.now = now  # the clock for offers, decisions and saves (tests set it)
        self.pending = {}  # token -> {"files": {kind: (filename, bytes)}, "run_date": date, "at": seconds}
        self.pending_settings = {}  # token -> {"raw": settings, "changes": [words], "at": seconds}
        self.lock = threading.Lock()  # one change at a time (upload, decision, undo, settings)

    # ---------- WSGI ----------

    def __call__(self, environ, start_response):
        head = environ["REQUEST_METHOD"] == "HEAD"
        response = self.handle({**environ, "REQUEST_METHOD": "GET"} if head else environ)
        start_response(response.status, response.headers + [("Content-Length", str(len(response.body)))])
        return [b"" if head else response.body]

    def handle(self, environ):
        # only this computer: a page on another site can't reach in by naming another host or posting from elsewhere
        if _host(environ.get("HTTP_HOST")) not in LOCAL_HOSTS:
            return self.page(pages.message_page, "Not allowed", "This screen only answers on this computer.",
                             status="403 Forbidden")
        method, path = environ["REQUEST_METHOD"], environ.get("PATH_INFO", "/")
        origin = environ.get("HTTP_ORIGIN")
        if method == "POST" and origin and _host(origin.split("//")[-1]) not in LOCAL_HOSTS:
            return self.page(pages.message_page, "Not allowed", "Forms can only be sent from this screen.",
                             status="403 Forbidden")
        with self.lock:
            self._drop_old_uploads()
        query = parse_qs(environ.get("QUERY_STRING", ""))
        if method == "GET":
            if path == "/":
                return self.openings(query.get("saved", [None])[0], desk_name(environ))
            if path == "/upload":
                return self.page(pages.upload_page, self.today(), self._db_is_empty())
            if path == "/review":
                return self.review(done=bool(query.get("done")))
            if path == "/review/fill":
                return self.fill(query.get("line", [""])[0])
            if path == "/settings":
                return self.settings_screen(saved=bool(query.get("saved")))
            if path == "/rules":
                return self.rules_screen(saved=bool(query.get("saved")))
            if path == "/compare":
                return self.compare(query.get("opening", [""])[0])
            if path == "/board":
                return self.board_screen(query.get("show", ["active"])[0], query.get("q", [""])[0], desk_name(environ))
            if path == "/board/card":
                return self.board_card(query.get("line", [""])[0])
            if path == "/board/add":
                return self.page(pages.fill_page, None, self._therapists(load_config(self.config_path)), dict(EMPTY_CARD),
                                 self._rules(load_config(self.config_path)), mode="add")
            if path == "/board/history":
                return self.board_history(query.get("line", [""])[0])
            if path == "/calls":
                return self.calls(query.get("from", [""])[0], desk=desk_name(environ))
            if path == "/inbox":
                return self.inbox(query.get("day", [""])[0], desk=desk_name(environ))
            if path == "/inbox/cancel":
                return self.cancel_form(query.get("appointment", [""])[0], bool(query.get("manual")),
                                        desk=desk_name(environ))
            if path == "/report":
                return self.report_screen(query.get("since", [""])[0], query.get("until", [""])[0])
            if path == "/files/outcomes.csv":
                return self.outcomes_csv()
            if path == "/check":
                return self.daily_check()
            if path == "/log":
                return self.log()
            if path == "/files/rebookings.csv":
                return self.rebookings_csv()
            if path.startswith("/files/"):
                return self.download(path[len("/files/"):])
        if method == "POST" and path in ("/upload/check", "/upload/save", "/upload/cancel"):
            length = int(environ.get("CONTENT_LENGTH") or 0)
            if length > MAX_UPLOAD:
                return self.page(pages.upload_page, self.today(), self._db_is_empty(),
                                 "The files are too big for one upload (20 MB).", status="413 Payload Too Large")
            body = environ["wsgi.input"].read(length)
            with self.lock:
                if path == "/upload/check":
                    return self.check(body, environ.get("CONTENT_TYPE", ""))
                token = parse_qs(body.decode("utf-8", errors="replace")).get("token", [""])[0]
                return self.save(token) if path == "/upload/save" else self.cancel(token)
        forms = {"/review/decide": self.decide, "/review/undo": self.undo, "/settings/check": self.check_settings,
                 "/settings/save": self.save_settings, "/settings/restore": self.restore_settings,
                 "/settings/pause": self.pause, "/opening": self.opening_action, "/rules/check": self.check_rules,
                 "/inbox/cancel": self.record_cancellation, "/inbox/rematch": self.match_again,
                 "/calls": self.call_action, "/board": self.board_action}
        if method == "POST" and path == "/desk":
            form = parse_qs(environ["wsgi.input"].read(min(int(environ.get("CONTENT_LENGTH") or 0), MAX_FORM))
                            .decode("utf-8", errors="replace"))
            return self.set_desk(form.get("name", [""])[0])
        if method == "POST" and path in forms:
            length = int(environ.get("CONTENT_LENGTH") or 0)
            if length > MAX_FORM:
                return self.page(pages.message_page, "Too big", "That form is too big.", status="413 Payload Too Large")
            form = parse_qs(environ["wsgi.input"].read(length).decode("utf-8", errors="replace"), keep_blank_values=True)
            with self.lock:
                if path.startswith("/review/") and self.paused():
                    return self.review(error="The platform is paused, so decisions can't be saved. Use the notebook.",
                                       status="409 Conflict")
                if path in ("/opening", "/inbox/cancel", "/inbox/rematch", "/calls", "/board") and self.paused():
                    return self.page(pages.message_page, "Paused", "The platform is paused, so offers can't be "
                                     "recorded here. Use the notebook.", status="409 Conflict")
                form["_desk"] = [desk_name(environ)]
                return forms[path](form)
        return self.page(pages.message_page, "Not found", "There's no page here.", status="404 Not Found")

    def page(self, render, *args, status="200 OK", **kwargs):
        """A screen, with the number of people held for review in the menu, and a banner while paused."""
        held, paused = self._menu_state()
        html = render(*args, held=held, **kwargs)
        if paused:
            html = html.replace("<main>", PAUSED_BANNER + "<main>", 1)
        return Response(html, status)

    def _menu_state(self):
        if not self.db_path.exists():
            return 0, False
        con = store.connect(self.db_path)
        try:
            held = sum(json.loads(r[0])["status"] == "review" for r in con.execute("SELECT record FROM people"))
            return held, store.is_paused(con)
        finally:
            con.close()

    def held(self):
        return self._menu_state()[0]

    def paused(self):
        return self._menu_state()[1]

    # ---------- screens ----------

    def openings(self, saved, desk=""):
        if not self.db_path.exists():
            return self.page(pages.queue_page, None, [], None, str)
        config = load_config(self.config_path)
        con = store.connect(self.db_path)
        try:
            view = store.latest_run(con)
            if view:
                count, first, last = con.execute("SELECT COUNT(*), MIN(date), MAX(date) FROM bookings").fetchone()
                view["bookings"] = {"count": count, "first": pages._day(first) if first else "none",
                                    "last": pages._day(last) if last else "none"}
                view["desk"] = store.desk_state(con)
            gaps = history_gaps(store.visit_ranges(con), store.open_weekdays(con))
            todo = sum(len(x) for x in self._unfinished(con))
            rest = feedback.resting(con, view["people"] if view else [], config.max_offers_per_week, self.now())
        finally:
            con.close()
        names = {p["lines"][0]: p["name"] for p in (view["people"] if view else [])}
        resting = sorted(((names.get(first, "?"), r["until"]) for first, r in rest.items()), key=lambda x: x[1])
        return self.page(pages.queue_page, view, gaps, saved if saved and saved.isdigit() else None,
                         self._first_name(config), desk_name=desk, now=self.now(), todo=todo, resting=resting,
                         limit=config.max_offers_per_week)

    @staticmethod
    def _first_name(config):
        def first_name(full):
            t = config.therapist_by_name(full)
            return t.first_name if t else full
        return first_name

    # ---------- offers: hold, offer one at a time, answer, close (plan §10.1) ----------

    def set_desk(self, name):
        """Remembers who's at the desk in this browser (a cookie); an empty name forgets it."""
        name = " ".join(name.split())[:40]
        cookie = (f"kettle_desk={quote(name)}; Path=/; SameSite=Strict; HttpOnly" if name else
                  "kettle_desk=; Path=/; SameSite=Strict; HttpOnly; Max-Age=0")
        response = redirect("/")
        response.headers.append(("Set-Cookie", cookie))
        return response

    def opening_action(self, form):
        """Every step on an opening. Saved, then (where names change) the openings are matched again."""
        def get(k):
            return form.get(k, [""])[0].strip()
        aid, do, by = get("opening"), get("do"), get("_desk")
        view, _ = self._latest()
        opening = next((o for o in (view["openings"] if view else []) if o["appointment_id"] == aid), None)
        if opening is None:
            return self.page(pages.message_page, "Not found", "That opening isn't in the last run.",
                             status="404 Not Found")
        back = redirect(f"/#o-{quote(aid)}")

        def refuse(message, status="400 Bad Request"):
            return self.page(pages.message_page, "Not saved", message, status=status)
        if not by:
            return refuse("Say who's at the desk first (top of the openings page).")
        now = self.now()
        con = store.connect(self.db_path)
        try:
            status = store.status_of(con, aid)
            state = store.desk_state(con).get(aid, {"live": None})
            live = state["live"]
            shown = {r["line"]: r for r in view["rows"][aid] if r["rank"] > 0}
            note = None
            if do == "hold":
                if status != "new":
                    return back
                if not get("checked"):
                    return refuse("Check in Kneadly that the slot is still free and block the time there first.")
                with con:
                    store.place_hold(con, aid, by, now)
            elif do == "offer":
                line = int(get("line")) if get("line").isdigit() else None
                if status != "held":
                    return refuse("Place the hold in Kneadly before the first call.")
                if line not in shown or line in {x["line"] for x in state.get("offers", [])}:
                    return refuse("That person isn't one of the names for this opening any more. Reload the page.")
                person = next((p for p in view["people"] if line in p["lines"]), {})
                try:
                    with con:
                        store.start_offer(con, aid, line, shown[line]["person"], person.get("phone"), by, now)
                except store.LiveOfferError as e:
                    return refuse(str(e), "409 Conflict")
                if load_config(self.config_path).max_offers_per_week:  # this offer may put them at the weekly limit
                    note = f"offer to line {line} for {opening['opening_id']}"
            elif do == "answer" and get("answer") == "yes":
                if not live or str(live["id"]) != get("offer"):
                    return back
                return self._booking_card(opening, live, view)
            elif do == "answer" and get("answer") in ("no", "no answer", "no, keep me on"):
                if not live or str(live["id"]) != get("offer"):
                    return back
                why = get("why") if get("why") in feedback.DECLINE_REASONS else None
                outcome = "no answer" if get("answer") == "no answer" else "no"
                keep = get("answer") == "no, keep me on" and next((p for p in view["people"]
                                                                   if live["line"] in p["lines"]), None)
                with con:
                    store.answer_offer(con, live["id"], outcome, by, now, why)
                    if keep:  # "keep me on, but not this one" counts as contact: the 60-day clock restarts (plan §11)
                        store.add_decision(con, "still interested", keep["lines"][0], by, now,
                                           entry={"added": self.today(), "name": keep["name"], "phone": keep["phone"],
                                                  "spec": LineSpec()}, everyone=set(load_config(self.config_path).therapists),
                                           summary="said no to an offer, still interested")
                note = f"offer: {get('answer')} from line {live['line']} for {opening['opening_id']}"
            elif do == "book":
                if not live or str(live["id"]) != get("offer"):
                    return refuse("That offer isn't open any more. Reload the page.")
                if not get("checked"):
                    return self._booking_card(opening, live, view,
                                              error="Check in Kneadly that our hold is still there first.")
                lengths = self._lengths(opening, live, view)
                if get("how") not in store.BOOKED_HOW or not get("length").isdigit() or int(get("length")) not in lengths:
                    return self._booking_card(opening, live, view, error="Choose the length and how it goes into Kneadly.")
                label = f"{opening['opening_id']} {pages._day(opening['date'])} {opening['start']}"
                with con:
                    store.add_rebooking(con, live, label, int(get("length")), get("how"), get("kneadly_id"), by, now)
                note = f"offer: yes from line {live['line']} for {opening['opening_id']}"
            elif do == "undo_yes":
                if get("rebooking").isdigit():
                    with con:
                        undone = store.undo_rebooking(con, int(get("rebooking")), now)
                    note = f"refill for {opening['opening_id']} undone" if undone else None
            elif do == "taken":
                how = get("how") if get("how") in store.TAKEN_HOW else "another way"
                if status in ("new", "held"):
                    with con:
                        store.close_opening(con, aid, "taken", by, now, how)
            elif do == "release":
                if status == "held" and not get("checked"):
                    return refuse("Remove the block in Kneadly first, so the slot is free again.")
                if status in ("new", "held"):
                    with con:
                        store.close_opening(con, aid, "released", by, now,
                                            "the start time passed" if get("how") == "passed" else "nobody left")
            elif do == "reopen":
                with con:
                    store.reopen(con, aid)
            elif do == "in_kneadly":
                if get("rebooking").isdigit():
                    with con:
                        store.mark_in_kneadly(con, int(get("rebooking")), get("kneadly_id")[:20], now)
                return redirect("/check")
            else:
                return refuse("That step couldn't be read. Reload the page.")
        finally:
            con.close()
        if note:  # someone said no, yes, or a yes was undone: the names change
            self.rematch(view, note)
        return redirect("/check") if get("how") == "passed" else back

    def _lengths(self, opening, offer, view):
        person = next((p for p in view["people"] if offer["line"] in p["lines"]), {})
        fits = sorted((n for n in person.get("lengths", []) if n <= opening["length_min"]), reverse=True)
        return fits or [opening["length_min"]]

    def _booking_card(self, opening, offer, view, error=None):
        person = next((p for p in view["people"] if offer["line"] in p["lines"]), {})
        config = load_config(self.config_path)
        return self.page(pages.booking_page, opening, offer, person, self._lengths(opening, offer, view),
                         self._first_name(config), error=error, status="400 Bad Request" if error else "200 OK")

    def _unfinished(self, con):
        """(refills not in Kneadly, holds on openings that have started, offers waiting 20+ min): the daily check."""
        openings = {r["appointment_id"]: dict(r) for r in con.execute("SELECT * FROM openings")}
        state, now = store.desk_state(con), self.now()
        not_in = [r for r in store.active_rebookings(con) if not r["in_kneadly"]]
        passed, waiting = [], []
        for aid, s in state.items():
            o = openings.get(aid)
            if o is None or s["status"] != "held":
                continue
            starts = datetime.strptime(f"{o['date']} {o['start']}", "%Y-%m-%d %H:%M")
            if s["live"] and pages._minutes(s["live"]["offered_at"], now) >= 20:
                waiting.append((o, s))
            if starts < now and not s["live"]:
                passed.append((o, s))
        return not_in, passed, waiting

    def daily_check(self):
        if not self.db_path.exists():
            return self.page(pages.check_page, [], [], [], self.now())
        con = store.connect(self.db_path)
        try:
            not_in, passed, waiting = self._unfinished(con)
        finally:
            con.close()
        return self.page(pages.check_page, not_in, passed, waiting, self.now())

    def rebookings_csv(self):
        """Every refill, for Julie's report. No desk names, like every output file."""
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(["opening", "rebooked_into", "client", "phone", "line", "length_min", "how", "in_kneadly",
                    "kneadly_id", "saved_at"])
        if self.db_path.exists():
            con = store.connect(self.db_path)
            try:
                for r in store.active_rebookings(con):
                    w.writerow([r["label"], r["appointment_id"], r["person"], pages.phone_display(r["phone"]),
                                r["line"], r["length_min"], r["how"], "yes" if r["in_kneadly"] else "no",
                                r["kneadly_id"] or "", r["made_at"]])
            finally:
                con.close()
        return Response(out.getvalue(), content_type="text/csv; charset=utf-8",
                        headers=[("Content-Disposition", 'attachment; filename="rebookings.csv"')])

    def log(self):
        history = []
        if self.db_path.exists():
            con = store.connect(self.db_path)
            try:
                history = [{**h, "summary": json.loads(h["summary"])} for h in store.import_history(con)]
            finally:
                con.close()
        return self.page(pages.log_page, history)

    def download(self, name):
        if name not in DOWNLOADS or not (self.out_dir / name).is_file():
            return self.page(pages.message_page, "Not found", "That file isn't there. Upload the files first.",
                             status="404 Not Found")
        disposition = "attachment" if name.endswith(".csv") else "inline"
        return Response((self.out_dir / name).read_bytes(), content_type=f"{DOWNLOADS[name]}; charset=utf-8",
                        headers=[("Content-Disposition", f'{disposition}; filename="{name}"')])

    # ---------- needs review: decisions on held people ----------

    def _latest(self):
        """(latest run view or None, recent decisions)."""
        if not self.db_path.exists():
            return None, []
        con = store.connect(self.db_path)
        try:
            return store.latest_run(con), store.recent_decisions(con)
        finally:
            con.close()

    def review(self, done=False, error=None, status="200 OK"):
        view, decisions = self._latest()
        people = view["people"] if view else []
        warnings = view["summary"].get("run_warnings", []) if view else []
        return self.page(pages.review_page, people, decisions, warnings, done=done, error=error, status=status)

    def _person(self, view, line):
        return next((p for p in (view["people"] if view else []) if line in p["lines"]), None)

    def fill(self, line_text):
        view, _ = self._latest()
        person = self._person(view, int(line_text)) if line_text.isdigit() else None
        if person is None:
            return self.review(error="That person isn't on the list any more.", status="404 Not Found")
        config = load_config(self.config_path)
        return self.page(pages.fill_page, person, self._therapists(config), prefill_from_record(person, config),
                         self._rules(config))

    @staticmethod
    def _rules(config):
        return [(rule.tag, rule.chip) for rule in config.routing]

    @staticmethod
    def _therapists(config):
        return [(name, t.first_name) for name, t in config.therapists.items()]

    def decide(self, form):
        """One decision from the review screen: saved, then the openings are matched again."""
        def get(k):
            return form.get(k, [""])[0].strip()
        kind, _, rest = get("choice").partition("|")
        line_text, _, other_text = rest.partition("|")
        checked_by = get("checked_by")
        view, _ = self._latest()
        if view is None:
            return self.review(error="Nothing has been uploaded yet.", status="400 Bad Request")
        line = int(line_text) if line_text.isdigit() else None
        person = self._person(view, line) if line else None
        config = load_config(self.config_path)

        def refuse(message):
            if kind == "start over" and person:
                return self.page(pages.fill_page, person, self._therapists(config), prefill_from_form(form),
                                 self._rules(config),
                                 error=message, status="400 Bad Request")
            return self.review(error=message, status="400 Bad Request")
        if not checked_by:
            return refuse("Write your name, so the decision is on record.")
        con = store.connect(self.db_path)
        try:
            known = store.line_numbers(con)
            if line not in known:
                return refuse("That decision couldn't be read. Reload the page and try again.")
            now = self.now()
            if kind in store.IDENTITY:
                other = None
                if kind != "ignore":
                    if other_text == "?":
                        other_text = get(f"other_{line}")
                    other = int(other_text) if other_text.isdigit() else None
                    if other is None or other == line or other not in known:
                        return refuse(f"Give the number of the other line that is the same person as line {line}.")
                with con:
                    store.add_decision(con, kind, line, checked_by, now, other_line=other)
                note = f"desk decision: {kind}, line {line}" + (f" and line {other}" if other else "")
            elif kind in store.ENTRY:
                if person is None:
                    return refuse("That person isn't on the list any more.")
                if kind == "start over":
                    try:
                        spec = card_spec(form, config, person)
                    except CardError as e:
                        return refuse(str(e))
                else:
                    spec = LineSpec() if kind == "still wants it" else LineSpec(gone="take off")
                entry = {"added": self.today(), "name": person["name"], "phone": person["phone"], "spec": spec}
                with con:
                    store.add_decision(con, kind, person["lines"][0], checked_by, now, entry=entry,
                                       everyone=set(config.therapists))
                note = f"desk decision: {kind}, {person['name']}"
            elif kind == store.KEEP_NEW_TEXT:
                with con:
                    store.add_decision(con, kind, line, checked_by, now)
                note = f"desk decision: line {line}, new text kept"
            else:
                return refuse("That decision couldn't be read. Reload the page and try again.")
        finally:
            con.close()
        self.rematch(view, note)
        return redirect("/review?done=1")

    def undo(self, form):
        decision_id = form.get("id", [""])[0]
        view, _ = self._latest()
        if not decision_id.isdigit() or view is None:
            return self.review(error="That decision couldn't be found.", status="400 Bad Request")
        con = store.connect(self.db_path)
        try:
            with con:
                undone = store.undo_decision(con, int(decision_id), self.now())
        finally:
            con.close()
        if undone:
            self.rematch(view, f"desk decision #{decision_id} undone")
        return redirect("/review?done=1")

    def rematch(self, view, note, keep_order=True, db_path=None, config_path=None, out_dir=None, allow_paused=False,
                run_date=None, add_ids=()):
        """Matches the last run's openings (plus `add_ids`) again, so every screen shows the change: with the last
        run's date, or `run_date` (today, for the inbox). The order stays the last run's, unless the settings
        changed it (`keep_order=False`). Inbox openings count their notice from now."""
        ids = [o["appointment_id"] for o in view["openings"]]
        ids += [a for a in add_ids if a not in ids]
        return sync(db_path or self.db_path, run_date or date.fromisoformat(view["run"]["run_date"]),
                    out_dir=out_dir or self.out_dir, config_path=config_path or self.config_path,
                    order=view["run"]["order_mode"] if keep_order else None, opening_ids=ids, note=note,
                    allow_paused=allow_paused, now=self.now())

    # ---------- the cancellation inbox (plan §9.4) ----------

    def inbox(self, day_text="", message=None, desk=""):
        try:
            day = date.fromisoformat(day_text) if day_text else self.today()
        except ValueError:
            day = self.today()
        if not self.db_path.exists():
            return self.page(pages.inbox_page, day, [], [], [], message, desk)
        config = load_config(self.config_path)
        first = self._first_name(config)
        now = self.now()
        con = store.connect(self.db_path)
        try:
            day_bookings = store.bookings_on(con, day)
            view = store.latest_run(con)
            state = store.desk_state(con)
            names = {a: [r["person"] for r in rows if r["rank"] > 0] for a, rows in (view["rows"] if view else {}).items()}
            rows = []
            for o in (dict(r) for r in con.execute("SELECT * FROM openings")):
                rows.append({**o, "late": True, "in_run": o["appointment_id"] in names,
                             "names": names.get(o["appointment_id"]), "status": self._inbox_status(o, state)})
            for c in store.normal_cancellations(con):
                if not store.heard_already(con, c["appointment_id"]).get("opening_id"):
                    rows.append({**c, "opening_id": None, "late": False, "in_run": False, "names": None,
                                 "status": "not late: Kneadly's online page offers it"})
        finally:
            con.close()
        upcoming, earlier = [], []
        for r in sorted(rows, key=lambda r: (r["date"], r["start"])):
            starts = datetime.strptime(f"{r['date']} {r['start']}", "%Y-%m-%d %H:%M")
            r["therapist"] = first(r["therapist"])
            r["notice"] = round((starts - now).total_seconds() / 3600, 1) if starts >= now else None
            (upcoming if starts >= now else earlier).append(r)
        return self.page(pages.inbox_page, day, day_bookings, upcoming, earlier, message, desk)

    @staticmethod
    def _inbox_status(o, state):
        if "no-show" in o["kind"].lower():
            return "no-show: never offered"
        s = state.get(o["appointment_id"])
        if not s or s["status"] == "new":
            return "new"
        if s["status"] == "held":
            return f"offering to {s['live']['person']}" if s["live"] else "held in Kneadly"
        if s["status"] == "filled" and s["rebooking"]:
            return f"filled: {s['rebooking']['person']}"
        return f"{s['status']}: {s['closed_how']}"

    def cancel_form(self, appointment="", manual=False, error=None, values=None, status="200 OK", desk=""):
        config = load_config(self.config_path)
        slot = None
        if appointment and not manual and self.db_path.exists():
            con = store.connect(self.db_path)
            try:
                slot = store.booking(con, appointment)
            finally:
                con.close()
            if slot is None:
                return self.inbox(message="That booking isn't in the uploaded files: enter it with its number.",
                                  desk=desk)
        return self.page(pages.cancel_page, slot, list(config.therapists), store.CHANNELS,
                         self.now().strftime("%Y-%m-%dT%H:%M"), error=error, values=values, status=status)

    def record_cancellation(self, form):
        """One cancellation from the inbox: under 24 h before the start it's an opening, matched straight away."""
        def get(k):
            return form.get(k, [""])[0].strip()
        manual, aid = bool(get("manual")), get("appointment")
        values = {k: get(k) for k in ("appointment", "date", "start", "therapist", "length", "heard_via", "cancelled_at")}

        def refuse(message):
            return self.cancel_form(aid, manual or not aid, error=message, values=values, status="400 Bad Request",
                                    desk=get("_desk"))
        if not get("_desk"):
            return refuse("Say who's at the desk first (top of the openings page).")
        view, _ = self._latest()
        if view is None:
            return refuse("Upload the files first.")
        config = load_config(self.config_path)
        now = self.now()
        con = store.connect(self.db_path)
        try:
            if manual:
                if not re.fullmatch(r"[A-Za-z0-9-]{1,20}", aid):
                    return refuse("Give the Kneadly appointment number (letters, numbers and dashes).")
                try:
                    slot = {"appointment_id": aid, "date": date.fromisoformat(get("date")),
                            "start": datetime.strptime(get("start")[:5], "%H:%M").time(), "therapist": get("therapist"),
                            "length_min": int(get("length"))}
                except ValueError:
                    return refuse("Give the date, start time and length.")
                if slot["therapist"] not in config.therapists or slot["length_min"] not in (30, 45, 60, 90):
                    return refuse("Choose the therapist and length from the lists.")
            else:
                b = store.booking(con, aid)
                if b is None:
                    return refuse("That booking isn't in the uploaded files: enter it with its number.")
                slot = {"appointment_id": aid, "date": date.fromisoformat(b["date"]),
                        "start": datetime.strptime(b["start"], "%H:%M").time(), "therapist": b["therapist"],
                        "length_min": b["length_min"], "client_name": b["client_name"]}
            if get("heard_via") not in store.CHANNELS:
                return refuse("Choose how it came in from the list.")
            try:
                cancelled_at = datetime.strptime(get("cancelled_at")[:16], "%Y-%m-%dT%H:%M")
            except ValueError:
                return refuse("Give the date and time they cancelled.")
            starts = datetime.combine(slot["date"], slot["start"])
            if cancelled_at > now + timedelta(minutes=5):
                return refuse("The time they cancelled can't be later than now.")
            if cancelled_at >= starts:
                return refuse("That's at or after the start: it's a no-show, and no-shows are never offered.")
            heard = store.heard_already(con, aid)
            if heard:
                return self.inbox(message=f"Already in the inbox: heard via {heard['heard_via']} "
                                          f"({heard['cancelled_at']}). One row per appointment: nothing added.",
                                  desk=get("_desk"))
            with con:
                opening_id = store.record_cancellation(con, slot, cancelled_at, get("heard_via"), get("_desk"), now)
        finally:
            con.close()
        if opening_id is None:
            return self.inbox(message=f"Recorded. {aid} was cancelled 24 hours or more before the start, so it isn't a "
                                      "late cancellation: Kneadly's online page offers it. Nothing to do here.",
                              desk=get("_desk"))
        self.rematch(view, f"inbox: {opening_id} ({aid}) cancelled via {get('heard_via')}", run_date=self.today(),
                     add_ids=[aid])
        return redirect(f"/#o-{quote(aid)}")

    # ---------- the feedback report (plan §11) ----------

    def report_screen(self, since_text="", until_text=""):
        try:
            until = date.fromisoformat(until_text) if until_text else self.today()
            since = date.fromisoformat(since_text) if since_text else until - timedelta(days=27)
        except ValueError:
            until, since = self.today(), self.today() - timedelta(days=27)
        if not self.db_path.exists():
            data = {"since": since, "until": until, "openings": 0, "no_shows": 0, "outcome": {}, "by_channel": {},
                    "median_minutes": None, "refilled": 0, "offers": 0, "offer_outcomes": {}, "reasons": {},
                    "mistakes": [], "export": {}}
            return self.page(pages.report_page, data)
        con = store.connect(self.db_path)
        try:
            data = feedback.report(con, since, until)
        finally:
            con.close()
        return self.page(pages.report_page, data)

    def outcomes_csv(self):
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(["opening", "rebooked_into", "date", "start", "therapist", "length_min", "hours_notice", "offers",
                    "filled_by", "status"])
        if self.db_path.exists():
            con = store.connect(self.db_path)
            try:
                w.writerows(feedback.outcomes_rows(con))
            finally:
                con.close()
        return Response(out.getvalue(), content_type="text/csv; charset=utf-8",
                        headers=[("Content-Disposition", 'attachment; filename="outcomes.csv"')])

    # ---------- the waitlist board (plan §6) ----------

    def board_screen(self, show="active", query="", desk="", message=None):
        view, _ = self._latest()
        people = view["people"] if view else []
        counts = {"active": 0, "review": 0, "stale": 0, "all": len(people)}
        for p in people:
            counts[p["status"]] = counts.get(p["status"], 0) + 1
        show = show if show in counts else "active"
        shown = people if show == "all" else [p for p in people if p["status"] == show]
        if query.strip():
            words, digits = fold(query.strip()), re.sub(r"\D", "", query)
            shown = [p for p in shown if words in fold(p["name"]) or (len(digits) >= 3 and digits in (p["phone"] or ""))]
        shown.sort(key=lambda p: (p["first_asked"] or "9999", p["name"]))
        config = load_config(self.config_path)
        since, flags = None, {}
        if self.db_path.exists():
            con = store.connect(self.db_path)
            try:
                since = store.get_meta(con, "board_only_since") if store.board_only(con) else None
                for first, r in feedback.resting(con, people, config.max_offers_per_week, self.now()).items():
                    flags.setdefault(first, []).append(f"resting until {r['until']:%a %b %d} ({r['count']} offers this week)")
                for first in feedback.three_nos(con, people):
                    flags.setdefault(first, []).append("said no 3 times in a row: ask if still interested")
            finally:
                con.close()
        return self.page(pages.board_page, shown, counts, show, query, list(config.therapists), self._first_name(config),
                         since, message, desk, flags)

    def board_card(self, line_text):
        view, _ = self._latest()
        person = self._person(view, int(line_text)) if line_text.isdigit() else None
        if person is None:
            return self.board_screen(message="That person isn't on the waitlist any more.")
        config = load_config(self.config_path)
        return self.page(pages.fill_page, person, self._therapists(config), prefill_from_record(person, config),
                         self._rules(config), mode="board")

    def board_history(self, line_text):
        view, _ = self._latest()
        person = self._person(view, int(line_text)) if line_text.isdigit() else None
        if person is None:
            return self.board_screen(message="That person isn't on the waitlist any more.")
        con = store.connect(self.db_path)
        try:
            book = [dict(r) for r in con.execute("SELECT line, added_raw FROM waitlist_lines ORDER BY line")
                    if r["line"] in person["lines"]]
            decisions = store.decisions_for(con, person["lines"])
        finally:
            con.close()
        return self.page(pages.history_page, person, book, decisions)

    def board_action(self, form):
        """Every change on the board is a desk entry (like the review queue's): saved with who and when, undoable,
        and the openings are matched again straight after. The matching rules don't change."""
        def get(k):
            return form.get(k, [""])[0].strip()
        do, by = get("do"), get("_desk")
        view, _ = self._latest()
        if not by:
            return self.board_screen(message="Say who's at the desk first (top of the openings page).")
        if view is None:
            return self.board_screen(desk=by, message="Upload the book first: the waitlist starts from it.")
        config = load_config(self.config_path)
        everyone, now = set(config.therapists), self.now()
        con = store.connect(self.db_path)
        try:
            if do == "mode":
                on = get("on") == "yes"
                if on and not get("agreed"):
                    return self.board_screen(desk=by, message="Retiring the book needs everyone's agreement first: tick the box.")
                with con:
                    store.set_meta(con, "board_only", "yes" if on else "no")
                    store.set_meta(con, "board_only_since", f"{self.today():%a %b %d, %Y}" if on else "")
                return redirect("/board")
            if do == "add":
                name, phone = " ".join(get("name").split()), normalise_phone(get("phone"))

                def again(message):
                    return self.page(pages.fill_page, None, self._therapists(config), prefill_from_form(form),
                                     self._rules(config), error=message, mode="add",
                                     values={"name": get("name"), "phone": get("phone")}, status="400 Bad Request")
                if len(name) < 2:
                    return again("Give their name.")
                if phone is None:
                    return again("Give a 10-digit phone number.")
                same = next((p for p in view["people"] if p["phone"] == phone), None)
                if same:
                    return self.board_screen("all", phone, by, f"Already on the waitlist with that number: {same['name']}. "
                                                               "Open their card instead.")
                try:
                    spec = card_spec(form, config, {})
                except CardError as e:
                    return again(str(e))
                with con:
                    did = store.add_decision(con, store.ADD, 0, by, now, entry={"added": self.today(), "name": name,
                                             "phone": phone, "spec": spec}, everyone=everyone, summary="added on the board")
                note, anchor = f"board: {name} added", store.DESK_LINE_START - 1 + did
            else:
                person = self._person(view, int(get("line"))) if get("line").isdigit() else None
                if person is None:
                    return self.board_screen(desk=by, message="That person isn't on the waitlist any more. Reload the page.")
                entry = {"added": self.today(), "name": person["name"], "phone": person["phone"]}
                anchor = person["lines"][0]
                if do == "card":
                    try:
                        spec = card_spec(form, config, person)
                    except CardError as e:
                        return self.page(pages.fill_page, person, self._therapists(config), prefill_from_form(form),
                                         self._rules(config), error=str(e), mode="board", status="400 Bad Request")
                    changed = card_changes(prefill_from_record(person, config), prefill_from_form(form))
                    if not changed:
                        return self.board_screen(message=f"Nothing changed on {person['name']}'s card.", desk=by)
                    kind, summary = "card edit", ", ".join(changed)
                elif do == "still":
                    spec, kind, summary = LineSpec(), "still interested", "still interested"
                elif do == "takeoff" and get("reason") in pages.TAKE_OFF_REASONS:
                    token = {"moved": "moved", "going to another clinic": "going to"}.get(get("reason"), "take off")
                    spec, kind, summary = LineSpec(gone=token), "take off", f"taken off: {get('reason')}"
                else:
                    return self.board_screen(desk=by, message="That change couldn't be read. Reload the page.")
                with con:
                    store.add_decision(con, kind, anchor, by, now, entry={**entry, "spec": spec}, everyone=everyone,
                                       summary=summary)
                note = f"board: {person['name']}, {summary}"
        finally:
            con.close()
        self.rematch(view, note)
        return redirect(f"/board?show=all#p-{anchor}")

    # ---------- the morning call list (plan §9.4, technical plan §11.5) ----------

    def calls(self, from_text="", desk="", message=None):
        try:
            first_day = date.fromisoformat(from_text) if from_text else self.today()
        except ValueError:
            first_day = self.today()
        is_today = first_day == self.today()
        rows, after = [], {}
        if self.db_path.exists():
            config = load_config(self.config_path)
            first = self._first_name(config)
            con = store.connect(self.db_path)
            try:
                rows = store.call_list(con, [first_day, first_day + timedelta(days=1)], self.now() if is_today else None)
                view = store.latest_run(con)
                people = {line: p for p in (view["people"] if view else []) for line in p["lines"]}
                for b in rows:
                    b["therapist"] = first(b["therapist"])
                    if b["state"] == "cancelled":
                        after[b["appointment_id"]] = self._after_cancel(con, b["appointment_id"], view, people)
            finally:
                con.close()
        return self.page(pages.calls_page, first_day, is_today, rows, after, message, desk)

    @staticmethod
    def _after_cancel(con, aid, view, people):
        heard = store.heard_already(con, aid)
        if heard is None:
            return None
        if heard["opening_id"] is None:
            return {"note": "Cancelled 24 hours or more before the start: not a late cancellation. Kneadly's online "
                            "page offers it."}
        o = con.execute("SELECT hours_notice FROM openings WHERE appointment_id = ?", (aid,)).fetchone()
        names = [{**r, "phone": people.get(r["line"], {}).get("phone")}
                 for r in (view["rows"].get(aid, []) if view else []) if r["rank"] > 0]
        return {"opening_id": heard["opening_id"], "appointment_id": aid, "notice": f"{o[0]:g}", "names": names}

    def call_action(self, form):
        """One tap on the call list. Cancelled goes through the inbox as a morning call: under 24 h before the start
        it's an opening, and its names appear right under the booking."""
        def get(k):
            return form.get(k, [""])[0].strip()
        aid, do, by, from_text = get("appointment"), get("do"), get("_desk"), get("from")
        back = redirect(f"/calls?from={quote(from_text)}#c-{quote(aid)}" if from_text else f"/calls#c-{quote(aid)}")
        if not by:
            return self.calls(from_text, message="Say who's at the desk first (top of the openings page).")
        now = self.now()
        con = store.connect(self.db_path)
        try:
            b = store.booking(con, aid)
            if b is None or do not in ("confirmed", "voicemail", "cancelled", "undo"):
                return self.calls(from_text, by, "That booking couldn't be found. Reload the page.")
            if do == "undo":
                with con:
                    store.undo_last_call(con, aid, now)
                return back
            if do != "cancelled":
                with con:
                    store.add_call(con, aid, do, by, now)
                return back
            slot = {"appointment_id": aid, "date": date.fromisoformat(b["date"]),
                    "start": datetime.strptime(b["start"], "%H:%M").time(), "therapist": b["therapist"],
                    "length_min": b["length_min"]}
            if now >= datetime.combine(slot["date"], slot["start"]):
                return self.calls(from_text, by, "That visit has already started: if they didn't come, it's a "
                                                 "no-show, and no-shows are never offered.")
            heard = store.heard_already(con, aid)
            with con:
                store.add_call(con, aid, "cancelled", by, now)
                opening_id = None if heard else store.record_cancellation(con, slot, now, "morning call", by, now)
        finally:
            con.close()
        if opening_id:
            view, _ = self._latest()
            self.rematch(view, f"call list: {opening_id} ({aid}) cancelled on a morning call", run_date=self.today(),
                         add_ids=[aid])
        return back

    def match_again(self, form):
        view, _ = self._latest()
        if view:
            self.rematch(view, "matched again from the inbox", run_date=self.today())
        return redirect("/inbox")

    # ---------- settings: check, then save; versions; the owner's switch ----------

    def settings_screen(self, saved=False, raw=None, problems=(), notice=None, status="200 OK"):
        current = settings_logic.read_file(self.config_path)
        versions, paused = [], False
        if self.db_path.exists():
            con = store.connect(self.db_path)
            try:
                versions, paused = store.settings_versions(con), store.is_paused(con)
            finally:
                con.close()
        file_note = None
        if versions and versions[0]["settings"] != current:
            file_note = ("The settings file was changed outside this screen after the last save here. What you see "
                         "is the file as it is now; saving from here records it as a new version.")
        return self.page(pages.settings_page, raw or current, settings_logic.orders(), versions, paused,
                         file_note=file_note, problems=problems, saved=saved, notice=notice, status=status)

    def check_settings(self, form):
        current = settings_logic.read_file(self.config_path)
        raw, problems = settings_logic.form_to_settings(form, current)
        problems += settings_logic.problems_with(raw)
        if problems:
            return self.settings_screen(raw=raw, problems=problems, status="400 Bad Request")
        return self._preview_settings(current, raw)

    def restore_settings(self, form):
        version_id = form.get("id", [""])[0]
        raw = None
        if version_id.isdigit() and self.db_path.exists():
            con = store.connect(self.db_path)
            try:
                raw = store.settings_version(con, int(version_id))
            finally:
                con.close()
        if raw is None:
            return self.settings_screen(problems=["That version couldn't be found."], status="404 Not Found")
        problems = settings_logic.problems_with(raw)
        if problems:
            return self.settings_screen(raw=raw, problems=problems, status="400 Bad Request")
        return self._preview_settings(settings_logic.read_file(self.config_path), raw)

    def rules_screen(self, saved=False, raw=None, problems=(), status="200 OK"):
        raw = raw or settings_logic.read_file(self.config_path)
        return self.page(pages.rules_page, raw, settings_logic.routing_of(raw), raw.get("therapists", {}),
                         problems=problems, saved=saved, status=status)

    def check_rules(self, form):
        current = settings_logic.read_file(self.config_path)
        raw, problems = settings_logic.rules_to_settings(form, current)
        problems += settings_logic.problems_with(raw)
        if problems:
            return self.rules_screen(raw=raw, problems=problems, status="400 Bad Request")
        return self._preview_settings(current, raw, back="/rules")

    def _preview_settings(self, current, raw, back="/settings"):
        """What saving would change: the settings, and the names on the last run's openings (matched again on a
        temporary copy of the database with the new settings, then thrown away). A change to the health routing
        rules, the private words or the therapists' tags also needs Marc's approval (plan §7.2)."""
        change_list = settings_logic.changes(current, raw)
        if not change_list:
            if back == "/rules":
                return self.rules_screen(problems=["Nothing changed: these are the rules already in use."])
            return self.settings_screen(notice="Nothing changed: these are the settings already in use.")
        approval = settings_logic.rules_changed(current, raw)
        notes = []
        view, _ = self._latest()
        before = after = {"active": 0, "stale": 0, "review": 0}
        name_changes = []
        if view:
            before = {s: sum(p["status"] == s for p in view["people"]) for s in before}
            with tempfile.TemporaryDirectory() as tmp:
                tmp = Path(tmp)
                shutil.copyfile(self.db_path, tmp / "check.db")
                settings_logic.write_file(tmp / "clinic.json", raw)
                result = self.rematch(view, "settings check", keep_order=False, db_path=tmp / "check.db",
                                      config_path=tmp / "clinic.json", out_dir=tmp / "out", allow_paused=True)
            after = {s: sum(p.status == s for p in result["people"]) for s in before}
            config = result["config"]
            tagged = set().union(*(t.tags for t in config.therapists.values()))
            cut_off = sum(1 for p in result["people"] if p.status == "active" and p.needs - tagged)
            if cut_off:
                notes.append(f"{cut_off} people on the list need a tag no therapist has any more: they won't be "
                             "offered anything until a therapist has it again.")
            for r in result["results"]:
                now = [x["person"] for x in view["rows"].get(r.opening.appointment_id, []) if x["rank"] > 0]
                new = [p.person.name for p in r.picks]
                if now != new:
                    t = config.therapist_by_name(r.opening.therapist)
                    name_changes.append({"opening": f"{r.opening.opening_id} · {r.opening.date:%a %b %d} "
                                                    f"{r.opening.start:%H:%M} · {t.first_name if t else r.opening.therapist}",
                                         "before": now, "after": new})
        if settings_logic.routing_of(current) != settings_logic.routing_of(raw) or \
                current.get("health_words") != raw.get("health_words"):
            notes.append("New or changed words apply to the book's lines on its next upload; the names above only "
                         "change where a therapist's tag changed.")
        token = secrets.token_urlsafe(16)
        self.pending_settings[token] = {"raw": raw, "changes": change_list, "at": clock.monotonic(),
                                        "approval": approval, "back": back}
        return self.page(pages.settings_preview_page, token, change_list, name_changes, before, after,
                         note=" ".join(notes) or None, approval=approval, back=back)

    def save_settings(self, form):
        token, name = form.get("token", [""])[0], form.get("checked_by", [""])[0].strip()
        pending = self.pending_settings.pop(token, None)
        if pending is None:
            return self.settings_screen(problems=["That check has expired or was already saved. Check the changes "
                                                  "again."], status="400 Bad Request")
        if not name:
            return self.settings_screen(raw=pending["raw"], problems=["Write your name, so the change is on record."],
                                        status="400 Bad Request")
        if pending.get("approval") and not form.get("approved", [""])[0]:
            return self.settings_screen(problems=["A change to the health routing rules needs Marc's approval: tick "
                                                  "the box when he has said yes. Nothing was saved."],
                                        status="400 Bad Request")
        problems = settings_logic.problems_with(pending["raw"])
        if problems:
            return self.settings_screen(raw=pending["raw"], problems=problems, status="400 Bad Request")
        current = settings_logic.read_file(self.config_path)
        now = self.now()
        con = store.connect(self.db_path)
        try:
            with con:
                if not store.settings_versions(con, limit=1):  # keep the settings as they were before the first change
                    store.save_settings_version(con, current, name, now, [])
                store.save_settings_version(con, pending["raw"], name, now, pending["changes"])
        finally:
            con.close()
        settings_logic.write_file(self.config_path, pending["raw"])
        view, _ = self._latest()
        if view:
            self.rematch(view, "settings changed: " + "; ".join(pending["changes"]), keep_order=False,
                         allow_paused=True)
        return redirect(f"{pending.get('back', '/settings')}?saved=1")

    def pause(self, form):
        name, action = form.get("checked_by", [""])[0].strip(), form.get("action", [""])[0]
        if not name or action not in ("pause", "resume"):
            return self.settings_screen(problems=["Write your name, so the switch is on record."],
                                        status="400 Bad Request")
        con = store.connect(self.db_path)
        try:
            with con:
                store.set_paused(con, action == "pause", name, self.now())
        finally:
            con.close()
        return redirect("/settings")

    # ---------- compare orders ----------

    def compare(self, appointment_id):
        view, _ = self._latest()
        if view is None or appointment_id not in {o["appointment_id"] for o in view["openings"]}:
            return self.page(pages.message_page, "Not found", "That opening isn't in the last run.",
                             status="404 Not Found")
        config = load_config(self.config_path)
        con = store.connect(self.db_path)
        try:
            _, _, bookings, people, _, _ = people_from_db(con, date.fromisoformat(view["run"]["run_date"]), config)
            opening = store.load_openings(con, [appointment_id])[0]
        finally:
            con.close()
        therapist = config.therapist_by_name(opening.therapist)
        first = therapist.first_name if therapist else opening.therapist

        def basis(order, p):
            asked = f"asked {p.first_asked:%b %d}" if p.first_asked else "asked: date unknown"
            if order == "shortest-notice":
                return "told the day before" if p.day_before else f"{p.notice:g} h notice"
            if order == "regulars-first":
                visits = visits_with(p, opening.therapist, bookings, config.nicknames)
                if p.regular_of == opening.therapist or visits >= config.regular_min_visits:
                    return f"regular of {first}" + (f", {visits} visits" if visits else "")
                return f"not a regular · {asked}"
            return asked
        columns = [(order, words, [(pick.person.name, basis(order, pick.person))
                                   for pick in match_opening(opening, people, bookings, config, order).picks])
                   for order, words in settings_logic.orders()]
        everyone = [pick.person.name for pick in
                    match_opening(opening, people, bookings, replace(config, max_names=10_000), "first-asked").picks]
        header = (f"{opening.opening_id} · {opening.date:%a %b %d} {opening.start:%H:%M} · {first} · "
                  f"{opening.length_min} min · {opening.hours_notice:g} h notice")
        return self.page(pages.compare_page, header, columns, everyone)

    # ---------- upload: check, then save or cancel ----------

    def check(self, body, content_type):
        empty = self._db_is_empty()
        try:
            fields, files = parse_multipart(body, content_type)
        except Exception:
            return self.page(pages.upload_page, self.today(), empty, "The upload couldn't be read. Try again.",
                             status="400 Bad Request")
        uploads = {k: files[k] for k in KINDS if k in files}
        try:
            run_date = date.fromisoformat(fields.get("run_date", "").strip())
        except ValueError:
            return self.page(pages.upload_page, self.today(), empty, "The run date isn't a date.",
                             status="400 Bad Request")
        if not uploads:
            return self.page(pages.upload_page, self.today(), empty, "Choose at least one file.",
                             status="400 Bad Request")
        try:
            check = self._try_sync(uploads, run_date)
        except (InputError, ValueError) as e:
            return self.page(pages.upload_page, self.today(), empty, f"Stopped: {e}", status="400 Bad Request")
        token = secrets.token_urlsafe(16)
        self.pending[token] = {"files": uploads, "run_date": run_date, "at": clock.monotonic()}
        return self.page(pages.preview_page, token, self._names(uploads), check)

    def save(self, token):
        pending = self.pending.pop(token, None)
        if pending is None:
            return self.page(pages.upload_page, self.today(), self._db_is_empty(),
                             "That check has expired or was already saved. Upload the files again.",
                             status="400 Bad Request")
        try:
            with tempfile.TemporaryDirectory() as tmp:
                paths = self._write(Path(tmp), pending["files"])
                result = sync(self.db_path, pending["run_date"], out_dir=self.out_dir, config_path=self.config_path,
                              input_names=self._names(pending["files"]), **paths)
        except (InputError, ValueError) as e:
            return self.page(pages.upload_page, self.today(), self._db_is_empty(), f"Stopped: {e}",
                             status="400 Bad Request")
        return redirect(f"/?saved={result['import_id']}")

    def cancel(self, token):
        self.pending.pop(token, None)
        return redirect("/upload")

    def _try_sync(self, uploads, run_date):
        """The real sync on a temporary copy of the database: exactly what saving would do, then thrown away."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            db = tmp / "check.db"
            if self.db_path.exists():
                shutil.copyfile(self.db_path, db)
            paths = self._write(tmp, uploads)
            result = sync(db, run_date, out_dir=tmp / "out", config_path=self.config_path,
                          input_names=self._names(uploads), **paths)
        people = result["people"]
        return {"run_date": run_date.isoformat(), "summary": result["summary"], "gaps": result["gaps"],
                "warnings": result["warnings"], "openings": len(result["results"]),
                "named": sum(1 for r in result["results"] if r.picks),
                "people": {"total": len(people), **{s: sum(p.status == s for p in people)
                                                    for s in ("active", "stale", "review")}}}

    @staticmethod
    def _names(uploads):
        return {k: name for k, (name, _) in uploads.items()}

    @staticmethod
    def _write(folder, uploads):
        """Writes the uploads for one sync; keeps each file's own name (safe characters only), which the sync log shows."""
        paths = {}
        for kind, (name, data) in uploads.items():
            safe = re.sub(r"[^\w.\-]", "_", Path(name).name) or f"{kind}.csv"
            target = folder / kind
            target.mkdir()
            (target / safe).write_bytes(data)
            paths[kind] = str(target / safe)
        return paths

    def _db_is_empty(self):
        if not self.db_path.exists():
            return True
        con = store.connect(self.db_path)
        try:
            return store.is_empty(con)
        finally:
            con.close()

    def _drop_old_uploads(self):
        now = clock.monotonic()
        for waiting in (self.pending, self.pending_settings):
            for token in [t for t, p in waiting.items() if now - p["at"] > PENDING_SECONDS]:
                del waiting[token]
