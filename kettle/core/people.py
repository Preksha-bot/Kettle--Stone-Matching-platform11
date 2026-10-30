"""Builds one record per waitlist person: groups the notebook lines, merges them, decides who is out of date."""
from dataclasses import dataclass, field
from datetime import date, time

from kettle.core.normalise import fullest_name, names_compatible, names_match_strictly, name_parts
from kettle.core.parse_notes import LineSpec

ACTIVE, STALE, REVIEW = "active", "stale", "review"
NOT_A_REAL_BOOKING = {"cancelled", "late cancel"}


@dataclass
class Person:
    lines: list                      # WaitlistLine, oldest first
    specs: list                      # LineSpec per line
    name: str = ""
    phone: str = None
    # merged needs
    therapists: set = None           # None = any
    excluded: set = field(default_factory=set)
    female_only: bool = False
    prenatal: bool = False
    needs: set = field(default_factory=set)   # therapist tags the routing rules require; never the reason
    pref: set = field(default_factory=set)
    lengths: set = None
    days: set = None
    days_excluded: set = field(default_factory=set)
    earliest_start: time = None
    start_before: time = None
    latest_end: time = None
    notice: float = None
    day_before: bool = False
    available_from: date = None
    available_until: date = None
    contact: str = None
    new_client: bool = False
    regular_of: str = None
    first_asked: date = None
    last_contact: date = None
    # verdict
    status: str = ACTIVE
    reasons: list = field(default_factory=list)

    @property
    def active_line(self):
        return self.lines[-1].line

    @property
    def line_ids(self):
        return [l.line for l in self.lines]

    @property
    def is_active(self):
        return self.status == ACTIVE

    def mark(self, status, reason):
        # stale beats review: both keep the person off the offer list, stale is the clearer reason
        if status == STALE or self.status == ACTIVE:
            self.status = status
        self.reasons.append(reason)


# ---------- the desk's decisions on held lines (reviewed.csv) ----------

SAME, APART, IGNORE = "same person", "different people", "ignore"
DECISION_WORDS = {"same person": SAME, "same": SAME, "different people": APART, "different": APART,
                  "not same": APART, "ignore": IGNORE, "ignore line": IGNORE}


@dataclass
class Reviewed:
    """What the desk decided about lines held for a phone/name mix-up. Empty = no decisions."""
    ignore: set = field(default_factory=set)     # line numbers to leave out entirely
    same: dict = field(default_factory=dict)     # line -> lines the desk says are the same person
    apart: set = field(default_factory=set)      # frozenset({a, b}): the desk says different people
    used: list = field(default_factory=list)     # plain-words list for the report

    def are_apart(self, line, others):
        return any(frozenset((line, o)) in self.apart for o in others)


def build_reviewed(rows, line_numbers):
    """rows: records with .row, .line, .decision, .other_line (None if blank). Returns (Reviewed, warnings).
    An unclear row, a line that isn't on the waitlist, or two rows that contradict each other are skipped
    with a warning, so those lines stay held: a doubtful decision is never applied."""
    reviewed, warnings, said = Reviewed(), [], {}
    for r in rows:
        where = f"reviewed.csv row {r.row}"
        decision = DECISION_WORDS.get(" ".join(r.decision.lower().split()))
        missing = [x for x in (r.line, r.other_line) if x is not None and x not in line_numbers]
        if decision is None:
            warnings.append(f"{where}: decision '{r.decision}' isn't one of: same person, different people, "
                            "ignore. Row skipped")
        elif missing:
            warnings.append(f"{where}: line {missing[0]} isn't on the waitlist. Row skipped")
        elif decision == IGNORE:
            reviewed.ignore.add(r.line)
            reviewed.used.append(f"line {r.line}: ignored")
        elif r.other_line is None or r.other_line == r.line:
            warnings.append(f"{where}: '{decision}' needs the other line's number in other_line. Row skipped")
        else:
            pair = frozenset((r.line, r.other_line))
            if said.get(pair, decision) != decision:
                warnings.append(f"{where}: lines {r.line} and {r.other_line} are marked both 'same person' and "
                                "'different people'. Both rows skipped")
                said[pair] = None
            else:
                said[pair] = decision
    for pair, decision in said.items():
        a, b = sorted(pair)
        if decision == SAME:
            reviewed.same.setdefault(a, set()).add(b)
            reviewed.same.setdefault(b, set()).add(a)
        elif decision == APART:
            reviewed.apart.add(pair)
        if decision:
            reviewed.used.append(f"lines {a} and {b}: {decision}")
    return reviewed, warnings


