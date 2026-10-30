"""Platform step 4 (platform-plan.md §7.3): the settings screen. Every change is checked by the same settings
check every run uses, shows which names it changes before anything is saved, is kept as a version that can be
put back, and the openings are matched again. Plus the compare-orders view and the owner's pause switch.
Every test works on a copy of config/clinic.json: the real file is never touched."""
import html
import json
import shutil
from datetime import date
from urllib.parse import urlencode

import pytest

from conftest import SAMPLE
from kettle import store
from kettle.adapters.csv_in import InputError
from kettle.adapters.upload import sync
from kettle.config import DEFAULT_CONFIG, load_config
from test_review import decide
from test_webapp import call, multipart, token_of, upload
from webapp.app import Platform

FORM = "application/x-www-form-urlencoded"


@pytest.fixture
def app(tmp_path):
    config = tmp_path / "clinic.json"
    shutil.copyfile(DEFAULT_CONFIG, config)
    platform = Platform(tmp_path / "data" / "kettle.db", tmp_path / "out", config_path=config,
                        today=lambda: date(2026, 10, 21))
    upload(platform, **SAMPLE)
    return platform


def settings_of(app):
    return json.loads(app.config_path.read_text(encoding="utf-8"))


def form_of(raw, **changes):
    """The settings form as the browser sends it for `raw`, with some fields changed (None = unticked)."""
    d, tw = raw["defaults"], raw["time_words"]
    form = {k: d[k] for k in ("order", "max_names", "length_min", "notice_hours", "stale_after_days")}
    form["regular_min_visits"] = d.get("regular_min_visits", 3)
    form.update(tw)
    for i, (name, t) in enumerate(raw["therapists"].items()):
        form.update({f"t{i}_name": name, f"t{i}_aliases": ", ".join(t["aliases"]), f"t{i}_approval": t["approval"]})
        if t["female"]:
            form[f"t{i}_female"] = "yes"
        if t["prenatal_trained"]:
            form[f"t{i}_prenatal"] = "yes"
    form["nicknames"] = "\n".join(f"{k} = {v}" for k, v in raw["nicknames"].items())
    form.update(changes)
    return {k: v for k, v in form.items() if v is not None}


def post(app, path, form):
    return call(app, "POST", path, urlencode(form, doseq=True).encode(), FORM)


def check(app, **changes):
    return post(app, "/settings/check", form_of(settings_of(app), **changes))


def save(app, page, name="Julie"):
    return post(app, "/settings/save", {"token": token_of(page), "checked_by": name})


# ---------- check, then save ----------

def test_the_screen_shows_the_settings_file(app):
    page = call(app, "GET", "/settings")[2]
    assert "Josée Landry" in page and "value='first-asked' checked" in page and "bob = robert" in page


def test_an_unchanged_form_saves_nothing(app):
    page = check(app)[2]
    assert "Nothing changed" in page and "Saved versions" not in page


def test_a_change_shows_which_names_change_before_anything_is_saved(app):
    before = app.config_path.read_bytes()
    status, _, page = check(app, notice_hours="3")
    assert status.startswith("200") and "Nothing has been saved yet" in page
    assert "Notice when not written (h): 2.0 → 3.0" in page
    assert "would show different names" in page and "O01 · Mon Sep 21 12:30 · Josée" in page
    assert app.config_path.read_bytes() == before
    assert not store.settings_versions(store.connect(app.db_path))


def test_saving_writes_the_file_keeps_versions_and_matches_again(app):
    original = settings_of(app)
    status, headers, _ = save(app, check(app, notice_hours="3")[2])
    assert status.startswith("303") and headers["Location"] == "/settings?saved=1"
    assert settings_of(app)["defaults"]["notice_hours"] == 3.0
    assert load_config(app.config_path).default_notice == 3.0  # the file still passes the settings check
    con = store.connect(app.db_path)
    versions = store.settings_versions(con)
    assert [v["changes"] for v in versions] == [["Notice when not written (h): 2.0 → 3.0"], []]
    assert versions[1]["settings"] == original  # the settings before the first change, so they can be put back
    assert store.latest_run(con)["summary"]["note"].startswith("settings changed: Notice")

    page = post(app, "/settings/restore", {"id": versions[1]["id"]})[2]
    assert "Notice when not written (h): 3.0 → 2.0" in page
    save(app, page)
    assert settings_of(app) == original


def test_mistakes_are_named_and_nothing_is_saved(app):
    before = app.config_path.read_bytes()
    raw = settings_of(app)
    rachel = list(raw["therapists"]).index("Rachel Thibodeau")
    for changes, problem in (({f"t{rachel}_aliases": "rachel, r, j"}, "short form 'j' is used for both"),
                             ({"max_names": "5"}, "can't be more than 3"),
                             ({"nicknames": "bob robert"}, "write it as short = full"),
                             ({"lunch_from": "14:00"}, "'lunch_from' must be earlier than 'lunch_until'"),
                             ({"stale_after_days": "soon"}, "'stale_after_days' must be a whole number"),
                             ({"new_name": "Sophie"}, "first and last name")):
        status, _, page = check(app, **changes)
        assert status.startswith("400") and problem in html.unescape(page), problem
    assert app.config_path.read_bytes() == before


