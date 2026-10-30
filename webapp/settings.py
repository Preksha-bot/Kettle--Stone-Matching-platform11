"""The settings screen's logic (platform-plan.md §7.3): the form <-> config/clinic.json, the extra checks the
screen adds to the settings check, and what changed in plain words. config/clinic.json stays the file the
matcher reads (run.py, sync.py and the screens); every save from the screen is also kept as a version in the
database, so any version can be put back."""
import copy
import json
import os
import tempfile
from pathlib import Path

import re

from kettle.config import DEFAULT_ROUTING, FEMALE_TAG, PRENATAL_TAG, check_settings, therapist_tags
from kettle.core.match import ORDERS

ORDER_WORDS = {"first-asked": "whoever asked first",
               "shortest-notice": "whoever can come at the shortest notice",
               "regulars-first": "regulars of that therapist first, then whoever asked first"}
APPROVAL_WORDS = {"none": "takes anyone", "see_first": "ask first"}
DEFAULT_WORDS = {"order": "Order", "max_names": "Names shown per opening", "length_min": "Length when not written",
                 "notice_hours": "Notice when not written (h)", "stale_after_days": "Out of date after (days)",
                 "regular_min_visits": "Regular after (visits)",
                 "max_offers_per_week": "Offers per person per week (0 = no limit)"}
TIME_WORDS = {"mornings_before": "Mornings start before", "afternoons_from": "Afternoons start from",
              "evenings_from": "Evenings start from", "lunch_from": "Lunch from", "lunch_until": "Lunch until",
              "quick_notice_hours": "'Can come quick' means (h)"}
MAX_NAMES = 3  # the clinic's ground rule: never more than 3 names


