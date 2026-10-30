"""Turns one notebook line's free-text notes into structured fields.

Each line is read on its own. A field left as None means "this line didn't mention it", so an
older line for the same person can supply it (see people.merge). Anything the parser can't
read goes into `unparsed`, and that person is then held for review instead of being offered.
A line that starts with "start over" (or "new:") replaces everything the older lines said.

Health details are never kept: a piece that mentions one is dropped. Only the clinic's routing rules
survive, as the therapist tags the person needs (`needs`; settings "routing"; today one rule: pregnancy ->
prenatal-trained therapists only, also kept as the flag `prenatal`). The reason is never kept, only the tag. The pieces beside a
health detail, and anything in brackets, are read only if they hold a scheduling word, so "sore neck,
Rachel only" still keeps "Rachel only". A piece that mixes both is held for review without quoting it.
"""
import re
from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date, time, timedelta

from kettle.config import PRENATAL_TAG, word_pattern
from kettle.core.normalise import MONTHS, MONTH_RE, fold

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
WEEKDAYS = {"Mon", "Tue", "Wed", "Thu", "Fri"}
DAY_RE = r"(?:mon(?:day)?s?|tue(?:s|sday)?s?|wed(?:nesday)?s?|thu(?:r|rs|rsday)?s?|fri(?:day)?s?|sat(?:urday)?s?|sun(?:day)?s?)"
DATE_RE = rf"(?:{MONTH_RE}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?|\d{{1,2}}/\d{{1,2}})"
CLOCK_RE = r"\d{1,2}(?::\d{2})?"
UNIT_RE = r"(?:min|mins|minutes|h|hr|hrs|hour|hours)"

HEALTH_RE = re.compile(
    r"pregnan|prenatal|expecting|trimester|\btri\b|sciatica|low back|back pain|bad back|\bknee|\bhips?\b"
    r"|shoulder|rotator|post-?op|surger|surgical|replacement|fibro|pressure|\bmva\b|claim|\btmj\b"
    r"|migraine|concussion|cancer|no deep|light only|hamstring|injur|\bpain|\bsore|accident|arthritis"
    r"|whiplash|sprain|strain|\bneck\b|headache|condition|diabet|stroke|tendon|\bdisc\b|plantar"
    r"|physio|chemo|scoliosis|chronic|ins pays"
)

# Words that carry no scheduling meaning once the patterns below have run.
FILLER = {
    "again", "called", "back", "now", "still", "waiting", "wants", "want", "in", "sorry", "add",
    "ok", "okay", "fine", "too", "only", "then", "the", "and", "or", "please", "pls", "if", "poss",
    "possible", "an", "a", "extra", "one", "is", "to", "also", "just", "thanks", "asap", "will",
}
START_OVER_RE = re.compile(r"\s*(?:start(?:ing)? over|new\s*:)\s*[-:,.]?\s*")
# what a person can take; a "start over" line has to say at least one of these
NEEDS_FIELDS = ("therapists", "excluded", "female_only", "prenatal", "needs", "lengths", "lengths_add", "days",
                "days_excluded", "time_mentioned", "notice", "day_before", "available_from", "available_until")


@dataclass
class LineSpec:
    # therapist block
    therapists: set = None          # allowed full names (all therapists = "any"); None = not mentioned
    excluded: set = field(default_factory=set)
    female_only: bool = None
    pref: set = field(default_factory=set)  # sort hint only, never a filter
    prenatal: bool = False
    needs: set = field(default_factory=set)  # therapist tags a routing rule requires (e.g. "prenatal-trained")
    # length
    lengths: set = None
    lengths_add: set = field(default_factory=set)  # "60 ok too"
    # days
    days: set = None
    days_excluded: set = field(default_factory=set)
    # time of day (start/end clock limits); time_any clears older limits
    time_mentioned: bool = False
    earliest_start: time = None
    start_before: time = None
    latest_end: time = None
    # notice
    notice: float = None
    day_before: bool = None
    # availability dates
    available_from: date = None
    available_until: date = None
    # status and contact
    gone: str = None
    contact: str = None
    new_client: bool = False
    regular_of: str = None
    contact_dates: list = field(default_factory=list)
    had_health_detail: bool = False
    unparsed: list = field(default_factory=list)
    needs_check: list = field(default_factory=list)  # reasons to hold the line that never quote the note
    start_over: bool = False  # older lines no longer count for what this person can take


