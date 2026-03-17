"""Translation coverage checks for config and options onboarding fields."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CUSTOM_STRINGS = ROOT / "custom_components" / "blockheat" / "strings.json"
CUSTOM_EN = ROOT / "custom_components" / "blockheat" / "translations" / "en.json"

TUNING_STEPS = (
    "tuning_targets",
    "tuning_daikin",
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_step_field_explanations(
    translations: dict, root_key: str, step_id: str
) -> None:
    step = translations[root_key]["step"][step_id]
    data = step.get("data")
    descriptions = step.get("data_description")

    assert isinstance(data, dict), f"{root_key}.{step_id}.data must be a mapping"
    assert isinstance(descriptions, dict), (
        f"{root_key}.{step_id}.data_description must be a mapping"
    )
    assert data, f"{root_key}.{step_id}.data must not be empty"
    assert set(descriptions.keys()) == set(data.keys()), (
        f"{root_key}.{step_id}.data_description keys must match data keys"
    )

    for key, label in data.items():
        assert str(label).strip(), f"{root_key}.{step_id}.data[{key}] must be non-empty"
    for key, description in descriptions.items():
        assert str(description).strip(), (
            f"{root_key}.{step_id}.data_description[{key}] must be non-empty"
        )


def test_translation_files_are_kept_in_sync() -> None:
    base = _load_json(CUSTOM_STRINGS)
    assert _load_json(CUSTOM_EN) == base


def test_all_tuning_steps_have_labels_and_descriptions_in_config_and_options() -> None:
    translations = _load_json(CUSTOM_STRINGS)
    for root_key in ("config", "options"):
        for step_id in TUNING_STEPS:
            _assert_step_field_explanations(translations, root_key, step_id)


def test_targets_copy_is_explicit() -> None:
    translations = _load_json(CUSTOM_STRINGS)
    config_step = translations["config"]["step"]

    assert (
        "Skip blocking" in config_step["tuning_targets"]["data"]["price_ignore_below"]
    )
    assert "Skip blocking" in config_step["tuning_targets"]["data"]["pv_ignore_above_w"]


def test_storage_sensor_copy_prefers_buffer_pipe_temperature() -> None:
    translations = _load_json(CUSTOM_STRINGS)
    config_step = translations["config"]["step"]["user"]
    options_step = translations["options"]["step"]["init"]

    for step in (config_step, options_step):
        label = step["data"]["storage_room_sensor"]
        description = step["data_description"]["storage_room_sensor"]

        assert "Buffer" in label
        assert "pipe temperature" in description
        assert "system energy" in description
