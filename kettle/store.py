"""The platform's database (one SQLite file on the desk computer): booking history, the migrated waitlist,
openings, the sync log and each run's results. Plan: platform-plan.md §4 and §5.

What is never stored: the uploaded files, the waitlist note text, and any word the parser couldn't read
(it might be a health detail). A line keeps only the fields read from it, plus a salted one-way
fingerprint so a later upload can tell whether its text changed.
"""
import hashlib
import json
import secrets
import sqlite3
from dataclasses import fields
from datetime import date, datetime, time, timedelta
from pathlib import Path

from kettle.adapters.csv_in import Booking, Opening, ReviewRow, WaitlistLine
from kettle.core.parse_notes import LineSpec
from kettle.core.people import gone_reason

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);

-- the sync log: one row per upload; file names only, never their contents
CREATE TABLE IF NOT EXISTS imports (
    id INTEGER PRIMARY KEY,
    synced_at TEXT NOT NULL,
    run_date TEXT NOT NULL,
    waitlist_file TEXT,
    appointments_file TEXT,
    openings_file TEXT,
    visits_from TEXT,          -- first and last visit date in the appointments file
    visits_to TEXT,
    summary TEXT NOT NULL      -- JSON: counts and warnings
);

-- the migrated green book: one row per notebook line, without the note text
CREATE TABLE IF NOT EXISTS waitlist_lines (
    line INTEGER PRIMARY KEY,
    added_raw TEXT NOT NULL,
    added TEXT,
    name TEXT NOT NULL,
    phone_raw TEXT NOT NULL,
    phone TEXT,
    same_number INTEGER NOT NULL,
    fingerprint TEXT NOT NULL,
    spec TEXT NOT NULL,        -- JSON: the fields read from the note
    changed_in_import INTEGER, -- the line's text changed after it was first saved: its person is held
    first_import INTEGER NOT NULL,
    last_import INTEGER NOT NULL
);

-- every booking ever synced (the history "booked since" needs)
CREATE TABLE IF NOT EXISTS bookings (
    appointment_id TEXT PRIMARY KEY,
    seq INTEGER NOT NULL,
    date TEXT NOT NULL,
    start TEXT,
    end TEXT,
    length_min INTEGER NOT NULL,
    therapist TEXT NOT NULL,
    client_id TEXT,
    client_name TEXT,
    booked_at TEXT,
    status TEXT NOT NULL,
    cancelled_at TEXT,
    rebooked_into TEXT,
    booked_via TEXT,
    confirmation TEXT,
    cancel_via TEXT,
    first_import INTEGER NOT NULL,
    last_import INTEGER NOT NULL
);

-- a booking seen again with a different status
CREATE TABLE IF NOT EXISTS booking_events (
    id INTEGER PRIMARY KEY,
    import_id INTEGER NOT NULL,
    appointment_id TEXT NOT NULL,
    old_status TEXT,
    new_status TEXT,
    cancelled_at TEXT
);

-- one row per cancelled appointment, however many files mention it
CREATE TABLE IF NOT EXISTS openings (
    appointment_id TEXT PRIMARY KEY,
    seq INTEGER NOT NULL,
    opening_id TEXT NOT NULL,
    date TEXT NOT NULL,
    start TEXT NOT NULL,
    length_min INTEGER NOT NULL,
    therapist TEXT NOT NULL,
    kind TEXT NOT NULL,
    cancelled_at TEXT,
    hours_notice REAL NOT NULL,
    heard_via TEXT,
    source TEXT,               -- 'desk' = entered in the cancellation inbox: notice is counted from now, not the cancellation
    first_import INTEGER NOT NULL,
    last_import INTEGER NOT NULL
);

-- what the desk decided on the review screen (replaces hand-editing reviewed.csv). Nothing is deleted:
-- an undone decision keeps its row with undone_at set.
CREATE TABLE IF NOT EXISTS desk_decisions (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,        -- same person / different people / ignore / start over / still wants it / take off /
                               -- keep new text / card edit / still interested / add (the last three from the board)
    line INTEGER NOT NULL,     -- the line it's about
    other_line INTEGER,        -- same person / different people: the other line
    desk_line INTEGER,         -- start over / still wants it / take off: the entry's own line number (10001 up)
    after_line INTEGER,        -- the newest book line when it was made: book lines after it are newer than the entry
    added TEXT,                -- the entry's date
    name TEXT,                 -- copied from the person, so the entry joins them
    phone TEXT,
    spec TEXT,                 -- JSON: what the person can take (start over), the same fields as waitlist_lines.spec
    checked_by TEXT NOT NULL,  -- kept for the record; never shown on a screen or in an output file
    made_at TEXT NOT NULL,
    undone_at TEXT,
    summary TEXT               -- what changed, in plain words, for the card's history (never a reason or a note)
);

-- every version of config/clinic.json saved from the settings screen, so any of them can be put back
CREATE TABLE IF NOT EXISTS settings_versions (
    id INTEGER PRIMARY KEY,
    saved_at TEXT NOT NULL,
    saved_by TEXT NOT NULL,    -- kept for the record; never shown on a screen or in an output file
    changes TEXT NOT NULL,     -- JSON: what changed, in plain words
    settings TEXT NOT NULL     -- the whole settings file as saved
);

