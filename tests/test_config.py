"""The settings check (plan §13 risk 7): a mistake in config/clinic.json stops the run before anything is matched."""
import copy
import json
from datetime import date

import pytest

from kettle.config import DEFAULT_CONFIG, ConfigError, check_settings, load_config
from kettle.core.parse_notes import NoteParser
from run import main

RAW = json.loads(DEFAULT_CONFIG.read_text(encoding="utf-8"))


def write(tmp_path, raw):
    path = tmp_path / "clinic.json"
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return path


def changed(edit):
    raw = copy.deepcopy(RAW)
    edit(raw)
    return raw


def add_melissa(aliases):
    def edit(raw):
        raw["therapists"]["Melissa Gallant"] = {"aliases": aliases, "female": True, "prenatal_trained": False,
                                                "approval": "none"}
    return edit


def test_clinic_settings_pass_the_check():
    assert check_settings(RAW) == []
    assert main(["--check-settings"]) == 0


def test_short_form_used_for_two_therapists_stops_the_run(tmp_path):
    with pytest.raises(ConfigError, match=r"short form 'm' is used for both Marc Cormier and Melissa Gallant"):
        load_config(write(tmp_path, changed(add_melissa(["melissa", "m"]))))


def test_short_form_removed_from_both_holds_notes_that_use_it(tmp_path):
    def edit(raw):
        add_melissa(["melissa"])(raw)
        raw["therapists"]["Marc Cormier"]["aliases"] = ["marc"]
    config = load_config(write(tmp_path, changed(edit)))
    assert NoteParser(config).parse("M only - 60 - Tues", date(2026, 10, 30)).unparsed


@pytest.mark.parametrize("edit,message", [
    (lambda raw: raw["therapists"]["Amira Haddad"].update(prenatal_traned=True), "unknown setting 'prenatal_traned'"),
    (lambda raw: raw["therapists"]["Dave Melanson"].update(approval="ask"), "'approval' must be one of"),
    (lambda raw: raw["therapists"]["Dave Melanson"].update(female="no"), "'female' must be true or false"),
    (lambda raw: raw["time_words"].update(mornings_before="25:00"), "'mornings_before' is '25:00', not a time"),
    (lambda raw: raw["time_words"].update(lunch_until="11:00"), "'lunch_from' must be earlier"),
    (lambda raw: raw["defaults"].update(max_names=0), "'max_names' must be a whole number"),
    (lambda raw: raw["defaults"].update(order="random"), "'order' must be one of"),
    (lambda raw: raw.pop("time_words"), "missing section 'time_words'"),
])
def test_each_mistake_is_named(tmp_path, edit, message):
    with pytest.raises(ConfigError, match=message):
        load_config(write(tmp_path, changed(edit)))


def test_broken_file_stops_with_a_clear_message(tmp_path):
    path = tmp_path / "clinic.json"
    path.write_text('{"therapists": {', encoding="utf-8")
    with pytest.raises(ConfigError, match="isn't valid JSON"):
        load_config(path)
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "missing.json")


def test_opening_therapist_matched_on_full_name_first(tmp_path, config):
    assert config.therapist_by_name("Josée Landry").name == "Josée Landry"
    assert config.therapist_by_name("Josee").name == "Josée Landry"
    assert config.therapist_by_name("Josée L.").name == "Josée Landry"
    assert config.therapist_by_name("Josée Arsenault") is None  # a different Josée, not in the settings
    two = load_config(write(tmp_path, changed(lambda raw: raw["therapists"].update(
        {"Dave Cormier": {"aliases": [], "female": False, "prenatal_trained": False, "approval": "none"}}))))
    assert two.therapist_by_name("Dave Cormier").name == "Dave Cormier"
    assert two.therapist_by_name("Dave Melanson").name == "Dave Melanson"
    assert two.therapist_by_name("Dave") is None  # two Daves: ambiguous, so the opening gets nobody and a warning
