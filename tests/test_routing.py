"""Routing rules and therapist tags (platform-plan.md §7.2, technical plan §15 #2 and #8): a health rule is a
settings change, not a code change. A rule's words send a person only to therapists with its tag; only the tag
is kept, never the reason. The clinic's pregnancy rule now lives in the settings and behaves exactly as before."""
import copy
import json
import re
from datetime import date

import pytest

from conftest import SAMPLE, SAMPLE_RUN_DATE, make_people
from kettle.adapters.csv_in import read_waitlist
from kettle.config import DEFAULT_CONFIG, check_settings, load_config, word_pattern
from kettle.core.match import allowed_therapists, summary
from kettle.core.parse_notes import NoteParser

POST_OP = {"tag": "post-op-trained", "words": ["post-op", "post op", "surger*"], "chip": "Post-op-trained only"}


def settings(**changes):
    raw = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    raw = copy.deepcopy(raw)
    for key, value in changes.items():
        raw[key] = value
    return raw


def config_from(raw, tmp_path):
    path = tmp_path / "clinic.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return load_config(path)


def with_post_op(tmp_path):
    raw = settings()
    raw["routing"]["Post-op"] = POST_OP
    raw["therapists"]["Josée Landry"]["tags"] = ["post-op-trained"]
    return config_from(raw, tmp_path)


# ---------- the pregnancy rule, now in the settings ----------

def test_the_sample_routes_exactly_the_two_pregnant_clients(config):
    parser = NoteParser(config)
    routed = {l.line: parser.parse(l.notes, SAMPLE_RUN_DATE).needs
              for l in read_waitlist(SAMPLE["waitlist"], SAMPLE_RUN_DATE)}
    assert {line: needs for line, needs in routed.items() if needs} == {10: {"prenatal-trained"}, 40: {"prenatal-trained"}}


def test_a_file_without_a_routing_section_gets_the_same_rule(tmp_path, config):
    raw = settings()
    del raw["routing"]
    old_style = config_from(raw, tmp_path)
    assert [(r.tag, r.words) for r in old_style.routing] == [(r.tag, r.words) for r in config.routing]


def test_no_routing_rules_at_all_keeps_no_health_routing(tmp_path):
    """Marc's option (b), technical plan §16: keep no tag; the desk picks Amira or Kelsey directly."""
    cfg = config_from(settings(routing={}), tmp_path)
    s = NoteParser(cfg).parse("pregnant, 2nd tri - female - 60", SAMPLE_RUN_DATE)
    assert not s.needs and not s.prenatal and s.had_health_detail and s.female_only


# ---------- a new rule without code ----------

def test_a_new_rule_routes_people_to_the_tagged_therapist(tmp_path):
    cfg = with_post_op(tmp_path)
    s = NoteParser(cfg).parse("post-op shoulder - any - 60", SAMPLE_RUN_DATE)
    assert s.needs == {"post-op-trained"} and not s.unparsed
    person = make_people([("10/20", "Ann Roy", "506-555-0901", "any - 60 - surgery on knee in Sept")], cfg)[0]
    assert person.needs == {"post-op-trained"} and allowed_therapists(person, cfg) == {"Josée Landry"}
    from kettle.adapters.csv_in import Opening
    opening = Opening("O1", "A-1", date(2026, 10, 22), None, 60, "Josée Landry", "late cancel", None, 3.0)
    text = summary(person, opening, cfg)
    assert text.startswith("Josée") and "post" not in text and "surger" not in text  # never the reason


def test_a_start_over_line_drops_an_older_lines_routing_like_any_other_limit(tmp_path):
    cfg = with_post_op(tmp_path)
    person = make_people([("10/01", "Ann Roy", "506-555-0901", "post-op - any - 60"),
                          ("10/20", "Ann Roy", "506-555-0901", "start over - Rachel only - 60")], cfg)[0]
    assert person.needs == set() and allowed_therapists(person, cfg) == {"Rachel Thibodeau"}


def test_lines_saved_before_rules_existed_still_route_by_the_old_flag(config):
    person = make_people([("10/20", "Ann Roy", "506-555-0901", "any - 60")], config)[0]
    person.prenatal = True  # as a line saved in the database before "needs" existed
    assert allowed_therapists(person, config) == {"Amira Haddad", "Kelsey Babineau"}


def test_extra_private_words_are_dropped_not_held(tmp_path):
    held = NoteParser(load_config()).parse("any - 1hr - AM - shingles", SAMPLE_RUN_DATE)
    assert held.unparsed == ["shingles"]
    cfg = config_from(settings(health_words=["shingles"]), tmp_path)
    s = NoteParser(cfg).parse("any - 1hr - AM - shingles", SAMPLE_RUN_DATE)
    assert not s.unparsed and s.had_health_detail and s.start_before is not None


def test_words_match_whole_words_or_the_start_with_a_star():
    assert re.search(word_pattern("tri"), "2nd tri") and not re.search(word_pattern("tri"), "a trip")
    assert re.search(word_pattern("pregnan*"), "pregnant 30 wks") and re.search(word_pattern("Post-op"), "post-op knee")


# ---------- the settings check ----------

@pytest.mark.parametrize("change, problem", [
    (lambda raw: raw["routing"].update({"Post-op": POST_OP}), "no therapist has the tag 'post-op-trained'"),
    (lambda raw: raw["routing"].update({"X": {**POST_OP, "tag": "prenatal-trained", "words": ["dave"]}}),
     "'dave' is also a short form for Dave Melanson"),
    (lambda raw: raw["routing"].update({"X": {**POST_OP, "tag": "prenatal-trained", "words": ["mornings"]}}),
     "already means something in the book's shorthand"),
    (lambda raw: raw["routing"].update({"X": {**POST_OP, "tag": "prenatal-trained", "words": ["tri"]}}),
     "'tri' is also a word of rule 'Prenatal'"),
    (lambda raw: raw["routing"].update({"X": {"tag": "prenatal-trained", "words": [], "chip": "x"}}), "'words' must be"),
    (lambda raw: raw["therapists"]["Josée Landry"].update(tags="post-op"), "'tags' must be a list"),
    (lambda raw: raw.update(health_words="shingles"), "health_words: must be a list"),
])
def test_rule_mistakes_are_named(change, problem):
    raw = settings()
    change(raw)
    assert any(problem in p for p in check_settings(raw)), check_settings(raw)
