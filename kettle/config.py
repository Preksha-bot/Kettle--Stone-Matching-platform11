"""Loads config/clinic.json, checks it, and exposes the clinic settings the rest of the code uses."""
import json
import re
from dataclasses import dataclass, field
from datetime import time
from pathlib import Path

from kettle.core.normalise import fold

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "clinic.json"

SECTIONS = {"therapists", "defaults", "time_words", "nicknames", "routing", "health_words"}
THERAPIST_FIELDS = {"aliases", "female", "prenatal_trained", "tags", "approval"}
RULE_FIELDS = {"tag", "words", "chip"}
# The clinic's two built-in therapist tags, set with the yes/no fields "female" and "prenatal_trained"
FEMALE_TAG, PRENATAL_TAG = "female", "prenatal-trained"
# The routing a settings file without a "routing" section gets: the clinic's one health rule (plan B9)
DEFAULT_ROUTING = {"Prenatal": {"tag": PRENATAL_TAG, "words": ["pregnan*", "prenatal*", "expecting*", "trimester*", "tri"],
                                "chip": "Prenatal-trained therapists only"}}
# Words a routing word may not be: they already say who, when, how long or how soon in the book's shorthand
SCHEDULE_WORDS = {"any", "anyone", "only", "or", "not", "but", "female", "am", "pm", "morning", "mornings", "afternoon",
                  "afternoons", "evening", "evenings", "lunch", "after", "before", "by", "from", "til", "until",
                  "notice", "min", "mins", "hr", "hrs", "hour", "hours", "day", "days", "week", "mon", "tue", "tues",
                  "wed", "thu", "thur", "thurs", "fri", "sat", "sun", "new", "client", "reg", "text", "call", "start",
                  "over", "same", "ok"}
APPROVALS = {"none", "see_first"}
DEFAULT_FIELDS = {"length_min", "notice_hours", "stale_after_days", "max_names", "order", "regular_min_visits",
                  "max_offers_per_week"}
CLOCK_FIELDS = {"mornings_before", "afternoons_from", "evenings_from", "lunch_from", "lunch_until"}
TIME_FIELDS = CLOCK_FIELDS | {"quick_notice_hours"}


class ConfigError(ValueError):
    """The settings file has a mistake. The run stops before anything is matched."""


def _hhmm(text):
    hours, minutes = text.split(":")
    return time(int(hours), int(minutes))


