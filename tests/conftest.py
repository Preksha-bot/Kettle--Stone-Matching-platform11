from datetime import date
from pathlib import Path

import pytest

from kettle.adapters.csv_in import WaitlistLine
from kettle.config import load_config
from kettle.core.normalise import normalise_phone, parse_added_date, is_same_number_marker
from kettle.core.parse_notes import NoteParser
from kettle.core.people import build_people
from kettle.pipeline import run

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = {
    "waitlist": str(ROOT / "waitlist-2026-10-21.csv"),
    "appointments": str(ROOT / "appointments-2026-09-21-to-2026-10-17.csv"),
    "openings": str(ROOT / "late-openings-2026-09-21-to-2026-10-17.csv"),
}
KEY = ROOT / "answer-key-tanya.csv"
SAMPLE_RUN_DATE = date(2026, 10, 21)


@pytest.fixture(scope="session")
def config():
    return load_config()


@pytest.fixture(scope="session")
def parser(config):
    return NoteParser(config)


@pytest.fixture(scope="session")
def sample(tmp_path_factory):
    """The whole pipeline on the sample files, run as of Oct 21 (the answer key's date)."""
    out = tmp_path_factory.mktemp("out")
    result = run(SAMPLE["waitlist"], SAMPLE["appointments"], SAMPLE["openings"], SAMPLE_RUN_DATE, out)
    result["out"] = out
    return result


def make_lines(rows, run_date=SAMPLE_RUN_DATE):
    """rows: (added, name, phone, notes) -> WaitlistLine list numbered from 1."""
    return [WaitlistLine(line=i, added_raw=a, added=parse_added_date(a, run_date), name=n, phone_raw=p,
                         phone=normalise_phone(p), same_number=is_same_number_marker(p), notes=t)
            for i, (a, n, p, t) in enumerate(rows, 1)]


def make_people(rows, config, bookings=(), run_date=SAMPLE_RUN_DATE, reviewed=None):
    lines = make_lines(rows, run_date)
    parser = NoteParser(config)
    specs = {l.line: parser.parse(l.notes, run_date) for l in lines}
    return build_people(lines, specs, list(bookings), run_date, config, reviewed)