-- every cancellation the desk entered in the inbox (plan §9.4): channel and time only, never the reason
CREATE TABLE IF NOT EXISTS cancellations (
    appointment_id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    start TEXT NOT NULL,
    therapist TEXT NOT NULL,
    length_min INTEGER NOT NULL,
    cancelled_at TEXT NOT NULL,
    heard_via TEXT NOT NULL,
    late INTEGER NOT NULL,     -- less than 24 h before the start: it became an opening
    recorded_at TEXT NOT NULL,
    recorded_by TEXT NOT NULL
);

-- the morning call list (plan §9.4): one row per tap. The last tap that isn't undone is the booking's state.
CREATE TABLE IF NOT EXISTS calls (
    id INTEGER PRIMARY KEY,
    appointment_id TEXT NOT NULL,
    outcome TEXT NOT NULL,     -- confirmed / voicemail / cancelled
    at TEXT NOT NULL,
    by TEXT NOT NULL,
    undone_at TEXT
);

-- the desk's work on each opening (plan §10.1). No row = new: nothing done yet.
CREATE TABLE IF NOT EXISTS opening_desk (
    appointment_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,      -- held (the time is blocked in Kneadly) / filled / taken / released
    hold_placed_at TEXT,
    hold_placed_by TEXT,
    closed_at TEXT,            -- filled, taken or released
    closed_by TEXT,
    closed_how TEXT            -- taken: a client called in / booked online / another way; released: nobody left
);

-- one offer to one person for one opening
CREATE TABLE IF NOT EXISTS offers (
    id INTEGER PRIMARY KEY,
    appointment_id TEXT NOT NULL,
    line INTEGER NOT NULL,     -- the person's newest line when offered
    person TEXT NOT NULL,
    phone TEXT,
    offered_at TEXT NOT NULL,
    offered_by TEXT NOT NULL,  -- shown on the openings screen, so two people at the desk can't both call
    outcome TEXT,              -- NULL = live; yes / no / no answer / withdrawn
    outcome_at TEXT,
    outcome_by TEXT,
    reason TEXT                -- why they said no, from a short list (the time, the day, ...); never free text
);
-- never two live offers for one opening: the "two people in the waiting room" rule, kept by the database itself
CREATE UNIQUE INDEX IF NOT EXISTS one_live_offer ON offers (appointment_id) WHERE outcome IS NULL;

-- a refill: who said yes, and how it goes into Kneadly (plan §10.3)
CREATE TABLE IF NOT EXISTS rebookings (
    id INTEGER PRIMARY KEY,
    appointment_id TEXT NOT NULL,  -- the cancelled appointment it refills ("rebooked into")
    offer_id INTEGER NOT NULL,
    label TEXT NOT NULL,           -- the opening, for screens and reasons: "O05 Wed Sep 23 11:45"
    line INTEGER NOT NULL,
    person TEXT NOT NULL,
    phone TEXT,
    length_min INTEGER NOT NULL,
    how TEXT NOT NULL,             -- booked now / book at check-in / new client
    in_kneadly INTEGER NOT NULL,
    kneadly_id TEXT,
    made_at TEXT NOT NULL,
    made_by TEXT NOT NULL,
    in_kneadly_at TEXT,
    undone_at TEXT
);