def clock(text):
    """'3:30' -> 15:30, '5' -> 17:00, '10' -> 10:00. Hours 1-7 are read as p.m. (clinic is open 9-8)."""
    hours, _, minutes = text.partition(":")
    h, m = int(hours), int(minutes or 0)
    if 1 <= h <= 7:
        h += 12
    return time(h, m)


def note_date(text, run_date):
    """Dates inside notes ('til Oct 9', 'til Nov 15', 'called 10/9') can be past or future:
    pick the year that puts the date nearest the run date."""
    t = text.replace(".", "").strip()
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})", t)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
    else:
        m = re.fullmatch(rf"({MONTH_RE})\s+(\d{{1,2}})(?:st|nd|rd|th)?", t)
        month, day = MONTHS[m.group(1)], int(m.group(2))
    return min((date(run_date.year + k, month, day) for k in (-1, 0, 1)), key=lambda d: abs((d - run_date).days))


def _said(value):
    """A parsed field holds something: 0 h notice counts; None, False and an empty set don't."""
    return value is not None and value is not False and value != set()


def day_set(text):
    out = set()
    for token in re.findall(DAY_RE, text):
        out.add(DAY_NAMES[["mon", "tue", "wed", "thu", "fri", "sat", "sun"].index(token[:3])])
    return out


def hours_value(amount, unit):
    value = 1.0 if amount in ("a", "an") else float(amount)
    return value / 60 if unit.startswith("m") else value


