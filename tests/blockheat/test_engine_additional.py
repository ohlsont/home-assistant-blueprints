"""Additional branch coverage tests for the Blockheat pure engine."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import importlib.util
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
ENGINE_MODULE = "homeassistant.custom_components.blockheat.engine"
ENGINE_PATH = ROOT / "homeassistant" / "custom_components" / "blockheat" / "engine.py"

if ENGINE_MODULE in sys.modules:
    engine = sys.modules[ENGINE_MODULE]
else:
    spec = importlib.util.spec_from_file_location(ENGINE_MODULE, ENGINE_PATH)
    assert spec and spec.loader
    engine = importlib.util.module_from_spec(spec)
    sys.modules[ENGINE_MODULE] = engine
    spec.loader.exec_module(engine)

DEFAULT_POLICY_CUTOFF = engine.DEFAULT_POLICY_CUTOFF
compute_comfort_target = engine.compute_comfort_target
compute_daikin = engine.compute_daikin
compute_fallback_conditions = engine.compute_fallback_conditions
compute_final_target = engine.compute_final_target
compute_floor = engine.compute_floor
compute_policy = engine.compute_policy
compute_saving_target = engine.compute_saving_target


def test_policy_minutes_to_block_zero_never_blocks() -> None:
    now = datetime(2026, 2, 18, 10, 0, tzinfo=UTC)
    result = compute_policy(
        price=50.0,
        prices_today=[1.0, 2.0, 3.0, 4.0],
        minutes_to_block=0,
        price_ignore_below=0.0,
        pv_now=0.0,
        pv_ignore_above_w=0.0,
        floor_temp=21.0,
        min_floor_temp=0.0,
        current_on=False,
        last_changed=now - timedelta(minutes=30),
        now=now,
        min_toggle_interval_min=15,
    )
    assert result.cutoff == DEFAULT_POLICY_CUTOFF
    assert result.blocked_now is False
    assert result.target_on is False


def test_policy_minutes_to_block_exceeds_slots_uses_default_cutoff() -> None:
    now = datetime(2026, 2, 18, 10, 0, tzinfo=UTC)
    result = compute_policy(
        price=50.0,
        prices_today=[2.0, 3.0, 4.0],
        minutes_to_block=90,
        price_ignore_below=0.0,
        pv_now=0.0,
        pv_ignore_above_w=0.0,
        floor_temp=21.0,
        min_floor_temp=0.0,
        current_on=False,
        last_changed=now - timedelta(minutes=30),
        now=now,
        min_toggle_interval_min=15,
    )
    assert result.cutoff == DEFAULT_POLICY_CUTOFF
    assert result.target_on is False


def test_policy_ignores_non_numeric_prices() -> None:
    now = datetime(2026, 2, 18, 10, 0, tzinfo=UTC)
    result = compute_policy(
        price=3.0,
        prices_today=["bad", None, "2.0", 4.0],
        minutes_to_block=15,
        price_ignore_below=0.0,
        pv_now=0.0,
        pv_ignore_above_w=0.0,
        floor_temp=21.0,
        min_floor_temp=0.0,
        current_on=False,
        last_changed=now - timedelta(minutes=30),
        now=now,
        min_toggle_interval_min=15,
    )
    assert result.cutoff == 4.0
    assert result.target_on is False


def test_policy_ignore_overrides_precedence() -> None:
    now = datetime(2026, 2, 18, 10, 0, tzinfo=UTC)
    result = compute_policy(
        price=9.0,
        prices_today=[1.0, 2.0, 9.0, 8.0],
        minutes_to_block=30,
        price_ignore_below=10.0,
        pv_now=5000.0,
        pv_ignore_above_w=1000.0,
        floor_temp=17.0,
        min_floor_temp=18.0,
        current_on=False,
        last_changed=now - timedelta(minutes=30),
        now=now,
        min_toggle_interval_min=15,
    )
    assert result.blocked_now is True
    assert result.target_on is False
    assert result.ignore_by_price is True
    assert result.ignore_by_pv is True
    assert result.below_min_floor is True


def test_saving_target_uses_virtual_at_warm_boundary() -> None:
    target = compute_saving_target(
        outdoor_temp=7.0,
        heatpump_setpoint=20.0,
        saving_cold_offset_c=1.0,
        virtual_temperature=17.5,
        warm_shutdown_outdoor=7.0,
        control_min_c=10.0,
        control_max_c=26.0,
    )
    assert target == 17.5


@pytest.mark.parametrize(
    (
        "outdoor_temp",
        "heatpump_setpoint",
        "saving_cold_offset_c",
        "virtual_temperature",
        "expected",
    ),
    [
        (-30.0, 5.0, 10.0, 40.0, 10.0),
        (99.0, 30.0, 10.0, 40.0, 26.0),
    ],
)
def test_saving_target_clamps_to_limits(
    outdoor_temp: float,
    heatpump_setpoint: float,
    saving_cold_offset_c: float,
    virtual_temperature: float,
    expected: float,
) -> None:
    target = compute_saving_target(
        outdoor_temp=outdoor_temp,
        heatpump_setpoint=heatpump_setpoint,
        saving_cold_offset_c=saving_cold_offset_c,
        virtual_temperature=virtual_temperature,
        warm_shutdown_outdoor=7.0,
        control_min_c=10.0,
        control_max_c=26.0,
    )
    assert target == expected


def test_comfort_no_boost_exactly_at_threshold() -> None:
    result = compute_comfort_target(
        room1_temp=21.0,
        room2_temp=21.0,
        storage_temp=24.0,
        outdoor_temp=0.0,
        comfort_target_c=22.0,
        comfort_to_heatpump_offset_c=2.0,
        storage_target_c=25.0,
        storage_to_heatpump_offset_c=2.0,
        maintenance_target_c=20.0,
        comfort_margin_c=0.2,
        cold_threshold=0.0,
        max_boost=3.0,
        boost_slope_c=5.0,
        control_min_c=10.0,
        control_max_c=26.0,
    )
    assert result.boost_clamped == 0.0
    assert result.target == 20.0


def test_comfort_boost_saturates_at_max() -> None:
    result = compute_comfort_target(
        room1_temp=21.0,
        room2_temp=21.0,
        storage_temp=24.0,
        outdoor_temp=-50.0,
        comfort_target_c=22.0,
        comfort_to_heatpump_offset_c=2.0,
        storage_target_c=25.0,
        storage_to_heatpump_offset_c=2.0,
        maintenance_target_c=20.0,
        comfort_margin_c=0.2,
        cold_threshold=0.0,
        max_boost=3.0,
        boost_slope_c=5.0,
        control_min_c=10.0,
        control_max_c=26.0,
    )
    assert result.boost_clamped == 3.0
    assert result.target == 23.0


def test_comfort_colder_outdoor_increases_target() -> None:
    at_threshold = compute_comfort_target(
        room1_temp=21.0,
        room2_temp=21.0,
        storage_temp=24.0,
        outdoor_temp=0.0,
        comfort_target_c=22.0,
        comfort_to_heatpump_offset_c=2.0,
        storage_target_c=25.0,
        storage_to_heatpump_offset_c=2.0,
        maintenance_target_c=20.0,
        comfort_margin_c=0.2,
        cold_threshold=0.0,
        max_boost=3.0,
        boost_slope_c=5.0,
        control_min_c=10.0,
        control_max_c=26.0,
    )
    colder = compute_comfort_target(
        room1_temp=21.0,
        room2_temp=21.0,
        storage_temp=24.0,
        outdoor_temp=-5.0,
        comfort_target_c=22.0,
        comfort_to_heatpump_offset_c=2.0,
        storage_target_c=25.0,
        storage_to_heatpump_offset_c=2.0,
        maintenance_target_c=20.0,
        comfort_margin_c=0.2,
        cold_threshold=0.0,
        max_boost=3.0,
        boost_slope_c=5.0,
        control_min_c=10.0,
        control_max_c=26.0,
    )
    assert at_threshold.boost_clamped == 0.0
    assert colder.boost_clamped == 1.0
    assert colder.target == at_threshold.target + 1.0


def test_comfort_storage_path_is_boosted_when_comfort_satisfied() -> None:
    result = compute_comfort_target(
        room1_temp=22.4,
        room2_temp=22.3,
        storage_temp=20.0,
        outdoor_temp=-10.0,
        comfort_target_c=22.0,
        comfort_to_heatpump_offset_c=2.0,
        storage_target_c=25.0,
        storage_to_heatpump_offset_c=2.0,
        maintenance_target_c=20.0,
        comfort_margin_c=0.2,
        cold_threshold=0.0,
        max_boost=3.0,
        boost_slope_c=5.0,
        control_min_c=10.0,
        control_max_c=26.0,
    )
    assert result.boost_clamped == 2.0
    assert result.comfort_target_unclamped == 22.0
    assert result.storage_target_unclamped == 25.0
    assert result.target == 25.0


def test_comfort_extreme_cold_clamps_to_control_max() -> None:
    result = compute_comfort_target(
        room1_temp=20.0,
        room2_temp=20.0,
        storage_temp=20.0,
        outdoor_temp=-100.0,
        comfort_target_c=22.0,
        comfort_to_heatpump_offset_c=2.0,
        storage_target_c=25.0,
        storage_to_heatpump_offset_c=2.0,
        maintenance_target_c=20.0,
        comfort_margin_c=0.2,
        cold_threshold=0.0,
        max_boost=10.0,
        boost_slope_c=1.0,
        control_min_c=10.0,
        control_max_c=26.0,
    )
    assert result.boost_clamped == 10.0
    assert result.target == 26.0


def test_comfort_missing_room_sensor_forces_unsatisfied_path() -> None:
    result = compute_comfort_target(
        room1_temp=None,
        room2_temp=25.0,
        storage_temp=30.0,
        outdoor_temp=0.0,
        comfort_target_c=22.0,
        comfort_to_heatpump_offset_c=2.0,
        storage_target_c=25.0,
        storage_to_heatpump_offset_c=2.0,
        maintenance_target_c=20.0,
        comfort_margin_c=0.2,
        cold_threshold=0.0,
        max_boost=3.0,
        boost_slope_c=5.0,
        control_min_c=10.0,
        control_max_c=26.0,
    )
    assert result.comfort_satisfied is False
    assert result.target == 20.0


def test_comfort_storage_vs_comfort_tie_is_stable() -> None:
    result = compute_comfort_target(
        room1_temp=22.0,
        room2_temp=22.0,
        storage_temp=20.0,
        outdoor_temp=0.0,
        comfort_target_c=22.0,
        comfort_to_heatpump_offset_c=2.0,
        storage_target_c=22.0,
        storage_to_heatpump_offset_c=2.0,
        maintenance_target_c=20.0,
        comfort_margin_c=0.2,
        cold_threshold=0.0,
        max_boost=3.0,
        boost_slope_c=5.0,
        control_min_c=10.0,
        control_max_c=26.0,
    )
    assert result.comfort_target_unclamped == result.storage_target_unclamped
    assert result.target == result.comfort_target_unclamped


def test_fallback_cooldown_exact_boundary_arms() -> None:
    now = datetime(2026, 2, 18, 10, 0, tzinfo=UTC)
    result = compute_fallback_conditions(
        policy_on=False,
        fallback_active=False,
        room1_temp=20.0,
        room2_temp=20.0,
        comfort_target_c=22.0,
        trigger_delta_c=0.5,
        release_delta_c=0.1,
        cooldown_minutes=60,
        last_trigger=now - timedelta(minutes=60),
        now=now,
    )
    assert result.cooldown_ok is True
    assert result.arm_condition is True


def test_fallback_cooldown_one_second_short_blocks_arm() -> None:
    now = datetime(2026, 2, 18, 10, 0, tzinfo=UTC)
    result = compute_fallback_conditions(
        policy_on=False,
        fallback_active=False,
        room1_temp=20.0,
        room2_temp=20.0,
        comfort_target_c=22.0,
        trigger_delta_c=0.5,
        release_delta_c=0.1,
        cooldown_minutes=60,
        last_trigger=now - timedelta(minutes=59, seconds=59),
        now=now,
    )
    assert result.cooldown_ok is False
    assert result.arm_condition is False


def test_fallback_missing_comfort_sensors_never_arms() -> None:
    now = datetime(2026, 2, 18, 10, 0, tzinfo=UTC)
    result = compute_fallback_conditions(
        policy_on=False,
        fallback_active=False,
        room1_temp=None,
        room2_temp=None,
        comfort_target_c=22.0,
        trigger_delta_c=0.5,
        release_delta_c=0.1,
        cooldown_minutes=60,
        last_trigger=now - timedelta(minutes=120),
        now=now,
    )
    assert result.comfort_min is None
    assert result.arm_condition is False


def test_final_target_policy_on_missing_saving_falls_back_to_control_current() -> None:
    result = compute_final_target(
        policy_on=True,
        fallback_active=False,
        saving_target=None,
        comfort_target=22.0,
        control_current=19.0,
        control_min_c=10.0,
        control_max_c=26.0,
    )
    assert result.source == "control_current"
    assert result.target == 19.0


def test_final_target_policy_off_missing_all_uses_control_min() -> None:
    result = compute_final_target(
        policy_on=False,
        fallback_active=False,
        saving_target=None,
        comfort_target=None,
        control_current=None,
        control_min_c=10.0,
        control_max_c=26.0,
    )
    assert result.source == "control_min_fallback"
    assert result.target == 10.0


def test_daikin_without_outdoor_sensor_uses_default_allow_path() -> None:
    result = compute_daikin(
        policy_on=True,
        current_temp=22.0,
        normal_temperature=22.0,
        saving_temperature=19.0,
        min_temp_change=0.5,
        outdoor_temp=None,
        outdoor_temp_threshold=-10.0,
        outdoor_sensor_defined=False,
    )
    assert result.outdoor_ok is True
    assert result.target_temp == 19.0
    assert result.should_write is True


def test_floor_hvac_fallback_prefers_auto_when_heat_missing() -> None:
    now = datetime(2026, 2, 18, 10, 0, tzinfo=UTC)
    result = compute_floor(
        policy_on=False,
        cur_temp=10.0,
        dev_min=5.0,
        comfort_temp_c=22.0,
        prefer_preset_manual=False,
        hvac_mode_when_on="heat",
        supported_hvac_modes=["cool", "auto"],
        preset_modes=[],
        soft_off_temp_override_c="",
        min_keep_temp_c="",
        schedule_defined=True,
        schedule_on=True,
        last_changed=now - timedelta(hours=1),
        min_switch_interval_min=15,
        now=now,
    )
    assert result.action == "set_on"
    assert result.hvac_mode_final == "auto"


def test_floor_debounce_blocks_action() -> None:
    now = datetime(2026, 2, 18, 10, 0, tzinfo=UTC)
    result = compute_floor(
        policy_on=False,
        cur_temp=5.0,
        dev_min=5.0,
        comfort_temp_c=22.0,
        prefer_preset_manual=False,
        hvac_mode_when_on="heat",
        supported_hvac_modes=["heat"],
        preset_modes=[],
        soft_off_temp_override_c="",
        min_keep_temp_c="",
        schedule_defined=True,
        schedule_on=True,
        last_changed=now - timedelta(minutes=5),
        min_switch_interval_min=15,
        now=now,
    )
    assert result.action is None


def test_floor_noop_when_already_at_target() -> None:
    now = datetime(2026, 2, 18, 10, 0, tzinfo=UTC)
    result = compute_floor(
        policy_on=False,
        cur_temp=22.0,
        dev_min=5.0,
        comfort_temp_c=22.0,
        prefer_preset_manual=False,
        hvac_mode_when_on="heat",
        supported_hvac_modes=["heat"],
        preset_modes=[],
        soft_off_temp_override_c="",
        min_keep_temp_c="",
        schedule_defined=True,
        schedule_on=True,
        last_changed=now - timedelta(hours=1),
        min_switch_interval_min=15,
        now=now,
    )
    assert result.action is None