def read_file(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_file(path, raw):
    """Writes the settings atomically: a half-written file can't be left behind for the matcher."""
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".clinic-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(raw, indent=2, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def _number(text, whole):
    """A form value as a number, or the text itself so the settings check names the mistake."""
    try:
        value = float(text)
    except (TypeError, ValueError):
        return text
    return int(value) if whole and value.is_integer() else value


def form_to_settings(form, current):
    """The settings form -> a settings dict like config/clinic.json, starting from `current` (so comments and
    anything the form doesn't show are kept). Returns (settings, problems the form itself shows)."""
    def get(k):
        return form.get(k, [""])[0].strip()
    raw, problems = copy.deepcopy(current), []
    d = raw.setdefault("defaults", {})
    d["order"] = get("order")
    for key in ("max_names", "length_min", "stale_after_days", "regular_min_visits"):
        d[key] = _number(get(key), whole=True)
    d["notice_hours"] = _number(get("notice_hours"), whole=False)
    if "max_offers_per_week" in form:
        d["max_offers_per_week"] = _number(get("max_offers_per_week"), whole=True)
    tw = raw.setdefault("time_words", {})
    for key in ("mornings_before", "afternoons_from", "evenings_from", "lunch_from", "lunch_until"):
        tw[key] = get(key)[:5]
    tw["quick_notice_hours"] = _number(get("quick_notice_hours"), whole=False)

    therapists, i = {}, 0
    while f"t{i}_name" in form:
        name = get(f"t{i}_name")
        if not get(f"t{i}_remove"):
            therapists[name] = _therapist(get, f"t{i}_")
        i += 1
    new_name = " ".join(get("new_name").split())
    if new_name:
        if new_name in therapists or new_name in current.get("therapists", {}):
            problems.append(f"There is already a therapist called {new_name}.")
        elif len(new_name.split()) < 2:
            problems.append("Give the new therapist's first and last name, as Kneadly shows it.")
        else:
            therapists[new_name] = _therapist(get, "new_")
    raw["therapists"] = therapists

    nicknames = {}
    for n, text in enumerate(form.get("nicknames", [""])[0].splitlines(), 1):
        if not text.strip():
            continue
        short, sep, full = text.partition("=")
        if not sep or not short.strip() or not full.strip():
            problems.append(f"Nicknames, line {n}: write it as short = full, e.g. bob = robert.")
            continue
        nicknames[short.strip().lower()] = full.strip().lower()
    raw["nicknames"] = nicknames
    return raw, problems


def _therapist(get, prefix):
    t = {"aliases": [a.strip().lower() for a in get(prefix + "aliases").split(",") if a.strip()],
         "female": bool(get(prefix + "female")), "prenatal_trained": bool(get(prefix + "prenatal")),
         "approval": get(prefix + "approval") or "none"}
    tags = _words(get(prefix + "tags"))
    if tags:
        t["tags"] = tags
    return t


def _words(text):
    """'post-op, Surger*' -> ['post-op', 'surger*']: comma- or line-separated, lowercase, no repeats."""
    return list(dict.fromkeys(w.strip().lower() for w in re.split(r"[,\n]", text or "") if w.strip()))


def other_tags(t):
    """A therapist's tags besides the two built-in yes/no ones (female, prenatal-trained)."""
    return sorted(therapist_tags(t) - {FEMALE_TAG, PRENATAL_TAG})


def set_tag(t, tag, on):
    """Gives a therapist (as in the settings file) a tag, or takes it away."""
    if tag == PRENATAL_TAG:
        t["prenatal_trained"] = on
    elif tag == FEMALE_TAG:
        t["female"] = on
    else:
        tags = set(t.get("tags", [])) | {tag} if on else set(t.get("tags", [])) - {tag}
        if tags:
            t["tags"] = sorted(tags)
        else:
            t.pop("tags", None)


def routing_of(raw):
    return raw.get("routing", DEFAULT_ROUTING)


def rules_to_settings(form, current):
    """The rules form -> settings, starting from `current`: each rule's words, card label and therapists (who get
    its tag), a new rule, and extra private words (only added here; removing one needs a developer).
    Returns (settings, problems the form itself shows)."""
    def get(k):
        return form.get(k, [""])[0].strip()
    raw, problems, routing = copy.deepcopy(current), [], {}
    names = list(raw.get("therapists", {}))
    i = 0
    while f"r{i}_name" in form:
        name, tag = get(f"r{i}_name"), get(f"r{i}_tag")
        if not get(f"r{i}_remove"):
            routing[name] = {"tag": tag, "words": _words(get(f"r{i}_words")), "chip": get(f"r{i}_chip")}
            ticked = set(form.get(f"r{i}_therapists", []))
            for n in names:
                set_tag(raw["therapists"][n], tag, n in ticked)
        i += 1
    new_name = " ".join(get("new_name").split())
    if new_name:
        tag = get("new_tag").lower()
        if new_name in routing or new_name in routing_of(current):
            problems.append(f"There is already a rule called {new_name}.")
        elif not re.fullmatch(r"[a-z0-9][a-z0-9-]*", tag):
            problems.append("The new rule's tag must be one word: letters, numbers and dashes, e.g. post-op-trained.")
        elif tag in {r["tag"] for r in routing.values()}:
            problems.append(f"Another rule already uses the tag '{tag}'.")
        else:
            routing[new_name] = {"tag": tag, "words": _words(get("new_words")), "chip": get("new_chip")}
            ticked = set(form.get("new_therapists", []))
            for n in names:
                set_tag(raw["therapists"][n], tag, n in ticked)
    raw["routing"] = routing
    raw["health_words"] = list(dict.fromkeys(current.get("health_words", []) + _words(get("health_add"))))
    return raw, problems


def rules_changed(old, new):
    """True when the routing rules, the private words, or who has a rule's tag differ: Marc approves those.
    (A tag no rule uses, like "female", is an ordinary setting.)"""
    routed = {r["tag"] for r in list(routing_of(old).values()) + list(routing_of(new).values())}

    def tagged(raw):
        return {n: therapist_tags(t) & routed for n, t in raw.get("therapists", {}).items()}
    before, after = tagged(old), tagged(new)
    return (routing_of(old) != routing_of(new) or old.get("health_words", []) != new.get("health_words", [])
            or any(before.get(n, set()) != after.get(n, set()) for n in set(before) | set(after)))


def problems_with(raw):
    """The settings check (kettle/config.py, the same one every run uses) plus the screen's own rules."""
    problems = check_settings(raw)
    max_names = raw.get("defaults", {}).get("max_names")
    if isinstance(max_names, int) and max_names > MAX_NAMES:
        problems.append(f"Names shown per opening can't be more than {MAX_NAMES}.")
    if not raw.get("therapists"):
        problems.append("There has to be at least one therapist.")
    return problems


def changes(old, new):
    """What differs between two versions of the settings, in plain words."""
    out = []
    od, nd = old.get("defaults", {}), new.get("defaults", {})
    for key, label in DEFAULT_WORDS.items():
        if od.get(key) != nd.get(key):
            before, after = od.get(key), nd.get(key)
            if key == "order":
                before, after = ORDER_WORDS.get(before, before), ORDER_WORDS.get(after, after)
            out.append(f"{label}: {before} → {after}")
    ot, nt = old.get("time_words", {}), new.get("time_words", {})
    out += [f"{label}: {ot.get(k)} → {nt.get(k)}" for k, label in TIME_WORDS.items() if ot.get(k) != nt.get(k)]
    oth, nth = old.get("therapists", {}), new.get("therapists", {})
    out += [f"Therapist added: {name}" for name in nth if name not in oth]
    out += [f"Therapist removed: {name}" for name in oth if name not in nth]
    for name in (n for n in nth if n in oth):
        a, b = oth[name], nth[name]
        if a.get("aliases") != b.get("aliases"):
            out.append(f"{name}: short forms {', '.join(a.get('aliases', [])) or 'none'} → "
                       f"{', '.join(b.get('aliases', [])) or 'none'}")
        for key, label in (("female", "female"), ("prenatal_trained", "prenatal-trained")):
            if a.get(key) != b.get(key):
                out.append(f"{name}: {label} {'yes' if a.get(key) else 'no'} → {'yes' if b.get(key) else 'no'}")
        if a.get("approval") != b.get("approval"):
            out.append(f"{name}: {APPROVAL_WORDS.get(a.get('approval'))} → {APPROVAL_WORDS.get(b.get('approval'))}")
        if other_tags(a) != other_tags(b):
            out.append(f"{name}: tags {', '.join(other_tags(a)) or 'none'} → {', '.join(other_tags(b)) or 'none'}")
    orr, nr = routing_of(old), routing_of(new)
    out += [f"Rule added: {n} (tag {r['tag']}; words {', '.join(r['words'])})" for n, r in nr.items() if n not in orr]
    out += [f"Rule removed: {n}" for n in orr if n not in nr]
    for n in (n for n in nr if n in orr):
        if orr[n].get("words") != nr[n].get("words"):
            out.append(f"Rule {n}: words {', '.join(orr[n].get('words', []))} → {', '.join(nr[n].get('words', []))}")
        if orr[n].get("chip") != nr[n].get("chip"):
            out.append(f"Rule {n}: card label {orr[n].get('chip')} → {nr[n].get('chip')}")
    added = [w for w in new.get("health_words", []) if w not in old.get("health_words", [])]
    if added:
        out.append(f"Private words added: {', '.join(added)}")
    removed = [w for w in old.get("health_words", []) if w not in new.get("health_words", [])]
    if removed:
        out.append(f"Private words removed: {', '.join(removed)}")
    on, nn = old.get("nicknames", {}), new.get("nicknames", {})
    out += [f"Nickname added: {k} = {v}" for k, v in nn.items() if on.get(k) != v]
    out += [f"Nickname removed: {k} = {v}" for k, v in on.items() if k not in nn]
    return out


def orders():
    return [(o, ORDER_WORDS[o]) for o in ORDERS]