class NoteParser:
    def __init__(self, config):
        self.config = config
        aliases = config.alias_map()
        self.aliases = aliases
        long_aliases = sorted((a for a in aliases if len(a) > 1), key=len, reverse=True)
        self.alias_re = r"(?:" + "|".join(re.escape(a) for a in long_aliases) + r")"
        self.letters = {a: n for a, n in aliases.items() if len(a) == 1}
        self.all_therapists = set(config.therapists)
        # the settings' routing rules, and any extra private words: a piece using one is a private detail too
        self.rules = [(rule.tag, re.compile(rule.pattern)) for rule in config.routing]
        extra = [rule.pattern for rule in config.routing] + [word_pattern(w) for w in config.health_words]
        self.health_re = re.compile(HEALTH_RE.pattern + "".join("|" + p for p in extra)) if extra else HEALTH_RE
        # any word that could limit who, when, how long or how soon: a piece holding one is never dropped unread
        self.schedule_word = re.compile(
            rf"\b{self.alias_re}\b|\b[a-z](?:\s*(?:/|\bor\b)\s*[a-z])+\b|\b[a-z]\s+only\b"
            rf"|\b(?:any|anyone|anybody|whoever|female|woman|women)\b|\b{DAY_RE}\b|\b(?:wkdays|weekdays?|weekends?|wknds?)\b"
            r"|\b(?:am|pm|mornings?|afternoons?|evenings?|eves?|lunch|noon|tonight)\b|\d{1,2}:\d{2}"
            r"|\b(?:after|before|by|from|until|til|till|notice|can come)\b|\bday before\b|\bnext day\b"
            rf"|\d+(?:\.\d+)?\s*{UNIT_RE}\b|\b(?:30|45|60|90)\b(?!\s*(?:wks?|weeks?|yrs?|years?|days?|months?|lbs?))"
        )

    # ---------- public ----------

    def parse(self, notes, run_date):
        spec = LineSpec()
        text = fold(notes)
        start_over = START_OVER_RE.match(text)
        if start_over:
            spec.start_over = True
            text = text[start_over.end():]
        # parentheses usually hold context ("(work)", "(2 kids)", "(rotator cuff ...)")
        for inner in re.findall(r"\(([^)]*)\)", text):
            self._parse_aside(inner, spec, run_date)
        text = re.sub(r"\([^)]*\)", " ", text)

        for segment in re.split(r"\s+-\s+|\s+-$|^-\s+|\.\s+|\.$|;", text):
            segment = segment.strip(" .,!?")
            if not segment:
                continue
            if self.health_re.search(segment):
                self._parse_aside(segment, spec, run_date)
                continue
            for part in segment.split(","):
                part = part.strip(" .!?")
                if part:
                    self._parse_part(part, spec, run_date)
        # a bare "start over" would wipe the older lines and leave "anyone, any time": hold it instead
        if spec.start_over and not any(_said(getattr(spec, f)) for f in NEEDS_FIELDS):
            spec.needs_check.append("'start over' line with no details")
        return spec

    # ---------- a piece next to a health detail, or in brackets ----------

    def _parse_aside(self, piece, spec, run_date):
        """Read only the comma parts that hold a scheduling word; drop the rest unread. Reasons to hold
        go in `needs_check` in plain words, so no health detail reaches a report."""
        for part in piece.split(","):
            part = part.strip(" .!?")
            health = self.health_re.search(part)
            if health:
                spec.had_health_detail = True
                spec.needs |= {tag for tag, words in self.rules if words.search(part)}
                spec.prenatal = PRENATAL_TAG in spec.needs
            if not self.schedule_word.search(self.health_re.sub(" ", part)):
                continue
            if health:
                spec.needs_check.append("scheduling words mixed with a private detail")
                continue
            before = len(spec.unparsed)
            self._parse_part(part, spec, run_date)
            if len(spec.unparsed) > before:
                del spec.unparsed[before:]
                spec.needs_check.append("unclear words next to a private detail")

    # ---------- one comma-separated piece ----------

    def _parse_part(self, s, spec, run_date):
        s = " " + s + " "

        def take(pattern, handler=None):
            nonlocal s
            for m in list(re.finditer(pattern, s)):
                if handler:
                    handler(m)
            s = re.sub(pattern, " ", s)

        cfg = self.config

        # people who have left the list
        def gone(m):
            spec.gone = m.group(0).strip(" ?!")
        take(r"\bmoved\b.*|#?\s*not in service.*|\bdisconnected\b.*|\btake (?:her |him |them |me )?off\b.*"
             r"|\bcross (?:her |him |them )?off\b.*|\bgoing to (?:someone|somewhere|another)\b.*"
             r"|\bfound (?:someone|another|a)\b.*|\bno longer\b.*|\bpassed away\b.*", gone)

        # context that carries no scheduling meaning
        take(r"\btried \d+\s*x\b|\bdrives? in from \w+|\bworks? (?:at|in|for|nights|days|shifts?)\b.*"
             r"|\bacross the st(?:reet)?\b|\bthen back to \w+|\bwedding is\b.*|\bstill wants in\b|\bwants an extra\b"
             r"|\bback now\b|\bshift work(?:er)?\b|\bretired\b")

        # dates: "called 10/9" is contact; availability windows
        take(rf"\bcalled ({DATE_RE})", lambda m: spec.contact_dates.append(note_date(m.group(1), run_date)))

        def until_end_of_month(m):
            d = note_date(m.group(1) + " 1", run_date)
            spec.available_until = d.replace(day=monthrange(d.year, d.month)[1])
        take(rf"\b(?:only )?(?:til|till|until|to) end of ({MONTH_RE})\b.*", until_end_of_month)

        def away_until(m):
            spec.available_from = note_date(m.group(1), run_date) + timedelta(days=1)
        take(rf"\b(?:away|gone|out of town|travel+ing|on vacation)\b.*?\b(?:til|till|until)\s+({DATE_RE})", away_until)

        def before_event(m):
            spec.available_until = note_date(m.group(1), run_date) - timedelta(days=1)
        take(rf"\b(?:wants one )?before (?:her |his )?(?:\w+ )?({DATE_RE})", before_event)

        def from_date(m):
            spec.available_from = note_date(m.group(1), run_date)
        take(rf"\b(?:from|after|starting) ({DATE_RE})", from_date)

        def until_date(m):
            spec.available_until = note_date(m.group(1), run_date)
        take(rf"\b(?:here |in town |only here |only )?(?:til|till|until) ({DATE_RE})", until_date)

        # notice
        def day_before(m):
            spec.day_before = True
        take(r"\bnext day only\b|\b(?:told )?(?:the )?day before\b|\bday'?s notice\b|\b(?:the )?night before\b", day_before)

        def default_notice(m):
            spec.notice = cfg.default_notice
        take(r"\bsame day ok\b", default_notice)

        def quick(m):
            spec.notice = cfg.quick_notice
        take(r"\bcan come (?:in )?quick(?:ly)?\b|\bcan come right away\b", quick)

        def notice(m):
            amount = m.group(2) or m.group(1)
            spec.notice = hours_value(amount, m.group(3))
        take(rf"\b(?:can come in|can be here in|can come within|needs?)\s+(an|a|\d+(?:\.\d+)?)(?:\s*-\s*(\d+(?:\.\d+)?))?\s*({UNIT_RE})\b(?:'?s)?(?:\s+notice)?", notice)
        take(rf"\b(\d+(?:\.\d+)?)(?:\s*-\s*(\d+(?:\.\d+)?))?\s*({UNIT_RE})'?s?\s+notice(?:\s+ok)?\b", notice)

        # contact preference, client status
        def text_only(m):
            spec.contact = "text only"
        take(r"\btext (?:only|don'?t call|pls|please)\b|\bno calls?\b", text_only)

        def call_only(m):
            spec.contact = "call (landline)"
        take(r"\blandline\b|\bcall only\b|\bno texts?\b", call_only)

        def new_client(m):
            spec.new_client = True
        take(r"\bnew (?:client|pt|patient)\b|\bfirst visit\b", new_client)

        def regular(m):
            spec.regular_of = self.aliases.get(m.group(1))
        take(rf"\b({self.alias_re})'?s reg(?:ular)?\b", regular)

        # length phrases that are conditional or additive
        take(r"\b(?:can do|could do|wants?)\s+\d+\s+if\s+(?:ins|insurance)\b.*")

        def length_optional(m):
            spec.lengths = (spec.lengths or set()) | {int(m.group(1))}
        take(r"\bwants?\s+(\d{2})\s+if poss(?:ible)?\b", length_optional)

        def length_add(m):
            spec.lengths_add.add(int(m.group(1)))
        take(r"\b(\d{2})\s*(?:min)?\s+ok too\b", length_add)

        # time of day
        def any_time(m):
            spec.time_mentioned = True
        take(r"\bany ?time\b", any_time)

        def lunch(m):
            spec.time_mentioned = True
            spec.earliest_start = clock(m.group(1)) if m.group(1) else cfg.lunch_from
            spec.latest_end = clock(m.group(2)) if m.group(2) else cfg.lunch_until
            spec.days = WEEKDAYS & (spec.days or WEEKDAYS)  # a work lunch break: weekdays
        take(rf"\b(?:on (?:his|her|their) )?lunch(?:\s+({CLOCK_RE})\s*-\s*({CLOCK_RE}))?\b(?:\s+only)?", lunch)

        def done_by(m):
            spec.time_mentioned = True
            spec.latest_end = clock(m.group(1))
        take(rf"\b(?:has to be |must be |needs to be )?(?:done|finished|out) by ({CLOCK_RE})", done_by)

        def not_before(m):
            spec.time_mentioned = True
            spec.earliest_start = clock(m.group(1))
        take(rf"\bnot before ({CLOCK_RE})\b", not_before)

        def evenings(m):
            spec.time_mentioned = True
            spec.earliest_start = clock(m.group(1)) if m.group(1) else cfg.evenings_from
        take(rf"\b(?:evenings?|eves?)(?:\s+(?:after|from)\s+({CLOCK_RE}))?\b", evenings)

        def after(m):
            spec.time_mentioned = True
            spec.earliest_start = clock(m.group(1))
        take(rf"\b(?:after|from|starting)\s+({CLOCK_RE})\b(?:\s+on)?", after)

        def mornings(m):
            spec.time_mentioned = True
            spec.start_before = cfg.mornings_before
        take(r"\b(?:am|a\.m\.|mornings?)\b", mornings)

        def afternoons(m):
            spec.time_mentioned = True
            spec.earliest_start = cfg.afternoons_from
        take(r"\b(?:pm|p\.m\.|afternoons?)\b", afternoons)

        # days
        def weekdays(m):
            spec.days = set(WEEKDAYS)
        take(r"\b(?:wkdays|weekdays|week days|mon-fri|m-f)\b", weekdays)

        def not_days(m):
            spec.days_excluded |= day_set(m.group(0))
        take(rf"\bnot\s+{DAY_RE}(?:\s*(?:or|/|,|&|and)\s*{DAY_RE})*\b", not_days)

        def days(m):
            spec.days = (spec.days or set()) | day_set(m.group(0))
        take(rf"\b{DAY_RE}(?:\s*(?:or|/|,|&|and)\s*{DAY_RE})*\b", days)

        # therapists
        a = self.alias_re

        def excluded(m):
            # "anyone but Dave" / "not Marc": only adds an exclusion, so an older line's therapist list still applies
            spec.excluded |= {self.aliases[x] for x in re.findall(a, m.group(0)) if x in self.aliases}
        take(rf"\b(?:ab|anyone but|any but|anybody but|not|no)\s+{a}(?:\s*(?:or|/|,|&)\s*{a})*\b", excluded)

        def female(m):
            spec.female_only = True
            spec.therapists = set(self.all_therapists)
        take(r"\b(?:any(?:one)? )?(?:female|woman|women)(?: therapist)?(?: only)?\b", female)

        def named(m):
            names = {self.aliases[x] for x in re.findall(a, m.group(0)) if x in self.aliases}
            if m.group("pref"):
                spec.pref |= names
            else:
                spec.therapists = (spec.therapists if spec.therapists and spec.therapists != self.all_therapists else set()) | names
        take(rf"\b{a}(?:\s*(?:or|/|,|&)\s*{a})*\b(?:\s+(?P<pref>pref(?:erred)?))?", named)

        def letters(m):
            picked = re.findall(r"\b[a-z]\b", m.group(0).replace("only", "").replace(" or ", " / "))
            if all(x in self.letters for x in picked):
                spec.therapists = (spec.therapists if spec.therapists and spec.therapists != self.all_therapists else set()) | {self.letters[x] for x in picked}
            else:
                spec.unparsed.append(m.group(0).strip())
        take(r"\b[a-z](?:\s*(?:/|\bor\b)\s*[a-z])+\b|\b[a-z]\s+only\b", letters)

        def any_therapist(m):
            spec.therapists = set(self.all_therapists)
        take(r"\b(?:any|anyone|anybody|whoever|no pref(?:erence)?)\b", any_therapist)

        # lengths
        def length_hours(m):
            spec.lengths = (spec.lengths or set()) | {round(float(m.group(1)) * 60)}
        take(r"\b(\d+(?:\.\d+)?)\s*(?:hr|hrs|hour|hours|h)\b", length_hours)
        take(r"\ban hour\b", lambda m: setattr(spec, "lengths", (spec.lengths or set()) | {60}))

        def length_minutes(m):
            spec.lengths = (spec.lengths or set()) | {int(x) for x in re.findall(r"\d{2}", m.group(0))}
        take(r"\b(?:30|45|60|90)\b(?:\s*(?:min|mins|minutes))?(?:\s*(?:or|/)\s*(?:30|45|60|90)\b(?:\s*(?:min|mins))?)*", length_minutes)

        # whatever is left must be filler, or the line needs a human
        leftover = [w for w in re.findall(r"[a-z0-9#']+", s) if w not in FILLER]
        if leftover:
            spec.unparsed.append(" ".join(leftover))
