"""Small helpers that turn messy notebook text into comparable values: phones, dates, names."""
import re
import unicodedata
from datetime import date

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "august": 8, "september": 9,
    "october": 10, "november": 11, "december": 12,
}
MONTH_RE = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"


def fold(text):
    """Lowercase, accents removed, single spaces: 'Josée  Landry' -> 'josee landry'."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text.lower()).strip()


def normalise_phone(text):
    """Digits only, 10 long (a leading 1 is dropped). Returns None if it isn't a usable number."""
    digits = re.sub(r"\D", "", text or "")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits if len(digits) == 10 else None


def is_same_number_marker(text):
    """'same #', 'same number', 'same no.' mean: same phone as this person's earlier line."""
    return bool(re.fullmatch(r"\s*same\s*(#|number|no\.?|num)\s*", (text or "").lower()))


def resolve_year(month, day, run_date):
    """Notebook dates have no year. Use the run date's year, or the year before if that lands in the future."""
    candidate = date(run_date.year, month, day)
    if candidate > run_date:
        candidate = date(run_date.year - 1, month, day)
    return candidate


def parse_added_date(text, run_date):
    """'Jul 6', '7/14', 'Sept 1', '10/19' -> date. Returns None if it can't be read."""
    t = fold(text).replace(".", "")
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?", t)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        if m.group(3):
            year = int(m.group(3))
            return date(year + 2000 if year < 100 else year, month, day)
        return resolve_year(month, day, run_date)
    m = re.fullmatch(rf"({MONTH_RE})\s+(\d{{1,2}})(?:,?\s*(\d{{4}}))?", t)
    if m:
        month, day = MONTHS[m.group(1)], int(m.group(2))
        if m.group(3):
            return date(int(m.group(3)), month, day)
        return resolve_year(month, day, run_date)
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", t)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


# ---------- names ----------

def name_parts(name):
    """'Lynn S.' -> ('lynn', 's'); 'Anne-Marie Leger' -> ('anne-marie', 'leger'); 'Kim' -> ('kim', None)."""
    tokens = [t.strip(".") for t in fold(name).split(" ") if t.strip(".")]
    if not tokens:
        return None, None
    return tokens[0], (tokens[-1] if len(tokens) > 1 else None)


def first_names_match(a, b, nicknames):
    if not a or not b:
        return False
    if a == b:
        return True
    ca, cb = nicknames.get(a, a), nicknames.get(b, b)
    if ca == cb or ca == b or cb == a:
        return True
    # short forms that are the start of the long one: Jen/Jennifer, Steph/Stephanie, Mel/Melanie
    short, long_ = sorted((a, b), key=len)
    return len(short) >= 3 and long_.startswith(short)


def last_names_match(a, b):
    """Equal, or one is just the initial of the other ('S' vs 'Savoie'). Missing counts as compatible."""
    if not a or not b:
        return True
    if a == b:
        return True
    if len(a) == 1 or len(b) == 1:
        return a[0] == b[0]
    return False


def names_compatible(name_a, name_b, nicknames):
    """Could these two notebook names be the same person? (A1 decision: first name + last name/initial.)"""
    fa, la = name_parts(name_a)
    fb, lb = name_parts(name_b)
    return first_names_match(fa, fb, nicknames) and last_names_match(la, lb)


def names_match_strictly(name_a, name_b, nicknames):
    """Used against the booking export: first name equivalent AND the same full last name."""
    fa, la = name_parts(name_a)
    fb, lb = name_parts(name_b)
    if not la or not lb or len(la) == 1 or len(lb) == 1:
        return False
    return la == lb and first_names_match(fa, fb, nicknames)


def fullest_name(names):
    """Pick the most complete spelling of a person's name from their lines."""
    return max(names, key=lambda n: (len((name_parts(n)[1] or "")), len(n)))
