"""The fill-in card on the review screen: what a held person can take, as the desk reads it from the book.
Saving it is a "start over" entry (plan §7.4): the person's older lines stop counting for what they can take,
and they keep their place in the queue. Builds the same fields the note parser produces (LineSpec)."""
from datetime import date, time

from kettle.config import PRENATAL_TAG
from kettle.core.parse_notes import LineSpec
from webapp.pages import CONTACT_CHOICES, DAYS, NOTICE_CHOICES

LENGTHS = ("30", "45", "60", "90")
NOTICES = {v for v, _ in NOTICE_CHOICES if v and v != "day"}
CONTACTS = {v for v, _ in CONTACT_CHOICES if v}


class CardError(ValueError):
    """Something on the card can't be saved; the message says what to fix."""


def prefill_from_record(rec, config):
    """The card as far as the person's lines could be read (a person record from the database)."""
    names = set(config.therapists)
    allowed, excluded = set(rec["therapists_allowed"]), set(rec["excluded"])
    if rec["prenatal_only"] or rec["female_only"]:
        who, only, but = "any", set(), set()
    elif excluded:
        who, only, but = "but", set(), excluded
    elif allowed != names:
        who, only, but = "only", allowed, set()
    else:
        who, only, but = "any", set(), set()
    days = set(rec["days"] or []) or (set(DAYS) - set(rec["days_excluded"]) if rec["days_excluded"] else set())
    notice = "day" if rec["day_before"] else f"{rec['notice_hours']:g}"
    needs = set(rec.get("needs", [])) | ({PRENATAL_TAG} if rec["prenatal_only"] else set())
    return {"who": who, "only": only, "but": but, "female": rec["female_only"], "needs": needs,
            "lengths": set(rec["lengths"]), "days": days, "from": rec["earliest_start"], "before": rec["start_before"],
            "done_by": rec["latest_end"], "notice": notice if notice == "day" or notice in NOTICES else "",
            "available_from": rec["available_from"], "available_until": rec["available_until"],
            "contact": rec["contact"] or "", "new_client": rec["new_client"]}


def prefill_from_form(form):
    """The card as it was sent, to show it again with what needs fixing."""
    def get(k):
        return form.get(k, [""])[0]
    return {"who": get("who") or "any", "only": set(form.get("only", [])), "but": set(form.get("but", [])),
            "female": bool(get("female")), "needs": set(form.get("needs", [])),
            "lengths": {int(x) for x in form.get("length", []) if x in LENGTHS}, "days": set(form.get("day", [])),
            "from": get("from"), "before": get("before"), "done_by": get("done_by"), "notice": get("notice"),
            "available_from": get("available_from"), "available_until": get("available_until"),
            "contact": get("contact"), "new_client": bool(get("new_client"))}


EMPTY_CARD = {"who": "any", "only": set(), "but": set(), "female": False, "needs": set(), "lengths": set(), "days": set(),
              "from": "", "before": "", "done_by": "", "notice": "", "available_from": "", "available_until": "",
              "contact": "", "new_client": False}
CARD_PARTS = (("therapists", ("who", "only", "but")), ("female only", ("female",)), ("routing", ("needs",)),
              ("length", ("lengths",)), ("days", ("days",)), ("time", ("from", "before", "done_by")),
              ("notice", ("notice",)), ("dates", ("available_from", "available_until")), ("contact", ("contact",)),
              ("new client", ("new_client",)))


def card_changes(old, new):
    """Which parts of a card differ, in plain words for its history ("therapists, notice"). Never the values:
    a routing change says "routing", not which rule."""
    def value(card, key):
        v = card.get(key)
        if key == "only" and card.get("who") != "only" or key == "but" and card.get("who") != "but":
            return set()
        return v if isinstance(v, (set, bool)) else (v or "")
    return [part for part, keys in CARD_PARTS if any(value(old, k) != value(new, k) for k in keys)]


def card_spec(form, config, rec):
    """The card -> a start-over LineSpec. Raises CardError with a plain message for anything unclear."""
    def get(k):
        return form.get(k, [""])[0].strip()
    names = set(config.therapists)
    spec = LineSpec(start_over=True, time_mentioned=True)
    who = get("who") or "any"
    only, but = set(form.get("only", [])) & names, set(form.get("but", [])) & names
    if who == "only":
        if not only:
            raise CardError("Tick at least one therapist under 'Only', or choose 'Any therapist'.")
        spec.therapists = only
    elif who == "but":
        if not but:
            raise CardError("Tick at least one therapist under 'Anyone but', or choose 'Any therapist'.")
        spec.therapists, spec.excluded = set(names), but
    else:
        spec.therapists = set(names)
    spec.female_only = bool(get("female"))
    spec.needs = set(form.get("needs", [])) & {rule.tag for rule in config.routing}
    spec.prenatal = PRENATAL_TAG in spec.needs
    spec.lengths = {int(x) for x in form.get("length", []) if x in LENGTHS} or None
    spec.days = set(form.get("day", [])) & set(DAYS) or None
    for field, attr, label in (("from", "earliest_start", "Starts from"), ("before", "start_before", "Starts before"),
                               ("done_by", "latest_end", "Done by")):
        if get(field):
            try:
                setattr(spec, attr, time.fromisoformat(get(field)[:5]))
            except ValueError:
                raise CardError(f"'{label}' isn't a time.") from None
    notice = get("notice")
    if notice == "day":
        spec.day_before = True
    elif notice:
        if notice not in NOTICES:
            raise CardError("Choose the notice from the list.")
        spec.notice = float(notice)
    for field, attr, label in (("available_from", "available_from", "Available from"),
                               ("available_until", "available_until", "Available until")):
        if get(field):
            try:
                setattr(spec, attr, date.fromisoformat(get(field)))
            except ValueError:
                raise CardError(f"'{label}' isn't a date.") from None
    if spec.available_from and spec.available_until and spec.available_from > spec.available_until:
        raise CardError("'Available from' is after 'Available until'.")
    if get("contact"):
        if get("contact") not in CONTACTS:
            raise CardError("Choose the contact from the list.")
        spec.contact = get("contact")
    spec.new_client = bool(get("new_client"))
    spec.regular_of = rec.get("regular_of")
    return spec
