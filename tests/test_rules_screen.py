"""Platform step 8 (platform-plan.md §7.2): the health routing rules screen. A new rule is a settings change:
check, before/after names, Marc's approval, a saved version, and the openings matched again. Works on a copy of
config/clinic.json, like the settings tests."""
import html
import json

from conftest import SAMPLE
from kettle import store
from test_offers import send
from test_settings import app, check, form_of, post, save, settings_of  # noqa: F401 (the app fixture)
from test_sync import waitlist_plus
from test_webapp import upload

THERAPISTS = ["Marc Cormier", "Dave Melanson", "Josée Landry", "Amira Haddad", "Kelsey Babineau", "Rachel Thibodeau"]


def rules_form(app, **changes):
    """The rules form as the browser sends it for the current settings, with some fields changed."""
    raw = settings_of(app)
    form = {}
    for i, (name, r) in enumerate(raw["routing"].items()):
        tagged = [n for n, t in raw["therapists"].items()
                  if r["tag"] in set(t.get("tags", [])) | ({"prenatal-trained"} if t["prenatal_trained"] else set())]
        form.update({f"r{i}_name": name, f"r{i}_tag": r["tag"], f"r{i}_words": ", ".join(r["words"]),
                     f"r{i}_chip": r["chip"], f"r{i}_therapists": tagged})
    form.update(changes)
    return {k: v for k, v in form.items() if v is not None}


def check_rules(app, **changes):
    return post(app, "/rules/check", rules_form(app, **changes))


POST_OP = {"new_name": "Post-op", "new_tag": "post-op-trained", "new_words": "post-op, post op, surger*",
           "new_chip": "Post-op-trained only", "new_therapists": ["Josée Landry"]}


def approve(app, page, name="Julie"):
    return post(app, "/settings/save", {"token": page.split("name=token value='")[1].split("'")[0],
                                        "checked_by": name, "approved": "yes"})


def test_the_screen_shows_the_pregnancy_rule_from_the_settings(app):
    page = html.unescape(send(app, "GET", "/rules")[2])
    assert "Prenatal" in page and "pregnan*, prenatal*, expecting*, trimester*, tri" in page
    assert "value='Amira Haddad' checked" in page and "value='Kelsey Babineau' checked" in page
    assert "value='Rachel Thibodeau' checked" not in page


def test_a_new_rule_needs_marcs_approval_and_then_routes_people(app, tmp_path):
    before = app.config_path.read_bytes()
    page = html.unescape(check_rules(app, **POST_OP)[2])
    assert "Rule added: Post-op (tag post-op-trained; words post-op, post op, surger*)" in page
    assert "Josée Landry: tags none → post-op-trained" in page
    assert "Marc has approved this change" in page and "apply to the book's lines on its next upload" in page
    status, _, text = post(app, "/settings/save", {"token": page.split("name=token value='")[1].split("'")[0],
                                                     "checked_by": "Julie"})
    assert status.startswith("400") and "needs Marc's approval" in html.unescape(text)
    assert app.config_path.read_bytes() == before  # nothing saved without it

    page = check_rules(app, **POST_OP)[2]
    status, headers, _ = approve(app, page)
    assert status.startswith("303") and dict(headers)["Location"] == "/rules?saved=1"
    raw = settings_of(app)
    assert raw["routing"]["Post-op"]["tag"] == "post-op-trained"
    assert raw["therapists"]["Josée Landry"]["tags"] == ["post-op-trained"]
    saved = store.settings_versions(store.connect(app.db_path))[0]["changes"]
    assert any(c.startswith("Rule added: Post-op") for c in saved)

    # the next upload of the book reads the new words: Ann only sees Josée, and the reason isn't kept
    book = waitlist_plus(tmp_path, ("10/20", "Ann Roy", "506-555-0902", "any - 60 - surgery on her knee in Sept"))
    upload(app, waitlist=book)
    ann = next(p for p in store.latest_run(store.connect(app.db_path))["people"] if 61 in p["lines"])
    assert ann["needs"] == ["post-op-trained"] and ann["therapists_allowed"] == ["Josée Landry"]
    assert "surger" not in store.connect(app.db_path).execute(
        "SELECT spec FROM waitlist_lines WHERE line = 61").fetchone()[0]


def test_a_rule_with_a_tag_nobody_has_or_a_bad_tag_is_refused(app):
    page = html.unescape(check_rules(app, **{**POST_OP, "new_therapists": None})[2])
    assert "no therapist has the tag 'post-op-trained'" in page
    page = html.unescape(check_rules(app, **{**POST_OP, "new_tag": "Post Op!"})[2])
    assert "one word: letters, numbers and dashes" in page
    page = html.unescape(check_rules(app, **{**POST_OP, "new_words": "post-op, mornings"})[2])
    assert "'mornings' already means something" in page


def test_taking_a_tag_away_shows_the_names_it_changes(app):
    page = html.unescape(check_rules(app, r0_therapists=["Kelsey Babineau"])[2])  # Amira no longer prenatal-trained
    assert "Amira Haddad: prenatal-trained yes → no" in page and "would show different names" in page
    assert "Marc has approved this change" in page


def test_a_private_word_is_added_and_then_dropped_not_held(app, tmp_path):
    book = waitlist_plus(tmp_path, ("10/20", "Gilles Probe", "506-555-0199", "any - 1hr - AM - shingles"))
    upload(app, waitlist=book)
    held = lambda: next(p for p in store.latest_run(store.connect(app.db_path))["people"] if 61 in p["lines"])  # noqa
    assert held()["status"] == "review"
    approve(app, check_rules(app, health_add="shingles")[2])
    assert settings_of(app)["health_words"] == ["shingles"]
    upload(app, waitlist=book)  # the book read again with the new word
    assert held()["status"] == "active"


def test_the_fill_in_card_has_a_chip_per_rule(app):
    approve(app, check_rules(app, **POST_OP)[2])
    form = send(app, "GET", "/review/fill?line=10")[2]  # Sarah Collette: prenatal
    assert "name=needs value='prenatal-trained' checked" in form
    assert "name=needs value='post-op-trained'>" in form and "Post-op-trained only (desk only" in form


def test_a_tag_no_rule_uses_is_an_ordinary_setting(app):
    page = html.unescape(check(app, new_name="Sophie Martin", new_aliases="sophie", new_female="yes")[2])
    assert "Marc has approved" not in page  # "female" isn't a health routing tag
    page = html.unescape(check(app, **{"t5_prenatal": "yes"})[2])  # Rachel prenatal-trained: changes routing
    assert "Marc has approved" in page
