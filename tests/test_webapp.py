"""Platform step 2 (platform-plan.md §4.1, §8): upload with a check before saving, the opening queue, downloads
and the sync log. The app is called the way the server calls it, with no network."""
import html
import io
import re
from datetime import date
from pathlib import Path
from wsgiref.util import setup_testing_defaults

import pytest

from conftest import SAMPLE
from test_privacy_and_unseen import HEALTH_WORDS
from test_sync import appointments_where, waitlist_plus
from webapp import pages
from webapp.app import Platform, parse_multipart

BOUNDARY = "----kettle-test"


def multipart(run_date="2026-10-21", **files):
    """A form as the browser sends it: the three file inputs (empty when not chosen) and the run date."""
    parts = [f'--{BOUNDARY}\r\nContent-Disposition: form-data; name="run_date"\r\n\r\n{run_date}\r\n'.encode()]
    for kind in ("waitlist", "appointments", "openings"):
        path = files.get(kind)
        name, data = (Path(path).name, Path(path).read_bytes()) if path else ("", b"")
        parts.append(f'--{BOUNDARY}\r\nContent-Disposition: form-data; name="{kind}"; filename="{name}"\r\n'
                     f"Content-Type: text/csv\r\n\r\n".encode() + data + b"\r\n")
    return b"".join(parts) + f"--{BOUNDARY}--\r\n".encode(), f"multipart/form-data; boundary={BOUNDARY}"


def call(app, method, path, body=b"", content_type="", host="localhost:8000", origin=None):
    environ = {}
    setup_testing_defaults(environ)
    environ.update({"REQUEST_METHOD": method, "PATH_INFO": path.partition("?")[0],
                    "QUERY_STRING": path.partition("?")[2], "HTTP_HOST": host, "CONTENT_TYPE": content_type,
                    "CONTENT_LENGTH": str(len(body)), "wsgi.input": io.BytesIO(body)})
    if origin:
        environ["HTTP_ORIGIN"] = origin
    seen = {}

    def start_response(status, headers):
        seen["status"], seen["headers"] = status, dict(headers)
    out = b"".join(app(environ, start_response))
    return seen["status"], seen["headers"], out.decode("utf-8")


def token_of(page):
    return re.search(r"name=token value='([^']+)'", page).group(1)


def upload(app, run_date="2026-10-21", **files):
    """Check, then save. Returns (check page, where the save went)."""
    body, ctype = multipart(run_date, **files)
    status, _, page = call(app, "POST", "/upload/check", body, ctype)
    assert status.startswith("200"), page
    status, headers, _ = call(app, "POST", "/upload/save", f"token={token_of(page)}".encode(),
                              "application/x-www-form-urlencoded")
    assert status.startswith("303")
    return page, headers["Location"]


@pytest.fixture
def app(tmp_path):
    return Platform(tmp_path / "data" / "kettle.db", tmp_path / "out", today=lambda: date(2026, 10, 21))


def test_an_empty_database_says_how_to_start(app):
    assert "Nothing has been uploaded yet" in call(app, "GET", "/")[2]
    assert "This is the first upload" in call(app, "GET", "/upload")[2]
    assert "No syncs yet" in call(app, "GET", "/log")[2]


def test_the_check_shows_what_will_change_and_saves_nothing(app):
    body, ctype = multipart(**SAMPLE)
    status, _, page = call(app, "POST", "/upload/check", body, ctype)
    assert status.startswith("200")
    assert "Nothing has been saved yet" in page
    assert "60 lines · new lines: 1-60" in page and "595 rows" in page and "44 openings · new: 44" in page
    assert "45 people: 30 active, 15 out of date, 0 held for review" in page
    assert "Openings to match:</b> 44 (34 with names)" in page
    assert not app.db_path.exists() and not app.out_dir.exists()


def test_saving_fills_the_database_and_shows_the_openings(app, sample):
    _, location = upload(app, **SAMPLE)
    assert location == "/?saved=1"
    page = call(app, "GET", location)[2]
    assert "Saved sync #1" in page and "44 openings: 34 with names, 10 with nobody" in page
    o01 = page[page.index("Mon Sep 21 · 12:30"):page.index("Tue Sep 22 · 11:00")]
    assert "Amanda Bourgeois" in o01 and "506-555-0125" in o01 and "line 42" in o01 and "ask Josée first" in o01
    assert "Not offered: <b>Gisele Maillet</b>" in o01
    assert "No-show: never offered" in page
    # the same output files as run.py
    assert (app.out_dir / "matches.csv").read_bytes() == (sample["out"] / "matches.csv").read_bytes()
    status, headers, csv_text = call(app, "GET", "/files/matches.csv")
    assert status.startswith("200") and headers["Content-Type"].startswith("text/csv")
    assert csv_text == (sample["out"] / "matches.csv").read_bytes().decode("utf-8")


def test_the_sync_log_names_the_files_not_their_contents(app):
    upload(app, **SAMPLE)
    page = call(app, "GET", "/log")[2]
    assert "waitlist-2026-10-21.csv" in page and "new 1-60" in page
    assert "works at the bank" not in page
    report = (app.out_dir / "preprocess-report.txt").read_text(encoding="utf-8")
    assert "waitlist: waitlist-2026-10-21.csv" in report  # the uploaded name, not a temporary path