def _is_hhmm(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{1,2}:\d{2}", value):
        return False
    hours, minutes = map(int, value.split(":"))
    return hours < 24 and minutes < 60


def _is_number(value, minimum=0, whole=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return value >= minimum and (not whole or float(value).is_integer())


def check_settings(raw):
    """Every mistake in the settings, in words Julie can act on. An empty list means the file is fine.
    Keys starting with "_" are comments and are allowed anywhere."""
    from kettle.core.match import ORDERS

    problems = []

    def unknown(where, keys, allowed):
        problems.extend(f"{where}: unknown setting '{k}' (allowed: {', '.join(sorted(allowed))})"
                        for k in keys if not k.startswith("_") and k not in allowed)

    if not isinstance(raw, dict):
        return ["the file should hold one set of settings in { }"]
    unknown("top level", raw, SECTIONS)
    for section in ("therapists", "defaults", "time_words"):
        if not isinstance(raw.get(section), dict):
            problems.append(f"missing section '{section}'")
    if problems:
        return problems

    # therapists: a short form may belong to one therapist only, or notes using it are read as the wrong person
    owner = {}
    for name, t in raw["therapists"].items():
        where = f"therapist '{name}'"
        if not isinstance(t, dict):
            problems.append(f"{where}: should be a set of settings in {{ }}")
            continue
        unknown(where, t, THERAPIST_FIELDS)
        problems.extend(f"{where}: '{key}' must be true or false"
                        for key in ("female", "prenatal_trained") if not isinstance(t.get(key), bool))
        if t.get("approval") not in APPROVALS:
            problems.append(f"{where}: 'approval' must be one of: {', '.join(sorted(APPROVALS))}")
        aliases = t.get("aliases")
        if not isinstance(aliases, list) or not all(isinstance(a, str) and a.strip() for a in aliases):
            problems.append(f"{where}: 'aliases' must be a list of short forms, e.g. [\"dave\", \"d\"]")
            continue
        for alias in aliases:
            key = fold(alias.strip())
            if owner.get(key, name) != name:
                problems.append(f"short form '{alias}' is used for both {owner[key]} and {name}: remove it from "
                                "both (notes that use it are then held for review)")
            owner.setdefault(key, name)

    d = raw["defaults"]
    unknown("defaults", d, DEFAULT_FIELDS)
    for key in ("length_min", "stale_after_days", "max_names", "regular_min_visits"):
        if (key in d or key != "regular_min_visits") and not _is_number(d.get(key), 1, whole=True):
            problems.append(f"defaults: '{key}' must be a whole number of 1 or more")
    if not _is_number(d.get("notice_hours")):
        problems.append("defaults: 'notice_hours' must be a number of hours, 0 or more")
    if "max_offers_per_week" in d and not _is_number(d["max_offers_per_week"], 0, whole=True):
        problems.append("defaults: 'max_offers_per_week' must be a whole number, 0 or more (0 = no limit)")
    if d.get("order") not in ORDERS:
        problems.append(f"defaults: 'order' must be one of: {', '.join(ORDERS)}")

    tw = raw["time_words"]
    unknown("time_words", tw, TIME_FIELDS)
    for key in sorted(CLOCK_FIELDS):
        if not _is_hhmm(tw.get(key)):
            problems.append(f"time_words: '{key}' is {tw.get(key)!r}, not a time (use HH:MM, e.g. 12:00)")
    if not _is_number(tw.get("quick_notice_hours")):
        problems.append("time_words: 'quick_notice_hours' must be a number of hours, 0 or more")
    if _is_hhmm(tw.get("lunch_from")) and _is_hhmm(tw.get("lunch_until")) \
            and _hhmm(tw["lunch_from"]) >= _hhmm(tw["lunch_until"]):
        problems.append("time_words: 'lunch_from' must be earlier than 'lunch_until'")

    nicknames = raw.get("nicknames", {})
    if not isinstance(nicknames, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in nicknames.items()):
        problems.append("nicknames: must be pairs of names, e.g. \"bob\": \"robert\"")
    problems += _check_routing(raw, owner)
    return problems


def therapist_tags(t):
    """A therapist's tags as written in the settings: the built-in yes/no ones plus the "tags" list."""
    tags = {x.strip().lower() for x in t.get("tags", []) if isinstance(x, str) and x.strip()}
    if t.get("female") is True:
        tags.add(FEMALE_TAG)
    if t.get("prenatal_trained") is True:
        tags.add(PRENATAL_TAG)
    return tags


def _check_routing(raw, short_forms):
    """Routing rules: each sends the people whose notes use its words only to therapists with its tag."""
    problems = []
    for name, t in raw["therapists"].items():
        if isinstance(t, dict) and "tags" in t and (not isinstance(t["tags"], list)
                                                   or not all(isinstance(x, str) and x.strip() for x in t["tags"])):
            problems.append(f"therapist '{name}': 'tags' must be a list of words, e.g. [\"post-op-trained\"]")
    routing = raw.get("routing", DEFAULT_ROUTING)
    if not isinstance(routing, dict):
        return problems + ["routing: should be a set of rules in { }"]
    everyone = set().union(*(therapist_tags(t) for t in raw["therapists"].values() if isinstance(t, dict)))
    words_of = {}
    for name, rule in routing.items():
        where = f"routing rule '{name}'"
        if not isinstance(rule, dict):
            problems.append(f"{where}: should be a set of settings in {{ }}")
            continue
        problems.extend(f"{where}: unknown setting '{k}' (allowed: {', '.join(sorted(RULE_FIELDS))})"
                        for k in rule if not k.startswith("_") and k not in RULE_FIELDS)
        tag = rule.get("tag")
        if not isinstance(tag, str) or not tag.strip():
            problems.append(f"{where}: 'tag' must be a word, e.g. \"post-op-trained\"")
        elif tag.strip().lower() not in everyone:
            problems.append(f"{where}: no therapist has the tag '{tag}', so the people it applies to could never be "
                            "offered anything: give the tag to at least one therapist")
        if not isinstance(rule.get("chip"), str) or not rule["chip"].strip():
            problems.append(f"{where}: 'chip' must be a short label for the card, e.g. \"Post-op-trained only\"")
        words = rule.get("words")
        if not isinstance(words, list) or not words or not all(isinstance(w, str) and w.strip("* ") for w in words):
            problems.append(f"{where}: 'words' must be a list of words that set it, e.g. [\"post-op\", \"surger*\"]")
            continue
        for w in words:
            key = fold(w.strip()).rstrip("*")
            if key in short_forms:
                problems.append(f"{where}: '{w}' is also a short form for {short_forms[key]}")
            elif key in SCHEDULE_WORDS or key.isdigit():
                problems.append(f"{where}: '{w}' already means something in the book's shorthand (who, when, "
                                "how long or how soon)")
            elif words_of.get(key, name) != name:
                problems.append(f"{where}: '{w}' is also a word of rule '{words_of[key]}'")
            words_of.setdefault(key, name)
    extra = raw.get("health_words", [])
    if not isinstance(extra, list) or not all(isinstance(w, str) and w.strip("* ") for w in extra):
        problems.append("health_words: must be a list of words, e.g. [\"shingles\"]")
    return problems


def word_pattern(word):
    """A word from the settings as a pattern for notes: a whole word, or the start of one when it ends with '*'
    ('pregnan*' matches 'pregnant'; 'tri' matches 'tri' but not 'trip')."""
    w = fold(word.strip())
    return r"\b" + re.escape(w.rstrip("*")) + (r"\w*" if w.endswith("*") else r"\b")


@dataclass
class Rule:
    """A routing rule: people whose notes use one of `words` only see therapists tagged `tag`."""
    name: str
    tag: str
    words: list
    chip: str  # the label on the fill-in card; desk only

    @property
    def pattern(self):
        return "|".join(word_pattern(w) for w in self.words)


@dataclass
class Therapist:
    name: str
    aliases: list
    tags: set           # "female", "prenatal-trained" and any the clinic adds
    approval: str       # "none" or "see_first"

    @property
    def first_name(self):
        return self.name.split()[0]

    @property
    def female(self):
        return FEMALE_TAG in self.tags

    @property
    def prenatal_trained(self):
        return PRENATAL_TAG in self.tags


@dataclass
class Config:
    therapists: dict  # full name -> Therapist
    default_length: int
    default_notice: float
    stale_after_days: int
    max_names: int
    order: str
    regular_min_visits: int
    max_offers_per_week: int  # offers per person in 7 days before they rest; 0 = no limit (Marc decides)
    mornings_before: time
    afternoons_from: time
    evenings_from: time
    lunch_from: time
    lunch_until: time
    quick_notice: float
    nicknames: dict = field(default_factory=dict)
    routing: list = field(default_factory=list)       # Rule
    health_words: list = field(default_factory=list)  # extra words that mark a private detail in a note

    def alias_map(self):
        """alias (lowercase) -> full therapist name."""
        out = {}
        for t in self.therapists.values():
            for alias in t.aliases:
                out[alias] = t.name
        return out

    def therapist_by_name(self, text):
        """Match a therapist column value to the configured therapist: the full name ('Josée Landry') first,
        else a first name with an optional start of the last name ('Josée', 'Josée L.') when exactly one
        therapist fits. None when nobody or more than one fits, so a new therapist is never mistaken for another."""
        key = " ".join(fold(text).replace(".", " ").split())
        for t in self.therapists.values():
            if fold(t.name) == key:
                return t
        first, _, rest = key.partition(" ")
        found = [t for t in self.therapists.values()
                 if fold(t.first_name) == first and fold(t.name).partition(" ")[2].startswith(rest)]
        return found[0] if len(found) == 1 else None


def load_config(path=DEFAULT_CONFIG):
    """Read and check the settings file. Any mistake stops the run with a list of what to fix."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ConfigError(f"settings file not found: {path}") from None
    except json.JSONDecodeError as e:
        raise ConfigError(f"{path} isn't valid JSON (line {e.lineno}, column {e.colno}): {e.msg}") from None
    problems = check_settings(raw)
    if problems:
        raise ConfigError(f"{path} has {len(problems)} problem(s):\n  " + "\n  ".join(problems))
    therapists = {
        name: Therapist(name, [a.lower() for a in t["aliases"]], therapist_tags(t), t["approval"])
        for name, t in raw["therapists"].items()
    }
    d, tw = raw["defaults"], raw["time_words"]
    return Config(
        therapists=therapists,
        default_length=int(d["length_min"]),
        default_notice=float(d["notice_hours"]),
        stale_after_days=int(d["stale_after_days"]),
        max_names=int(d["max_names"]),
        order=d["order"],
        regular_min_visits=int(d.get("regular_min_visits", 3)),
        max_offers_per_week=int(d.get("max_offers_per_week", 0)),
        mornings_before=_hhmm(tw["mornings_before"]),
        afternoons_from=_hhmm(tw["afternoons_from"]),
        evenings_from=_hhmm(tw["evenings_from"]),
        lunch_from=_hhmm(tw["lunch_from"]),
        lunch_until=_hhmm(tw["lunch_until"]),
        quick_notice=float(tw["quick_notice_hours"]),
        nicknames={k.lower(): v.lower() for k, v in raw.get("nicknames", {}).items()},
        routing=[Rule(name, r["tag"].strip().lower(), list(r["words"]), r["chip"])
                 for name, r in raw.get("routing", DEFAULT_ROUTING).items()],
        health_words=list(raw.get("health_words", [])),
    )