def test_adding_and_removing_a_therapist(app):
    page = check(app, new_name="Sophie Martin", new_aliases="Sophie, so", new_female="yes")[2]
    assert "Therapist added: Sophie Martin" in page
    save(app, page)
    assert settings_of(app)["therapists"]["Sophie Martin"] == {"aliases": ["sophie", "so"], "female": True,
                                                               "prenatal_trained": False, "approval": "none"}
    dave = list(settings_of(app)["therapists"]).index("Dave Melanson")
    page = check(app, **{f"t{dave}_remove": "yes"})[2]
    assert "Therapist removed: Dave Melanson" in page and "O04 · Tue Sep 22 12:15 · Dave Melanson" in page


def people_by_line(app):
    con = store.connect(app.db_path)
    return {line: p for p in store.latest_run(con)["people"] for line in p["lines"]}


def test_a_note_that_said_any_follows_the_therapist_list(app):
    """'any' is kept as 'any', not as the six names of the day: a new therapist is included, a removed one isn't."""
    assert '"therapists": "any"' in store.connect(app.db_path).execute(
        "SELECT spec FROM waitlist_lines WHERE line = 39").fetchone()[0]  # Joel Bertin: "any - 30 or 45 - ..."
    save(app, check(app, new_name="Sophie Martin", new_aliases="sophie")[2])
    assert "Sophie Martin" in people_by_line(app)[39]["therapists_allowed"]


def test_removing_a_therapist_holds_only_the_people_who_asked_for_them(app):
    dave = list(settings_of(app)["therapists"]).index("Dave Melanson")
    save(app, check(app, **{f"t{dave}_remove": "yes"})[2])
    people = people_by_line(app)
    terry = people[3]  # Terry Hebert: "Dave only" (out of date anyway, so stale wins)
    assert "line 3: names a therapist who is no longer in the settings, check the notebook" in terry["reasons"]
    normand = people[4]  # Normand Vienneau: "Dave only"
    assert normand["status"] == "review"
    joel = people[39]    # "any": still active, and no longer offered Dave
    assert joel["status"] == "active" and "Dave Melanson" not in joel["therapists_allowed"]


def test_a_new_order_changes_who_is_shown_first(app):
    page = check(app, order="shortest-notice")[2]
    assert "Order: whoever asked first → whoever can come at the shortest notice" in page
    assert "would show different names" in page
    save(app, page)
    assert "order: shortest-notice" in call(app, "GET", "/")[2]


def test_a_file_changed_outside_the_screen_is_pointed_out(app):
    save(app, check(app, notice_hours="3")[2])
    raw = settings_of(app)
    raw["defaults"]["stale_after_days"] = 90
    app.config_path.write_text(json.dumps(raw), encoding="utf-8")
    assert "changed outside this screen" in call(app, "GET", "/settings")[2]


def test_the_name_is_required_and_never_shown(app):
    page = check(app, notice_hours="3")[2]
    assert "Write your name" in save(app, page, name=" ")[2]
    save(app, check(app, notice_hours="3")[2], name="Zelda Quist")
    seen = [call(app, "GET", p)[2] for p in ("/", "/settings", "/log", "/review")]
    files = [f.read_text(encoding="utf-8") for f in app.out_dir.rglob("*") if f.is_file()]
    assert not any("Zelda" in text for text in seen + files)


# ---------- compare orders ----------

def test_compare_orders_shows_each_order_and_everyone_who_fits(app):
    page = call(app, "GET", "/")[2]
    assert "/compare?opening=A-24010" in page
    page = html.unescape(call(app, "GET", "/compare?opening=A-24010")[2])  # O01, Josée Mon Sep 21 12:30
    assert "4 people fit this opening" in page  # Tanya's list for O01: Joel, Amanda, Nicole, Lise
    for order in ("first-asked", "shortest-notice", "regulars-first"):
        assert f"<b>{order}</b>" in page
    shortest = page[page.index("<b>shortest-notice</b>"):page.index("<b>regulars-first</b>")]
    assert shortest.index("Joel Bertin") < shortest.index("Amanda Bourgeois") and "0.5 h notice" in shortest
    assert call(app, "GET", "/compare?opening=nothing")[0].startswith("404")


# ---------- the owner's switch ----------

def test_pausing_stops_uploads_and_decisions_until_switched_back_on(app, tmp_path):
    assert "Write your name" in post(app, "/settings/pause", {"action": "pause", "checked_by": ""})[2]
    post(app, "/settings/pause", {"action": "pause", "checked_by": "Marc"})
    page = call(app, "GET", "/")[2]
    assert "The platform is paused" in page
    body, ctype = multipart(openings=SAMPLE["openings"])
    assert "paused" in call(app, "POST", "/upload/check", body, ctype)[2]
    assert decide(app, "take off|61|")[0].startswith("409")
    with pytest.raises(InputError, match="paused"):
        sync(app.db_path, date(2026, 10, 21), openings=SAMPLE["openings"], out_dir=tmp_path / "o")  # sync.py too
    save(app, check(app, notice_hours="3")[2])  # settings can still be fixed while paused
    assert settings_of(app)["defaults"]["notice_hours"] == 3.0
    post(app, "/settings/pause", {"action": "resume", "checked_by": "Marc"})
    assert "The platform is paused" not in call(app, "GET", "/")[2]
    assert call(app, "POST", "/upload/check", body, ctype)[0].startswith("200")
