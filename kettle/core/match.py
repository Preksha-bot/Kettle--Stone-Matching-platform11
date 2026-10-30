"""The core matcher: for one late opening, who on the list fits? Same code for CSV input today and the platform later."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from kettle.core.normalise import names_match_strictly

ORDERS = ("first-asked", "shortest-notice", "regulars-first")
DAY_LONG = {"Mon": "Mondays", "Tue": "Tuesdays", "Wed": "Wednesdays", "Thu": "Thursdays",
            "Fri": "Fridays", "Sat": "Saturdays", "Sun": "Sundays"}


def hm(t):
    """12-hour clock without leading zero, e.g. 4:00, 12:30 (portable; no %-I on Windows)."""
    h = t.hour % 12 or 12
    return f"{h}:{t.minute:02d}"


@dataclass
class Pick:
    person: object
    summary: str
    tags: list = field(default_factory=list)


@dataclass
class MatchResult:
    opening: object
    picks: list = field(default_factory=list)
    closest: list = field(default_factory=list)  # (person, why not)
    note: str = ""


def allowed_therapists(person, config):
    names = set(person.therapists) if person.therapists else set(config.therapists)
    names -= person.excluded
    if person.female_only:
        names = {n for n in names if config.therapists[n].female}
    if person.prenatal:  # also a tag in `needs` now; kept for lines saved before routing rules existed
        names = {n for n in names if config.therapists[n].prenatal_trained}
    for tag in person.needs:
        names = {n for n in names if tag in config.therapists[n].tags}
    return names


def why_not(person, opening, therapist, config):
    """None if the person fits the opening, else a short reason safe to show at the desk (no health details)."""
    if person.status != "active":
        label = "stale" if person.status == "stale" else "held for review"
        return f"{label}: {person.reasons[0]}"
    d = opening.date
    if person.available_from and d < person.available_from:
        return f"not available until {person.available_from:%b %d}"
    if person.available_until and d > person.available_until:
        return f"only available until {person.available_until:%b %d}"

    if therapist is None or therapist.name not in allowed_therapists(person, config):
        first = therapist.first_name if therapist else opening.therapist
        if therapist and therapist.name in person.excluded:
            return f"not {first}"
        if therapist and person.female_only and not therapist.female:
            return "female therapist only"
        return f"{first} isn't on their list"

    day = opening.day
    if (person.days and day not in person.days) or day in person.days_excluded:
        return f"can't do {DAY_LONG[day]}"

    fitting = sorted(l for l in person.lengths if l <= opening.length_min)
    if not fitting:
        return f"wants {min(person.lengths)} min"

    start = opening.start
    if person.start_before and start >= person.start_before:
        return "mornings only"
    if person.earliest_start and start < person.earliest_start:
        return f"only from {hm(person.earliest_start)}"
    if person.latest_end:
        start_dt = datetime.combine(d, start)
        if not any((start_dt + timedelta(minutes=l)).time() <= person.latest_end for l in fitting):
            return f"has to be done by {hm(person.latest_end)}"

    if person.day_before and opening.cancelled_at.date() >= d:
        return "needs to be told the day before"
    if opening.hours_notice < person.notice:
        return f"needs {person.notice:g} h notice"
    return None


def summary(person, opening, config):
    """One line the desk can read in seconds: what this person can take."""
    names = allowed_therapists(person, config)
    if names == set(config.therapists):
        who = "any therapist"
    elif person.female_only and not person.therapists and not person.prenatal and not person.needs:
        who = "female therapist"
    elif not person.therapists and person.excluded and not (person.prenatal or person.needs or person.female_only):
        who = "anyone but " + " or ".join(sorted(config.therapists[n].first_name for n in person.excluded))
    else:
        who = " or ".join(sorted(config.therapists[n].first_name for n in names))
    parts = [who, "/".join(str(l) for l in sorted(person.lengths)) + " min"]
    if person.days:
        parts.append("/".join(x for x in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"] if x in person.days))
    if person.days_excluded:
        parts.append("not " + "/".join(sorted(person.days_excluded)))
    if person.start_before:
        parts.append("mornings")
    if person.earliest_start and person.latest_end:
        parts.append(f"{hm(person.earliest_start)}–{hm(person.latest_end)}")
    elif person.earliest_start:
        parts.append(f"from {hm(person.earliest_start)}")
    elif person.latest_end:
        parts.append(f"done by {hm(person.latest_end)}")
    parts.append("told day before" if person.day_before else f"{person.notice:g} h notice")
    return " · ".join(parts)


def tags(person, therapist):
    out = []
    if therapist and therapist.approval == "see_first":
        out.append(f"ask {therapist.first_name} first")
    if person.new_client:
        out.append("new client, phone only")
    if person.contact:
        out.append(person.contact)
    return out


def visits_with(person, therapist_name, bookings, nicknames):
    names = {l.name for l in person.lines}
    return sum(1 for b in bookings if b.therapist == therapist_name and b.status.lower() == "completed"
               and any(names_match_strictly(n, b.client_name, nicknames) for n in names))


def sort_key(order, opening, bookings, config):
    def first_asked(p):
        return (p.first_asked, p.lines[0].line)

    if order == "shortest-notice":
        return lambda p: (24.0 if p.day_before else p.notice, *first_asked(p))
    if order == "regulars-first":
        def regular(p):
            is_regular = p.regular_of == opening.therapist or \
                visits_with(p, opening.therapist, bookings, config.nicknames) >= config.regular_min_visits
            return (0 if is_regular else 1, *first_asked(p))
        return regular
    return first_asked


def match_opening(opening, people, bookings, config, order=None, declined=()):
    """Up to config.max_names people who fit, or nobody. `declined` = waitlist line numbers to skip (said no)."""
    result = MatchResult(opening=opening)
    if opening.is_no_show:
        result.note = "no-show: only known 15 minutes after the start, so it is never offered"
        return result
    therapist = config.therapist_by_name(opening.therapist)
    ranked = sorted(people, key=sort_key(order or config.order, opening, bookings, config))
    for person in ranked:
        if set(person.line_ids) & set(declined):
            continue
        reason = why_not(person, opening, therapist, config)
        if reason is None:
            if len(result.picks) < config.max_names:
                result.picks.append(Pick(person, summary(person, opening, config), tags(person, therapist)))
        elif len(result.closest) < 3:
            result.closest.append((person, reason))
    if not result.picks:
        result.note = "nobody on the list fits"
    return result


def match_all(openings, people, bookings, config, order=None, declined=None):
    declined = declined or {}
    return [match_opening(o, people, bookings, config, order, declined.get(o.opening_id, ())) for o in openings]
