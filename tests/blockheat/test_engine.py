"""Unit tests for the Blockheat pure engine."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ENGINE_MODULE = "homeassistant.custom_components.blockheat.engine"
ENGINE_PATH = ROOT / "homeassistant" / "custom_components" / "blockheat" / "engine.py"

if ENGINE_MODULE in sys.modules:
    engine = sys.modules[ENGINE_MODULE]
else:
    spec = importlib.util.spec_from_file_location(ENGINE_MODULE, ENGINE_PATH)
    assert spec
    assert spec.loader
    engine = importlib.util.module_from_spec(spec)
    sys.modules[ENGINE_MODULE] = engine
    spec.loader.exec_module(engine)

compute_comfort_target = engine.compute_comfort_target
compute_daikin = engine.compute_daikin
compute_final_target = engine.compute_final_target
compute_policy = engine.compute_policy
compute_price_quartile = engine.compute_price_quartile
compute_saving_target = engine.compute_saving_target


class PolicyTests(unittest.TestCase):
    def test_policy_turns_on_in_expensive_slot(self) -> None:
        now = datetime(2026, 2, 18, 10, 0, tzinfo=UTC)
        result = compute_policy(
            price=4.0,
            prices_today=[1.0, 2.0, 3.0, 4.0],
            minutes_to_block=30,
            price_ignore_below=0.0,
            pv_now=0.0,
            pv_ignore_above_w=0.0,
            current_on=False,
            last_changed=now - timedelta(minutes=60),
            now=now,
            min_toggle_interval_min=15,
        )
        assert result.target_on
        assert result.should_turn_on

    def test_policy_respects_debounce(self) -> None:
        now = datetime(2026, 2, 18, 10, 0, tzinfo=UTC)
        result = compute_policy(
            price=4.0,
            prices_today=[1.0, 2.0, 3.0, 4.0],
            minutes_to_block=30,
            price_ignore_below=0.0,
            pv_now=0.0,
            pv_ignore_above_w=0.0,
            current_on=False,
            last_changed=now - timedelta(minutes=5),
            now=now,
            min_toggle_interval_min=15,
        )
        assert result.target_on
        assert not result.should_turn_on


class SavingTargetTests(unittest.TestCase):
    def test_saving_warm_shutdown_uses_heatpump_setpoint(self) -> None:
        target = compute_saving_target(
            outdoor_temp=8.0,
            heatpump_setpoint=20.0,
            saving_cold_offset_c=1.0,
            warm_shutdown_outdoor=7.0,
            control_min_c=10.0,
            control_max_c=26.0,
        )
        assert target == 20.0

    def test_saving_cold_mode_uses_setpoint_offset(self) -> None:
        target = compute_saving_target(
            outdoor_temp=0.0,
            heatpump_setpoint=20.0,
            saving_cold_offset_c=1.0,
            warm_shutdown_outdoor=7.0,
            control_min_c=10.0,
            control_max_c=26.0,
        )
        assert target == 19.0


class ComfortTargetTests(unittest.TestCase):
    def test_comfort_unsatisfied_follows_comfort_path(self) -> None:
        result = compute_comfort_target(
            room1_temp=21.0,
            room2_temp=21.0,
            storage_temp=25.0,
            outdoor_temp=2.0,
            comfort_target_c=22.0,
            storage_target_c=25.0,
            heatpump_offset_c=2.0,
            heatpump_setpoint=20.0,
            comfort_margin_c=0.2,
            cold_threshold=0.0,
            max_boost=3.0,
            boost_slope_c=5.0,
            control_min_c=10.0,
            control_max_c=26.0,
        )
        assert result.target == pytest.approx(20.0)

    def test_comfort_satisfied_storage_needs_heat_prefers_storage_path(self) -> None:
        result = compute_comfort_target(
            room1_temp=22.0,
            room2_temp=22.2,
            storage_temp=24.0,
            outdoor_temp=2.0,
            comfort_target_c=22.0,
            storage_target_c=25.0,
            heatpump_offset_c=2.0,
            heatpump_setpoint=20.0,
            comfort_margin_c=0.2,
            cold_threshold=0.0,
            max_boost=3.0,
            boost_slope_c=5.0,
            control_min_c=10.0,
            control_max_c=26.0,
        )
        assert result.target == pytest.approx(23.0)

    def test_comfort_satisfied_storage_ok_uses_maintenance(self) -> None:
        result = compute_comfort_target(
            room1_temp=22.0,
            room2_temp=22.2,
            storage_temp=25.5,
            outdoor_temp=2.0,
            comfort_target_c=22.0,
            storage_target_c=25.0,
            heatpump_offset_c=2.0,
            heatpump_setpoint=20.0,
            comfort_margin_c=0.2,
            cold_threshold=0.0,
            max_boost=3.0,
            boost_slope_c=5.0,
            control_min_c=10.0,
            control_max_c=26.0,
        )
        assert result.target == pytest.approx(20.0)


class FinalTargetTests(unittest.TestCase):
    def test_final_prefers_saving_when_policy_on(self) -> None:
        result = compute_final_target(
            policy_on=True,
            saving_target=18.0,
            comfort_target=23.0,
            control_current=21.0,
            control_min_c=10.0,
            control_max_c=26.0,
        )
        assert result.target == 18.0
        assert result.source == "saving"

    def test_final_prefers_comfort_when_policy_off(self) -> None:
        result = compute_final_target(
            policy_on=False,
            saving_target=18.0,
            comfort_target=23.0,
            control_current=21.0,
            control_min_c=10.0,
            control_max_c=26.0,
        )
        assert result.target == 23.0
        assert result.source == "comfort"

    def test_final_uses_default_min_when_policy_off_targets_missing(self) -> None:
        result = compute_final_target(
            policy_on=False,
            saving_target=18.0,
            comfort_target=None,
            control_current=None,
            control_min_c=10.0,
            control_max_c=26.0,
        )
        assert result.target == 10.0
        assert result.source == "control_min_default"


_DAIKIN_DEFAULTS: dict[str, object] = {
    "current_temp": 22.0,
    "current_hvac_mode": "off",
    "normal_temperature": 22.0,
    "preheat_offset": 2.0,
    "min_temp_change": 0.5,
    "outdoor_temp": 0.0,
    "mild_threshold": 5.0,
    "cold_threshold": -5.0,
    "disable_threshold": -22.0,
    "outdoor_sensor_defined": True,
    "price_quartile": "low",
}


def _daikin(**overrides: object) -> object:
    kwargs = {**_DAIKIN_DEFAULTS, **overrides}
    return compute_daikin(**kwargs)


class PriceQuartileTests(unittest.TestCase):
    def test_very_low(self) -> None:
        assert compute_price_quartile(0.5, [0.5, 1.0, 1.5, 2.0]) == "very_low"

    def test_very_high(self) -> None:
        assert compute_price_quartile(2.0, [0.5, 1.0, 1.5, 2.0]) == "very_high"

    def test_low(self) -> None:
        prices = [float(i) for i in range(1, 25)]
        assert compute_price_quartile(8.0, prices) == "low"

    def test_high(self) -> None:
        prices = [float(i) for i in range(1, 25)]
        assert compute_price_quartile(18.0, prices) == "high"

    def test_empty_prices_returns_low(self) -> None:
        assert compute_price_quartile(1.0, []) == "low"


class ConsumerTests(unittest.TestCase):
    def test_very_high_price_turns_off(self) -> None:
        result = _daikin(price_quartile="very_high", current_hvac_mode="heat")
        assert result.mode == "off"
        assert result.target_hvac_mode == "off"
        assert result.should_write_mode is True

    def test_very_low_price_preheats(self) -> None:
        result = _daikin(price_quartile="very_low", outdoor_temp=0.0)
        assert result.mode == "preheat"
        assert result.target_temp == 24.0  # 22 + 2
        assert result.target_hvac_mode == "heat"

    def test_mild_weather_turns_off(self) -> None:
        result = _daikin(outdoor_temp=10.0)
        assert result.mode == "off"
        assert result.target_hvac_mode == "off"

    def test_cool_weather_normal_mode(self) -> None:
        result = _daikin(outdoor_temp=0.0)
        assert result.mode == "normal"
        assert result.target_temp == 22.0
        assert result.target_hvac_mode == "heat"

    def test_cold_weather_capacity_assist(self) -> None:
        result = _daikin(outdoor_temp=-10.0)
        assert result.mode == "capacity_assist"
        assert result.target_temp == 22.0
        assert result.target_hvac_mode == "heat"

    def test_extreme_cold_below_disable_turns_off(self) -> None:
        result = _daikin(outdoor_temp=-25.0)
        assert result.mode == "off"
        assert result.target_hvac_mode == "off"
        assert not result.outdoor_ok

    def test_no_outdoor_sensor_defaults_to_normal(self) -> None:
        result = _daikin(outdoor_sensor_defined=False)
        assert result.mode == "normal"
        assert result.target_hvac_mode == "heat"
        assert result.target_temp == 22.0

    def test_no_mode_write_when_already_correct(self) -> None:
        result = _daikin(
            outdoor_temp=0.0,
            current_hvac_mode="heat",
            current_temp=22.0,
        )
        assert result.mode == "normal"
        assert not result.should_write_mode
        assert not result.should_write_temp

    def test_mode_write_when_switching_on(self) -> None:
        result = _daikin(
            outdoor_temp=0.0,
            current_hvac_mode="off",
        )
        assert result.should_write_mode is True
        assert result.target_hvac_mode == "heat"


if __name__ == "__main__":
    unittest.main()