# ---------- grouping (A1: phone and name together) ----------

def group_lines(lines, specs, config, reviewed=None):
    """Returns a list of Person, one per real person, with identity problems flagged for review.
    The desk's decisions (`reviewed`) settle a flagged pair or leave a line out."""
    reviewed = reviewed or Reviewed()
    nick = config.nicknames
    people = []
    phone_of = {}   # line number -> resolved phone
    person_of = {}  # line number -> Person
    flags = {}      # line number -> [reason]

    for line in lines:
        if line.line in reviewed.ignore:
            continue
        told = [x for x in sorted(reviewed.same.get(line.line, ())) if x in person_of]  # desk: same person
        phone = line.phone
        if line.same_number:
            earlier = told or [l.line for l in lines if l.line < line.line and l.line in phone_of
                               and names_compatible(l.name, line.name, nick)]
            if earlier:
                phone = phone_of[earlier[-1]]
            else:
                flags.setdefault(line.line, []).append("phone says 'same #' but no earlier line with this name")
        elif phone is None and not told:
            flags.setdefault(line.line, []).append(f"phone '{line.phone_raw}' can't be read")
        phone_of[line.line] = phone

        homes = [person_of[x] for x in told]
        for person in people:
            if any(person is h for h in homes) or reviewed.are_apart(line.line, person.line_ids):
                continue
            same_phone = phone is not None and person.phone == phone
            same_name = any(names_compatible(l.name, line.name, nick) for l in person.lines)
            if same_phone and same_name:
                homes.append(person)
                if not told:
                    break
            elif same_phone:
                note = f"shares phone with line {person.active_line} ({person.lines[-1].name}) under another name"
                flags.setdefault(line.line, []).append(note)
                for l in person.lines:
                    flags.setdefault(l.line, []).append(f"shares phone with line {line.line} ({line.name}) under another name")
            elif same_name and phone is not None and person.phone is not None:
                # only flag when both lines give a last name or initial that agree ("Lynn S." / "Lynn Savoie"),
                # so two different people who merely share a first name are not held back
                la, lb = name_parts(person.lines[-1].name)[1], name_parts(line.name)[1]
                if la and lb:
                    flags.setdefault(line.line, []).append(f"same name as line {person.active_line} but a different phone")
                    for l in person.lines:
                        flags.setdefault(l.line, []).append(f"same name as line {line.line} but a different phone")
        if homes:
            home = _join(homes, people, person_of)
        else:
            home = Person(lines=[], specs=[], phone=phone)
            people.append(home)
        if phone is not None:
            home.phone = phone  # newest readable number: the desk may have confirmed a new one
        home.lines.append(line)
        home.specs.append(specs[line.line])
        person_of[line.line] = home

    for person in people:
        for l in person.lines:
            for reason in flags.get(l.line, []):
                person.mark(REVIEW, f"check identity: line {l.line} {reason}")
    return people


def _join(groups, people, person_of):
    """Several groups are one person (the desk said so, directly or through a shared line): fold them into
    the first, keeping lines oldest first."""
    home, rest = groups[0], []
    for g in groups[1:]:
        if g is not home and not any(g is r for r in rest):
            rest.append(g)
    for other in rest:
        pairs = sorted(zip(home.lines + other.lines, home.specs + other.specs), key=lambda p: p[0].line)
        home.lines, home.specs = [l for l, _ in pairs], [s for _, s in pairs]
        home.phone = home.phone or other.phone
        people[:] = [p for p in people if p is not other]
        for l in other.lines:
            person_of[l.line] = home
    return home


# ---------- merging (B6: newer line overrides only what it mentions) ----------

def start_index(person):
    """Index of the newest "start over" line (0 if none). Older lines no longer count for what the person
    can take, and their unreadable words no longer hold them; they still count for when they first asked."""
    return max((i for i, s in enumerate(person.specs) if s.start_over), default=0)