def test_a_file_that_cant_be_read_stops_with_nothing_saved(app, tmp_path):
    bad = tmp_path / "appointments.csv"
    bad.write_text("appointment_id,date\nA-1,2026-10-29\n", encoding="utf-8")
    body, ctype = multipart(waitlist=SAMPLE["waitlist"], appointments=str(bad))
    status, _, page = call(app, "POST", "/upload/check", body, ctype)
    assert status.startswith("400") and "Nothing was saved" in page and "missing column" in page
    assert not app.pending and not app.db_path.exists()


def test_the_first_upload_needs_the_waitlist(app):
    body, ctype = multipart(openings=SAMPLE["openings"])
    page = call(app, "POST", "/upload/check", body, ctype)[2]
    assert "first sync needs the waitlist" in page


def test_no_files_or_a_bad_date_are_refused(app):
    body, ctype = multipart()
    assert "Choose at least one file" in call(app, "POST", "/upload/check", body, ctype)[2]
    body, ctype = multipart(run_date="soon", waitlist=SAMPLE["waitlist"])
    assert "run date isn't a date" in html.unescape(call(app, "POST", "/upload/check", body, ctype)[2])


def test_a_cancelled_or_unknown_check_cant_be_saved(app):
    body, ctype = multipart(**SAMPLE)
    token = token_of(call(app, "POST", "/upload/check", body, ctype)[2])
    form = "application/x-www-form-urlencoded"
    assert call(app, "POST", "/upload/cancel", f"token={token}".encode(), form)[0].startswith("303")
    status, _, page = call(app, "POST", "/upload/save", f"token={token}".encode(), form)
    assert status.startswith("400") and "expired or was already saved" in page
    assert not app.db_path.exists() or "No syncs yet" in call(app, "GET", "/log")[2]


def test_a_gap_in_the_booking_history_is_shown_before_and_after_saving(app, tmp_path):
    early = appointments_where(tmp_path, "early.csv", lambda r: r["date"] <= "2026-10-10")
    last_two_days = appointments_where(tmp_path, "two-days.csv", lambda r: r["date"] >= "2026-10-16")
    upload(app, waitlist=SAMPLE["waitlist"], appointments=early, openings=SAMPLE["openings"])
    check, _ = upload(app, "2026-10-30", appointments=last_two_days)
    assert "Gap in the booking history" in check and "no booking data for visits on Oct 12 to Oct 15" in check
    page = call(app, "GET", "/")[2]
    assert "no booking data for visits on Oct 12 to Oct 15" in page and "Run date Fri Oct 30" in page


def test_a_new_waitlist_line_is_added_on_the_next_upload(app, tmp_path):
    upload(app, **SAMPLE)
    book = waitlist_plus(tmp_path, ("10/20", "Paul Arsenault", "506-555-0190", "any - 60 - after 4"))
    check, _ = upload(app, waitlist=book)
    assert "61 lines · new lines: 61 · changed: none · already saved: 60" in check
    assert "46 people" in call(app, "GET", "/")[2]


def test_no_screen_shows_a_health_detail(app, tmp_path):
    book = waitlist_plus(tmp_path, ("10/20", "Gilles Probe", "506-555-0199", "any - 1hr - AM - shingles"))
    check, _ = upload(app, waitlist=book, appointments=SAMPLE["appointments"], openings=SAMPLE["openings"])
    screens = [check] + [call(app, "GET", p)[2] for p in ("/", "/log", "/upload", "/files/preprocess-report.txt",
                                                           "/files/matches.txt", "/files/sync-log.txt")]
    for page in screens:
        assert "shingles" not in page and HEALTH_WORDS.search(page) is None, HEALTH_WORDS.search(page)
    assert "1 held for review" in screens[1]


def test_names_and_reasons_are_escaped():
    opening = {"opening_id": "O1", "appointment_id": "A-1", "date": "2026-10-21", "start": "10:00", "therapist": "Dave Melanson",
               "length_min": 60, "hours_notice": 3.0, "kind": "late cancel", "cancelled_at": None, "heard_via": None}
    rows = [{"rank": 1, "person": "<script>x</script>", "line": 3, "can_take": "a & b", "flags": "<i>"}]
    html = pages.opening_card(opening, rows, {3: {"phone": "5065550101"}}, lambda n: n)
    assert "<script>" not in html and "&lt;script&gt;" in html and "a &amp; b" in html and "&lt;i&gt;" in html


def test_other_hosts_and_other_sites_are_refused(app):
    assert call(app, "GET", "/", host="evil.example")[0].startswith("403")
    body, ctype = multipart(**SAMPLE)
    assert call(app, "POST", "/upload/check", body, ctype, origin="http://evil.example")[0].startswith("403")
    assert call(app, "POST", "/upload/check", body, ctype, origin="http://localhost:8000")[0].startswith("200")


def test_only_the_output_files_can_be_downloaded(app):
    upload(app, **SAMPLE)
    for path in ("/files/kettle.db", "/files/../data/kettle.db", "/files/core/people.json", "/files/nothing.txt"):
        assert call(app, "GET", path)[0].startswith("404"), path
    assert call(app, "GET", "/files/sync-log.txt")[0].startswith("200")


def test_head_requests_get_headers_only(app):
    status, headers, body = call(app, "HEAD", "/")
    assert status.startswith("200") and body == "" and int(headers["Content-Length"]) > 0


def test_empty_file_inputs_are_left_out():
    body, ctype = multipart(waitlist=SAMPLE["waitlist"])
    fields, files = parse_multipart(body, ctype)
    assert fields == {"run_date": "2026-10-21"} and list(files) == ["waitlist"]
    assert files["waitlist"][1] == Path(SAMPLE["waitlist"]).read_bytes()