-- the latest run's view of each waitlist person (rebuilt on every run)
CREATE TABLE IF NOT EXISTS people (first_line INTEGER PRIMARY KEY, record TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS match_runs (
    id INTEGER PRIMARY KEY,
    import_id INTEGER NOT NULL,
    run_date TEXT NOT NULL,
    order_mode TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS matches (
    run_id INTEGER NOT NULL,
    appointment_id TEXT NOT NULL,
    opening_id TEXT NOT NULL,
    rank INTEGER NOT NULL,     -- 1-3 = names shown, 0 = nobody, -1 to -3 = closest not offered (reason in can_take)
    line INTEGER,
    person TEXT,
    can_take TEXT,
    flags TEXT
);
"""

# Stands in for each word the parser couldn't read: the person is still held, and the word itself (which
# might be a health detail) is never kept. The desk finds it on that line in the book.
UNREAD_WORD = "one word (see the book)"
# what a "gone" note becomes, so only the reason is kept and not the rest of the note
GONE_TOKENS = {"number not in service": "not in service", "moved away": "moved",
               "going somewhere else now": "going to", "asked to come off the list": "take off"}
SPEC_NOT_KEPT = {"had_health_detail"}
ANY_THERAPIST = "any"
CHANGED_REASON = "changed since it was first saved"
# Entries the desk makes on the review screen get line numbers from here up, so they never meet a book line.
DESK_LINE_START = 10001
IDENTITY = ("same person", "different people", "ignore")
ENTRY = ("start over", "still wants it", "take off", "card edit", "still interested", "add")
ADD = "add"  # a new person added on the board: an entry of their own, linked to nobody
KEEP_NEW_TEXT = "keep new text"


def connect(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    if "source" not in {r[1] for r in con.execute("PRAGMA table_info(openings)")}:  # databases made before the inbox
        con.execute("ALTER TABLE openings ADD COLUMN source TEXT")
    if "summary" not in {r[1] for r in con.execute("PRAGMA table_info(desk_decisions)")}:  # ... before the board
        con.execute("ALTER TABLE desk_decisions ADD COLUMN summary TEXT")
    if "reason" not in {r[1] for r in con.execute("PRAGMA table_info(offers)")}:  # ... before decline reasons
        con.execute("ALTER TABLE offers ADD COLUMN reason TEXT")
    if get_meta(con, "salt") is None:
        set_meta(con, "salt", secrets.token_hex(16))
        con.commit()
    return con


def get_meta(con, key, default=None):
    row = con.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_meta(con, key, value):
    con.execute("INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, str(value)))


def is_empty(con):
    return con.execute("SELECT COUNT(*) FROM waitlist_lines").fetchone()[0] == 0


def is_paused(con):
    """The owner's switch: while paused, nothing is synced and no decision is saved (plan §12)."""
    return get_meta(con, "paused") == "yes"


def set_paused(con, paused, by, when):
    set_meta(con, "paused", "yes" if paused else "no")
    set_meta(con, "paused_changed", f"{_iso(when)} by {by.strip()}")


# ---------- values <-> text ----------

def _iso(x):
    if x is None:
        return None
    if isinstance(x, datetime):
        return x.strftime("%Y-%m-%d %H:%M")
    if isinstance(x, time):
        return x.strftime("%H:%M")
    return x.isoformat()


def _dt(text):
    return datetime.strptime(text, "%Y-%m-%d %H:%M") if text else None


def _t(text):
    return datetime.strptime(text, "%H:%M").time() if text else None


def _d(text):
    return date.fromisoformat(text) if text else None


def _encode(value):
    if isinstance(value, set):
        return {"set": sorted(value, key=str)}
    if isinstance(value, time):
        return {"time": value.isoformat()}
    if isinstance(value, date):
        return {"date": value.isoformat()}
    if isinstance(value, list):
        return [_encode(v) for v in value]
    return value


def _decode(value):
    if isinstance(value, dict):
        if "set" in value:
            return set(value["set"])
        if "time" in value:
            return time.fromisoformat(value["time"])
        if "date" in value:
            return date.fromisoformat(value["date"])
    if isinstance(value, list):
        return [_decode(v) for v in value]
    return value


def spec_to_json(spec, everyone=None):
    """The fields read from a note, minus anything that could hold the note's own words. `everyone`: all the
    therapists in the settings when the note was read; a note that said "any" is kept as "any", so it still
    means every therapist after the settings change."""
    out = {}
    for f in fields(LineSpec):
        if f.name in SPEC_NOT_KEPT:
            continue
        value = getattr(spec, f.name)
        if f.name == "unparsed":
            value = [UNREAD_WORD] * len(value)
        elif f.name == "gone" and value:
            value = GONE_TOKENS[gone_reason(value)]
        elif f.name == "therapists" and everyone is not None and value == set(everyone):
            value = ANY_THERAPIST
        out[f.name] = _encode(value)
    return json.dumps(out, sort_keys=True, ensure_ascii=False)


def spec_from_json(text, everyone=None):
    """`everyone`: the therapists in the settings now, which is what "any" means."""
    spec = LineSpec(**{k: _decode(v) for k, v in json.loads(text).items()})
    if spec.therapists == ANY_THERAPIST:
        spec.therapists = set(everyone or ())
    return spec


def fingerprint(con, line):
    """Salted one-way hash of everything written on the line, so a changed line can be spotted without
    keeping its text."""
    raw = "\x1f".join([str(line.line), line.added_raw, line.name, line.phone_raw, line.notes])
    return hashlib.sha256((get_meta(con, "salt") + raw).encode("utf-8")).hexdigest()


# ---------- loading what the core needs ----------

def load_lines(con, everyone=None):
    """WaitlistLine records (without notes) and their specs, keyed by line number, as the core expects.
    `everyone`: the therapists in the settings now (what a note that said "any" means).
    The desk's entries come right after the book line that was newest when each was made, so a later book
    line is still newer than the entry, as a newer line in the book is today."""
    ordered = []
    for r in con.execute("SELECT * FROM waitlist_lines ORDER BY line"):
        line = WaitlistLine(line=r["line"], added_raw=r["added_raw"], added=_d(r["added"]), name=r["name"],
                            phone_raw=r["phone_raw"], phone=r["phone"], same_number=bool(r["same_number"]), notes="")
        spec = spec_from_json(r["spec"], everyone)
        if r["changed_in_import"] is not None:
            spec.needs_check.append(CHANGED_REASON)
        ordered.append(((r["line"], 0, 0), line, spec))
    for d in active_decisions(con):
        if d["desk_line"] is None:
            continue
        line = WaitlistLine(line=d["desk_line"], added_raw=d["added"], added=_d(d["added"]), name=d["name"],
                            phone_raw=d["phone"] or "", phone=d["phone"], same_number=False, notes="")
        ordered.append(((d["after_line"], 1, d["id"]), line, spec_from_json(d["spec"], everyone)))
    ordered.sort(key=lambda x: x[0])
    return [line for _, line, _ in ordered], {line.line: spec for _, line, spec in ordered}


def load_bookings(con):
    return [Booking(appointment_id=r["appointment_id"], date=_d(r["date"]), start=_t(r["start"]), end=_t(r["end"]),
                    length_min=r["length_min"], therapist=r["therapist"], client_id=r["client_id"],
                    client_name=r["client_name"], booked_at=_dt(r["booked_at"]), status=r["status"],
                    cancelled_at=_dt(r["cancelled_at"]), rebooked_into=r["rebooked_into"])
            for r in con.execute("SELECT * FROM bookings ORDER BY seq")]


def load_openings(con, appointment_ids=None, now=None):
    """All openings in the order first seen, or only `appointment_ids` in the order given. An opening entered in
    the inbox counts its notice from `now` (when an offer can go out, plan B1); one from a file keeps the notice
    from the cancellation, as Tanya's answers do."""
    rows = {r["appointment_id"]: r for r in con.execute("SELECT * FROM openings ORDER BY seq")}
    ids = list(rows) if appointment_ids is None else appointment_ids
    out = []
    for a in ids:
        r = rows[a]
        notice = r["hours_notice"]
        if r["source"] == "desk" and now is not None:
            notice = max(0.0, round((datetime.combine(_d(r["date"]), _t(r["start"])) - now).total_seconds() / 3600, 1))
        out.append(Opening(opening_id=r["opening_id"], appointment_id=a, date=_d(r["date"]), start=_t(r["start"]),
                           length_min=r["length_min"], therapist=r["therapist"], kind=r["kind"],
                           cancelled_at=_dt(r["cancelled_at"]), hours_notice=notice))
    return out


def save_live_notice(con, openings):
    """Keeps the notice each inbox opening was matched with, so the screens show what the names were found for."""
    con.executemany("UPDATE openings SET hours_notice = ? WHERE appointment_id = ? AND source = 'desk'",
                    [(o.hours_notice, o.appointment_id) for o in openings])


def visit_ranges(con):
    """(first, last) visit date covered by each appointments upload."""
    return [(_d(r["visits_from"]), _d(r["visits_to"]))
            for r in con.execute("SELECT visits_from, visits_to FROM imports WHERE visits_from IS NOT NULL")]


def open_weekdays(con):
    """Weekdays the clinic has had any booking on (so a Sunday between two files isn't called a gap)."""
    return {_d(r[0]).weekday() for r in con.execute("SELECT DISTINCT date FROM bookings")}


# ---------- saving ----------

def new_import(con, synced_at, run_date, files):
    cur = con.execute("INSERT INTO imports (synced_at, run_date, waitlist_file, appointments_file, openings_file, "
                      "summary) VALUES (?, ?, ?, ?, ?, '{}')",
                      (_iso(synced_at), run_date.isoformat(), files.get("waitlist"), files.get("appointments"),
                       files.get("openings")))
    return cur.lastrowid


def finish_import(con, import_id, summary, visits=None):
    con.execute("UPDATE imports SET summary = ?, visits_from = ?, visits_to = ? WHERE id = ?",
                (json.dumps(summary, ensure_ascii=False), _iso(visits[0]) if visits else None,
                 _iso(visits[1]) if visits else None, import_id))


def save_lines(con, import_id, lines, specs, everyone=None):
    """Migrates the book: new line numbers are added; a known line whose text changed is updated and its
    person held. Returns (new, changed, unchanged, missing) line numbers."""
    known = {r["line"]: r for r in con.execute("SELECT line, fingerprint FROM waitlist_lines")}
    new, changed, unchanged = [], [], []
    for l in lines:
        fp = fingerprint(con, l)
        values = (l.added_raw, _iso(l.added), l.name, l.phone_raw, l.phone, int(l.same_number), fp,
                  spec_to_json(specs[l.line], everyone))
        if l.line not in known:
            con.execute("INSERT INTO waitlist_lines (added_raw, added, name, phone_raw, phone, same_number, "
                        "fingerprint, spec, line, first_import, last_import) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        values + (l.line, import_id, import_id))
            new.append(l.line)
        elif known[l.line]["fingerprint"] != fp:
            con.execute("UPDATE waitlist_lines SET added_raw = ?, added = ?, name = ?, phone_raw = ?, phone = ?, "
                        "same_number = ?, fingerprint = ?, spec = ?, changed_in_import = ?, last_import = ? "
                        "WHERE line = ?", values + (import_id, import_id, l.line))
            changed.append(l.line)
        else:
            # same text: refresh the fields (dates in notes are read against the newest run date)
            con.execute("UPDATE waitlist_lines SET added = ?, spec = ?, last_import = ? WHERE line = ?",
                        (_iso(l.added), values[7], import_id, l.line))
            unchanged.append(l.line)
    missing = sorted(set(known) - {l.line for l in lines})
    return new, changed, unchanged, missing


def save_bookings(con, import_id, bookings, extra):
    """Adds bookings to the history; a booking seen again is updated, and a status change is logged.
    `extra`: appointment_id -> {booked_via, confirmation, cancel_via} when the file has those columns.
    Returns (new, updated, status_changes) counts."""
    known = {r["appointment_id"]: r for r in con.execute("SELECT appointment_id, status, cancelled_at FROM bookings")}
    seq = con.execute("SELECT COALESCE(MAX(seq), 0) FROM bookings").fetchone()[0]
    new = updated = changes = 0
    for b in bookings:
        x = extra.get(b.appointment_id, {})
        values = (_iso(b.date), _iso(b.start), _iso(b.end), b.length_min, b.therapist, b.client_id, b.client_name,
                  _iso(b.booked_at), b.status, _iso(b.cancelled_at), b.rebooked_into,
                  x.get("booked_via"), x.get("confirmation"), x.get("cancel_via"))
        old = known.get(b.appointment_id)
        if old is None:
            seq += 1
            con.execute("INSERT INTO bookings (date, start, end, length_min, therapist, client_id, client_name, "
                        "booked_at, status, cancelled_at, rebooked_into, booked_via, confirmation, cancel_via, "
                        "appointment_id, seq, first_import, last_import) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        values + (b.appointment_id, seq, import_id, import_id))
            known[b.appointment_id] = {"status": b.status, "cancelled_at": _iso(b.cancelled_at)}
            new += 1
            continue
        if old["status"] != b.status:
            con.execute("INSERT INTO booking_events (import_id, appointment_id, old_status, new_status, cancelled_at) "
                        "VALUES (?, ?, ?, ?, ?)", (import_id, b.appointment_id, old["status"], b.status,
                                                   _iso(b.cancelled_at)))
            changes += 1
        con.execute("UPDATE bookings SET date = ?, start = ?, end = ?, length_min = ?, therapist = ?, client_id = ?, "
                    "client_name = ?, booked_at = ?, status = ?, cancelled_at = ?, rebooked_into = ?, "
                    "booked_via = COALESCE(?, booked_via), confirmation = COALESCE(?, confirmation), "
                    "cancel_via = COALESCE(?, cancel_via), last_import = ? WHERE appointment_id = ?",
                    values + (import_id, b.appointment_id))
        updated += 1
    return new, updated, changes


def save_openings(con, import_id, openings, heard_via):
    """One row per appointment ID: the same cancellation in two files is one opening. Returns the new count."""
    known = {r[0] for r in con.execute("SELECT appointment_id FROM openings")}
    seq = con.execute("SELECT COALESCE(MAX(seq), 0) FROM openings").fetchone()[0]
    new = 0
    for o in openings:
        values = (o.opening_id, _iso(o.date), _iso(o.start), o.length_min, o.therapist, o.kind,
                  _iso(o.cancelled_at), o.hours_notice, heard_via.get(o.appointment_id))
        if o.appointment_id in known:
            con.execute("UPDATE openings SET opening_id = ?, date = ?, start = ?, length_min = ?, therapist = ?, "
                        "kind = ?, cancelled_at = ?, hours_notice = ?, heard_via = COALESCE(?, heard_via), "
                        "last_import = ? WHERE appointment_id = ?", values + (import_id, o.appointment_id))
        else:
            seq += 1
            con.execute("INSERT INTO openings (opening_id, date, start, length_min, therapist, kind, cancelled_at, "
                        "hours_notice, heard_via, appointment_id, seq, first_import, last_import) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        values + (o.appointment_id, seq, import_id, import_id))
            known.add(o.appointment_id)
            new += 1
    return new


def save_run(con, import_id, run_date, order, people_records, results):
    """Keeps this run's people (rebuilt each time) and the names shown per opening (kept for every run)."""
    con.execute("DELETE FROM people")
    con.executemany("INSERT INTO people (first_line, record) VALUES (?, ?)",
                    [(rec["lines"][0], json.dumps(rec, ensure_ascii=False)) for rec in people_records])
    run_id = con.execute("INSERT INTO match_runs (import_id, run_date, order_mode) VALUES (?, ?, ?)",
                         (import_id, run_date.isoformat(), order)).lastrowid
    rows = []
    for r in results:
        o = r.opening
        if not r.picks:
            rows.append((run_id, o.appointment_id, o.opening_id, 0, None, None, r.note, ""))
        for i, p in enumerate(r.picks, 1):
            rows.append((run_id, o.appointment_id, o.opening_id, i, p.person.active_line, p.person.name,
                         p.summary, "; ".join(p.tags)))
        for i, (person, why) in enumerate(r.closest, 1):
            rows.append((run_id, o.appointment_id, o.opening_id, -i, person.active_line, person.name, why, ""))
    con.executemany("INSERT INTO matches VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
    return run_id


def add_run_warnings(con, import_id, warnings):
    """Every warning of the run (the sync's own and the matcher's), kept with the sync for the screens."""
    summary = json.loads(con.execute("SELECT summary FROM imports WHERE id = ?", (import_id,)).fetchone()[0])
    summary["run_warnings"] = list(warnings)
    con.execute("UPDATE imports SET summary = ? WHERE id = ?", (json.dumps(summary, ensure_ascii=False), import_id))


def import_history(con):
    return [dict(r) for r in con.execute("SELECT * FROM imports ORDER BY id")]


# ---------- the cancellation inbox ----------

LATE_HOURS = 24  # the clinic's policy: under 24 h is a late cancel
CHANNELS = ("voicemail (overnight)", "phone", "text reply", "morning call", "online (Kneadly)", "other")


def bookings_on(con, day):
    """The day's bookings that haven't been cancelled or missed: the ones a cancellation can be entered for."""
    return [dict(r) for r in con.execute(
        "SELECT * FROM bookings WHERE date = ? AND lower(status) NOT IN ('cancelled', 'late cancel', 'no-show') "
        "ORDER BY start, therapist", (day.isoformat(),))]


def booking(con, appointment_id):
    r = con.execute("SELECT * FROM bookings WHERE appointment_id = ?", (appointment_id,)).fetchone()
    return dict(r) if r else None


def heard_already(con, appointment_id):
    """How this cancellation is already known (an opening or an inbox entry), or None."""
    r = con.execute("SELECT opening_id, heard_via, cancelled_at FROM openings WHERE appointment_id = ?",
                    (appointment_id,)).fetchone()
    if r:
        return dict(r)
    r = con.execute("SELECT heard_via, cancelled_at FROM cancellations WHERE appointment_id = ?",
                    (appointment_id,)).fetchone()
    return {"opening_id": None, **dict(r)} if r else None


def record_cancellation(con, slot, cancelled_at, heard_via, by, when):
    """One cancellation from the inbox. `slot`: appointment_id, date, start (date and time objects), therapist,
    length_min. Under 24 h before the start it becomes an opening (ID = the appointment ID, so hearing it again on
    another channel changes nothing); otherwise it's only recorded. Returns the new opening's ID, or None."""
    start = datetime.combine(slot["date"], slot["start"])
    late = start - cancelled_at < timedelta(hours=LATE_HOURS)
    aid = slot["appointment_id"]
    con.execute("INSERT INTO cancellations (appointment_id, date, start, therapist, length_min, cancelled_at, heard_via, "
                "late, recorded_at, recorded_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (aid, _iso(slot["date"]), _iso(slot["start"]), slot["therapist"], slot["length_min"], _iso(cancelled_at),
                 heard_via, int(late), _iso(when), by))
    old = con.execute("SELECT status FROM bookings WHERE appointment_id = ?", (aid,)).fetchone()
    if old:  # keeps "booked since" right: a cancelled booking doesn't count as booked
        status = "Late cancel" if late else "Cancelled"
        con.execute("UPDATE bookings SET status = ?, cancelled_at = ?, cancel_via = ? WHERE appointment_id = ?",
                    (status, _iso(cancelled_at), heard_via, aid))
        con.execute("INSERT INTO booking_events (import_id, appointment_id, old_status, new_status, cancelled_at) "
                    "VALUES (0, ?, ?, ?, ?)", (aid, old[0], status, _iso(cancelled_at)))
    if not late:
        return None
    n = con.execute("SELECT COUNT(*) FROM openings WHERE source = 'desk'").fetchone()[0]
    opening_id = f"D{n + 1:02d}"
    seq = con.execute("SELECT COALESCE(MAX(seq), 0) FROM openings").fetchone()[0] + 1
    con.execute("INSERT INTO openings (appointment_id, seq, opening_id, date, start, length_min, therapist, kind, "
                "cancelled_at, hours_notice, heard_via, source, first_import, last_import) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 'late cancel', ?, ?, ?, 'desk', 0, 0)",
                (aid, seq, opening_id, _iso(slot["date"]), _iso(slot["start"]), slot["length_min"], slot["therapist"],
                 _iso(cancelled_at), round(max(0.0, (start - cancelled_at).total_seconds() / 3600), 1), heard_via))
    return opening_id


def normal_cancellations(con):
    return [dict(r) for r in con.execute("SELECT * FROM cancellations WHERE late = 0")]


# ---------- the morning call list ----------

CALL_OUTCOMES = ("confirmed", "voicemail", "cancelled")


def _needs_a_call(confirmation):
    """Kneadly's confirmation value: text C and phone are confirmed; n/a (booked the same day) needs no call."""
    c = (confirmation or "").strip().lower()
    return not (c.startswith("text") or c.startswith("phone") or c.startswith("n/a"))


def call_list(con, days, cutoff=None):
    """The bookings on `days` to call: not confirmed in the last upload, not cancelled or missed, plus every booking
    the desk has already tapped. Bookings starting before `cutoff` (now, on today's list) are left out unless the
    desk cancelled them. Each row carries its calls (oldest first) and its state: to call / voicemail / confirmed /
    cancelled."""
    marks = ",".join("?" * len(days))
    calls = {}
    for r in con.execute(f"SELECT * FROM calls WHERE undone_at IS NULL AND appointment_id IN "
                         f"(SELECT appointment_id FROM bookings WHERE date IN ({marks})) ORDER BY id",
                         [d.isoformat() for d in days]):
        calls.setdefault(r["appointment_id"], []).append(dict(r))
    out = []
    for b in con.execute(f"SELECT * FROM bookings WHERE date IN ({marks}) ORDER BY date, start, therapist",
                         [d.isoformat() for d in days]):
        b, made = dict(b), calls.get(b["appointment_id"], [])
        state = made[-1]["outcome"] if made else "to call"
        if not made and (b["status"].lower() in ("cancelled", "late cancel", "no-show")
                         or not _needs_a_call(b["confirmation"])):
            continue
        starts = datetime.combine(_d(b["date"]), _t(b["start"]))
        if cutoff and starts < cutoff and state != "cancelled":
            continue
        out.append({**b, "calls": made, "state": state})
    return out


def add_call(con, appointment_id, outcome, by, when):
    return con.execute("INSERT INTO calls (appointment_id, outcome, at, by) VALUES (?, ?, ?, ?)",
                       (appointment_id, outcome, _iso(when), by)).lastrowid


def undo_last_call(con, appointment_id, when):
    """Undoes the booking's last tap, unless it was a cancellation (that one made an opening: release it there)."""
    r = con.execute("SELECT id, outcome FROM calls WHERE appointment_id = ? AND undone_at IS NULL ORDER BY id DESC "
                    "LIMIT 1", (appointment_id,)).fetchone()
    if r is None or r["outcome"] == "cancelled":
        return False
    con.execute("UPDATE calls SET undone_at = ? WHERE id = ?", (_iso(when), r["id"]))
    return True


# ---------- offers, holds and refills ----------

BOOKED_HOW = ("booked now", "book at check-in", "new client")
TAKEN_HOW = ("a client called in", "booked online", "another way")


class LiveOfferError(Exception):
    """An offer is already out for this opening: only one at a time."""


def desk_state(con):
    """Per opening (appointment ID): its desk status, hold, offers (oldest first), the live offer and the refill."""
    state = {}
    for r in con.execute("SELECT * FROM opening_desk"):
        state[r["appointment_id"]] = {**dict(r), "offers": [], "live": None, "rebooking": None}
    for r in con.execute("SELECT * FROM offers ORDER BY id"):
        s = state.setdefault(r["appointment_id"], {"status": "new", "offers": [], "live": None, "rebooking": None})
        s["offers"].append(dict(r))
        if r["outcome"] is None:
            s["live"] = dict(r)
    for r in con.execute("SELECT * FROM rebookings WHERE undone_at IS NULL"):
        if r["appointment_id"] in state:
            state[r["appointment_id"]]["rebooking"] = dict(r)
    return state


def status_of(con, appointment_id):
    r = con.execute("SELECT status FROM opening_desk WHERE appointment_id = ?", (appointment_id,)).fetchone()
    return r[0] if r else "new"


def place_hold(con, appointment_id, by, when):
    con.execute("INSERT INTO opening_desk (appointment_id, status, hold_placed_at, hold_placed_by) VALUES (?, 'held', ?, ?)"
                " ON CONFLICT(appointment_id) DO UPDATE SET status = 'held', hold_placed_at = excluded.hold_placed_at,"
                " hold_placed_by = excluded.hold_placed_by, closed_at = NULL, closed_by = NULL, closed_how = NULL",
                (appointment_id, _iso(when), by))


def close_opening(con, appointment_id, status, by, when, how=None):
    """filled / taken / released. A live offer is withdrawn: nobody is left waiting on an answer."""
    con.execute("INSERT INTO opening_desk (appointment_id, status, closed_at, closed_by, closed_how) VALUES (?, ?, ?, ?, ?)"
                " ON CONFLICT(appointment_id) DO UPDATE SET status = excluded.status, closed_at = excluded.closed_at,"
                " closed_by = excluded.closed_by, closed_how = excluded.closed_how",
                (appointment_id, status, _iso(when), by, how))
    if status != "filled":
        con.execute("UPDATE offers SET outcome = 'withdrawn', outcome_at = ?, outcome_by = ? "
                    "WHERE appointment_id = ? AND outcome IS NULL", (_iso(when), by, appointment_id))


def reopen(con, appointment_id):
    """Back to new (a slot marked taken or released by mistake). The hold has to be placed again."""
    con.execute("DELETE FROM opening_desk WHERE appointment_id = ? AND status IN ('taken', 'released')",
                (appointment_id,))


def start_offer(con, appointment_id, line, person, phone, by, when):
    try:
        return con.execute("INSERT INTO offers (appointment_id, line, person, phone, offered_at, offered_by) "
                           "VALUES (?, ?, ?, ?, ?, ?)",
                           (appointment_id, line, person, phone, _iso(when), by)).lastrowid
    except sqlite3.IntegrityError:
        raise LiveOfferError("An offer is already out for this opening: wait for that answer first.") from None


def get_offer(con, offer_id):
    r = con.execute("SELECT * FROM offers WHERE id = ?", (offer_id,)).fetchone()
    return dict(r) if r else None


def answer_offer(con, offer_id, outcome, by, when, reason=None):
    con.execute("UPDATE offers SET outcome = ?, outcome_at = ?, outcome_by = ?, reason = ? WHERE id = ? AND outcome IS NULL",
                (outcome, _iso(when), by, reason, offer_id))


def add_rebooking(con, offer, label, length_min, how, kneadly_id, by, when):
    """A yes: the refill, the offer closed as yes, the opening filled."""
    answer_offer(con, offer["id"], "yes", by, when)
    rid = con.execute("INSERT INTO rebookings (appointment_id, offer_id, label, line, person, phone, length_min, how, "
                      "in_kneadly, kneadly_id, made_at, made_by, in_kneadly_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                      (offer["appointment_id"], offer["id"], label, offer["line"], offer["person"], offer["phone"],
                       length_min, how, int(how == "booked now"), kneadly_id or None, _iso(when), by,
                       _iso(when) if how == "booked now" else None)).lastrowid
    close_opening(con, offer["appointment_id"], "filled", by, when)
    return rid


def undo_rebooking(con, rebooking_id, when):
    """A yes saved by mistake: the refill is undone, the offer is live again, the opening held again."""
    r = con.execute("SELECT * FROM rebookings WHERE id = ? AND undone_at IS NULL", (rebooking_id,)).fetchone()
    if r is None:
        return False
    con.execute("UPDATE rebookings SET undone_at = ? WHERE id = ?", (_iso(when), rebooking_id))
    con.execute("UPDATE offers SET outcome = NULL, outcome_at = NULL, outcome_by = NULL WHERE id = ?", (r["offer_id"],))
    con.execute("UPDATE opening_desk SET status = 'held', closed_at = NULL, closed_by = NULL, closed_how = NULL "
                "WHERE appointment_id = ?", (r["appointment_id"],))
    return True


def mark_in_kneadly(con, rebooking_id, kneadly_id, when):
    con.execute("UPDATE rebookings SET in_kneadly = 1, kneadly_id = COALESCE(?, kneadly_id), in_kneadly_at = ? "
                "WHERE id = ? AND undone_at IS NULL", (kneadly_id or None, _iso(when), rebooking_id))


def declined_lines(con):
    """Who said no (or didn't answer) to each opening: appointment ID -> their lines. Never offered it again."""
    out = {}
    for r in con.execute("SELECT appointment_id, line FROM offers WHERE outcome IN ('no', 'no answer')"):
        out.setdefault(r[0], set()).add(r[1])
    return out


def active_rebookings(con):
    return [dict(r) for r in con.execute("SELECT * FROM rebookings WHERE undone_at IS NULL ORDER BY id")]


# ---------- settings versions ----------

def save_settings_version(con, settings, saved_by, saved_at, changes):
    return con.execute("INSERT INTO settings_versions (saved_at, saved_by, changes, settings) VALUES (?, ?, ?, ?)",
                       (_iso(saved_at), saved_by.strip(), json.dumps(changes, ensure_ascii=False),
                        json.dumps(settings, ensure_ascii=False))).lastrowid


def settings_versions(con, limit=20):
    return [{**dict(r), "changes": json.loads(r["changes"]), "settings": json.loads(r["settings"])}
            for r in con.execute("SELECT * FROM settings_versions ORDER BY id DESC LIMIT ?", (limit,))]


def settings_version(con, version_id):
    r = con.execute("SELECT settings FROM settings_versions WHERE id = ?", (version_id,)).fetchone()
    return json.loads(r[0]) if r else None


# ---------- the desk's decisions ----------

def active_decisions(con):
    return [dict(r) for r in con.execute("SELECT * FROM desk_decisions WHERE undone_at IS NULL ORDER BY id")]


def decisions_for(con, lines):
    """Every decision about a person (any of their lines, book or desk), newest first: the card's history."""
    lines = set(lines)
    return [dict(r) for r in con.execute("SELECT * FROM desk_decisions ORDER BY id DESC")
            if r["line"] in lines or r["desk_line"] in lines or r["other_line"] in lines]


def board_only(con):
    """Mode B (plan §6.3): the book is retired and the board is the waitlist; book uploads are refused."""
    return get_meta(con, "board_only") == "yes"


def recent_decisions(con, limit=20):
    return [dict(r) for r in con.execute("SELECT * FROM desk_decisions ORDER BY id DESC LIMIT ?", (limit,))]


def line_numbers(con):
    """Every line a decision may name: the book's and the desk's own entries."""
    book = {r[0] for r in con.execute("SELECT line FROM waitlist_lines")}
    return book | {d["desk_line"] for d in active_decisions(con) if d["desk_line"]}


def add_decision(con, kind, line, checked_by, made_at, other_line=None, entry=None, everyone=None, summary=None):
    """Saves one decision. `entry` (for start over / still wants it / take off): {"added", "name", "phone",
    "spec"}; the entry is linked to `line` (the person's first line) so it joins that person.
    Returns the decision's id."""
    row = {"kind": kind, "line": line, "other_line": other_line, "checked_by": checked_by.strip(),
           "made_at": _iso(made_at), "summary": summary}
    if entry:
        row.update(added=_iso(entry["added"]), name=entry["name"], phone=entry["phone"],
                   spec=spec_to_json(entry["spec"], everyone),
                   after_line=con.execute("SELECT COALESCE(MAX(line), 0) FROM waitlist_lines").fetchone()[0])
    if kind == KEEP_NEW_TEXT:
        changed = con.execute("SELECT changed_in_import FROM waitlist_lines WHERE line = ?", (line,)).fetchone()
        row["spec"] = json.dumps({"changed_in_import": changed[0] if changed else None})
        con.execute("UPDATE waitlist_lines SET changed_in_import = NULL WHERE line = ?", (line,))
    columns = ", ".join(row)
    decision_id = con.execute(f"INSERT INTO desk_decisions ({columns}) VALUES ({', '.join('?' * len(row))})",
                              tuple(row.values())).lastrowid
    if entry:
        con.execute("UPDATE desk_decisions SET desk_line = ? WHERE id = ?", (DESK_LINE_START - 1 + decision_id, decision_id))
    return decision_id


def undo_decision(con, decision_id, when):
    """Undoes a decision (its row stays, marked undone). Returns False if there was nothing to undo."""
    d = con.execute("SELECT * FROM desk_decisions WHERE id = ? AND undone_at IS NULL", (decision_id,)).fetchone()
    if d is None:
        return False
    con.execute("UPDATE desk_decisions SET undone_at = ? WHERE id = ?", (_iso(when), decision_id))
    if d["kind"] == KEEP_NEW_TEXT:
        con.execute("UPDATE waitlist_lines SET changed_in_import = ? WHERE line = ?",
                    (json.loads(d["spec"])["changed_in_import"], d["line"]))
    return True


def decision_rows(con):
    """The decisions the core's reviewed.csv logic understands: identity decisions, plus a "same person" link
    from each desk entry to the person it was made for."""
    rows = []
    for d in active_decisions(con):
        if d["kind"] in IDENTITY:
            rows.append(ReviewRow(row=d["id"], line=d["line"], decision=d["kind"], other_line=d["other_line"]))
        elif d["desk_line"] and d["kind"] != ADD:
            rows.append(ReviewRow(row=d["id"], line=d["desk_line"], decision="same person", other_line=d["line"]))
    return rows


def latest_run(con):
    """The newest run: its sync, openings in the order matched, and the rows per opening; None if none yet."""
    run = con.execute("SELECT * FROM match_runs ORDER BY id DESC LIMIT 1").fetchone()
    if run is None:
        return None
    sync_row = con.execute("SELECT * FROM imports WHERE id = ?", (run["import_id"],)).fetchone()
    rows = con.execute("SELECT * FROM matches WHERE run_id = ? ORDER BY rowid", (run["id"],)).fetchall()
    order = list(dict.fromkeys(r["appointment_id"] for r in rows))
    openings = {r["appointment_id"]: dict(r) for r in con.execute("SELECT * FROM openings")}
    people = [json.loads(r["record"]) for r in con.execute("SELECT record FROM people ORDER BY first_line")]
    return {"run": dict(run), "sync": dict(sync_row), "summary": json.loads(sync_row["summary"]),
            "openings": [openings[a] for a in order],
            "rows": {a: [dict(r) for r in rows if r["appointment_id"] == a] for a in order},
            "people": people}
