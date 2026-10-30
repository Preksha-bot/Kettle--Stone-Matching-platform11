"""Present-day adapter: reads the three CSV exports (and the desk's optional reviewed.csv) into plain
records the core understands.

The files are never changed. Missing columns stop the run with a clear message.
"""
import csv
from dataclasses import dataclass
from datetime import date, datetime, time
from pathlib import Path

from kettle.core.normalise import is_same_number_marker, normalise_phone, parse_added_date

WAITLIST_COLUMNS = ["line", "added", "name", "phone", "notes"]
APPOINTMENT_COLUMNS = ["appointment_id", "date", "start", "end", "length_min", "therapist",
                       "client_id", "client_name", "booked_at", "status", "cancelled_at"]
OPENING_COLUMNS = ["opening_id", "appointment_id", "date", "start", "length_min", "therapist",
                   "kind", "cancelled_at"]
REVIEWED_COLUMNS = ["line", "decision", "other_line"]


class InputError(Exception):
    pass


@dataclass
class WaitlistLine:
    line: int
    added_raw: str
    added: date
    name: str
    phone_raw: str
    phone: str            # 10 digits, or None
    same_number: bool     # phone column says "same #"
    notes: str


@dataclass
class Booking:
    appointment_id: str
    date: date
    start: time
    end: time
    length_min: int
    therapist: str
    client_id: str
    client_name: str
    booked_at: datetime
    status: str
    cancelled_at: datetime
    rebooked_into: str


@dataclass
class Opening:
    opening_id: str
    appointment_id: str
    date: date
    start: time
    length_min: int
    therapist: str
    kind: str
    cancelled_at: datetime
    hours_notice: float

    @property
    def day(self):
        return self.date.strftime("%a")

    @property
    def is_no_show(self):
        return "no-show" in self.kind.lower() or "no show" in self.kind.lower()


@dataclass
class ReviewRow:
    row: int              # row number in the file (the header is row 1), for messages
    line: int
    decision: str         # as written; the core decides what it means
    other_line: int       # or None


def _rows(path, required, allow_empty=False):
    path = Path(path)
    if not path.exists():
        raise InputError(f"File not found: {path}")
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = [c for c in required if c not in (reader.fieldnames or [])]
        if missing:
            raise InputError(f"{path.name} is missing column(s): {', '.join(missing)}")
        rows = [{k: (v or "").strip() for k, v in row.items() if k} for row in reader]
    if not rows and not allow_empty:
        raise InputError(f"{path.name} has no rows")
    return rows


def _dt(text):
    return datetime.strptime(text, "%Y-%m-%d %H:%M") if text else None


def _t(text):
    return datetime.strptime(text, "%H:%M").time() if text else None


def _d(text):
    return datetime.strptime(text, "%Y-%m-%d").date()


def read_waitlist(path, run_date):
    lines = []
    for row in _rows(path, WAITLIST_COLUMNS):
        lines.append(WaitlistLine(
            line=int(row["line"]),
            added_raw=row["added"],
            added=parse_added_date(row["added"], run_date),
            name=row["name"],
            phone_raw=row["phone"],
            phone=normalise_phone(row["phone"]),
            same_number=is_same_number_marker(row["phone"]),
            notes=row["notes"],
        ))
    return sorted(lines, key=lambda l: l.line)


def read_appointments(path):
    out = []
    for row in _rows(path, APPOINTMENT_COLUMNS):
        out.append(Booking(
            appointment_id=row["appointment_id"],
            date=_d(row["date"]),
            start=_t(row["start"]),
            end=_t(row["end"]),
            length_min=int(row["length_min"]),
            therapist=row["therapist"],
            client_id=row["client_id"],
            client_name=row["client_name"],
            booked_at=_dt(row["booked_at"]),
            status=row["status"],
            cancelled_at=_dt(row["cancelled_at"]),
            rebooked_into=row.get("rebooked_into", ""),
        ))
    return out


def read_openings(path):
    out = []
    for row in _rows(path, OPENING_COLUMNS):
        d, start = _d(row["date"]), _t(row["start"])
        cancelled = _dt(row["cancelled_at"])
        if row.get("hours_notice"):
            notice = float(row["hours_notice"])
        else:  # derive it: time from cancellation to start
            notice = max(0.0, (datetime.combine(d, start) - cancelled).total_seconds() / 3600)
        out.append(Opening(
            opening_id=row["opening_id"],
            appointment_id=row["appointment_id"],
            date=d,
            start=start,
            length_min=int(row["length_min"]),
            therapist=row["therapist"],
            kind=row["kind"],
            cancelled_at=cancelled,
            hours_notice=notice,
        ))
    return out


def read_reviewed(path):
    """The desk's decisions file (line, decision, other_line, and any notes columns). It may be empty.
    Returns (rows, warnings): a row whose line numbers can't be read is skipped with a warning."""
    rows, warnings = [], []
    for n, row in enumerate(_rows(path, REVIEWED_COLUMNS, allow_empty=True), 2):
        if not any(row.values()):
            continue
        try:
            line = int(row["line"].lstrip("Ww"))
            other = int(row["other_line"].lstrip("Ww")) if row["other_line"] else None
        except ValueError:
            warnings.append(f"reviewed.csv row {n}: line numbers must be numbers, e.g. 39 or W39. Row skipped")
            continue
        rows.append(ReviewRow(row=n, line=line, decision=row["decision"], other_line=other))
    return rows, warnings


def check_openings_against_export(openings, bookings):
    """A8: each opening should be a late-cancel / no-show row in the booking export. Returns warnings."""
    by_id = {b.appointment_id: b for b in bookings}
    warnings = []
    for o in openings:
        b = by_id.get(o.appointment_id)
        if b is None:
            warnings.append(f"{o.opening_id}: appointment {o.appointment_id} not in the booking export")
        elif b.status.lower() not in ("late cancel", "no-show", "cancelled"):
            warnings.append(f"{o.opening_id}: export shows {o.appointment_id} as '{b.status}'")
        elif b.therapist != o.therapist or b.date != o.date or b.start != o.start:
            warnings.append(f"{o.opening_id}: therapist/date/time differ from the export")
    return warnings