def merge(person, config):
    all_therapists = set(config.therapists)
    start = start_index(person)
    for line, spec in zip(person.lines[start:], person.specs[start:]):
        spec: LineSpec
        if spec.therapists is not None:
            person.therapists = None if spec.therapists == all_therapists else set(spec.therapists)
            person.excluded = set(spec.excluded)
            person.female_only = bool(spec.female_only)
        else:
            person.excluded |= spec.excluded
            if spec.female_only:
                person.female_only = True
        person.prenatal = person.prenatal or spec.prenatal
        person.needs |= spec.needs
        person.pref |= spec.pref

        if spec.lengths is not None:
            person.lengths = set(spec.lengths)
        if spec.lengths_add:
            person.lengths = (person.lengths or {config.default_length}) | spec.lengths_add

        if spec.days is not None:
            person.days = set(spec.days)
            person.days_excluded = set(spec.days_excluded)
        else:
            person.days_excluded |= spec.days_excluded

        if spec.time_mentioned:
            person.earliest_start, person.start_before, person.latest_end = (
                spec.earliest_start, spec.start_before, spec.latest_end)

        if spec.day_before:
            person.day_before = True
        elif spec.notice is not None:
            person.notice, person.day_before = spec.notice, False

        if spec.available_from is not None:
            person.available_from = spec.available_from
        if spec.available_until is not None:
            person.available_until = spec.available_until
        if spec.contact:
            person.contact = spec.contact
        person.new_client = person.new_client or spec.new_client
        if spec.regular_of:
            person.regular_of = spec.regular_of

        for text in spec.unparsed:
            person.mark(REVIEW, f"line {line.line}: can't read '{text}'")
        for reason in spec.needs_check:
            person.mark(REVIEW, f"line {line.line}: {reason}, check the notebook")
        if line.added is None:
            person.mark(REVIEW, f"line {line.line}: date '{line.added_raw}' can't be read")

    person.name = fullest_name([l.name for l in person.lines])
    if person.lengths is None:
        person.lengths = {config.default_length}
    if person.notice is None:
        person.notice = config.default_notice
    dates = [l.added for l in person.lines if l.added]
    contact_dates = [d for s in person.specs for d in s.contact_dates]
    person.first_asked = min(dates) if dates else None
    person.last_contact = max(dates + contact_dates) if dates else None


# ---------- out of date ----------

def gone_reason(text):
    t = text or ""
    if "service" in t or "disconnected" in t:
        return "number not in service"
    if "moved" in t:
        return "moved away"
    if "going to" in t or "found" in t:
        return "going somewhere else now"
    return "asked to come off the list"


def mark_stale(person, bookings, run_date, config):
    newest = person.lines[-1]
    newest_spec = person.specs[-1]
    if newest_spec.gone:
        person.mark(STALE, gone_reason(newest_spec.gone))
    if person.last_contact and (run_date - person.last_contact).days > config.stale_after_days:
        person.mark(STALE, f"no contact since {person.last_contact:%b %d} (over {config.stale_after_days} days)")
    if person.available_until and person.available_until < run_date:
        person.mark(STALE, f"only wanted a spot until {person.available_until:%b %d}")

    # B7: booked since their newest line -> they got in
    if newest.added:
        nick = config.nicknames
        names = {l.name for l in person.lines}
        for b in bookings:
            if b.status.lower() in NOT_A_REAL_BOOKING or not b.booked_at:
                continue
            if b.booked_at.date() <= newest.added:
                continue
            if any(names_match_strictly(n, b.client_name, nick) for n in names):
                when = f"{b.booked_at:%b %d} ({b.client_name}, {b.therapist.split()[0]} {b.date:%b %d})"
                if person.regular_of:
                    person.mark(REVIEW, f"regular who wanted an extra visit has booked since: {when}")
                else:
                    person.mark(STALE, f"booked since: {when}")
                break


def build_people(lines, specs, bookings, run_date, config, reviewed=None):
    people = group_lines(lines, specs, config, reviewed)
    for person in people:
        merge(person, config)
        mark_stale(person, bookings, run_date, config)
    return people


def line_verdicts(people, ignored=()):
    """Per notebook line: active / stale / review / duplicate of W<n> (same shape as Tanya's key),
    plus "ignored" for lines the desk left out in reviewed.csv."""
    out = {line: "ignored" for line in ignored}
    for p in people:
        for l in p.lines:
            if p.status == STALE:
                out[l.line] = "stale"
            elif p.status == REVIEW:
                out[l.line] = "review"
            elif l.line == p.active_line:
                out[l.line] = "active"
            else:
                out[l.line] = f"duplicate of W{p.active_line:02d}"
    return out
