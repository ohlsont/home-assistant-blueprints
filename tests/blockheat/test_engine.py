"""Unit tests for the Blockheat pure engine."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

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

compute_comfort_target = engine.compute_comfort_target
compute_daikin = engine.compute_daikin
compute_final_target = engine.compute_final_target
compute_policy = engine.compute_policy
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
        self.assertTrue(result.target_on)
        self.assertTrue(result.should_turn_on)

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
        self.assertTrue(result.target_on)
        self.assertFalse(result.should_turn_on)


class SavingTargetTests(unittest.TestCase):
    def test_saving_warm_shutdown_uses_virtual_temperature(self) -> None:
        target = compute_saving_target(
            outdoor_temp=8.0,
            heatpump_setpoint=20.0,
            saving_cold_offset_c=1.0,
            virtual_temperature=17.0,
            warm_shutdown_outdoor=7.0,
            control_min_c=10.0,
            control_max_c=26.0,
        )
        self.assertEqual(target, 17.0)

    def test_saving_cold_mode_uses_setpoint_offset(self) -> None:
        target = compute_saving_target(
            outdoor_temp=0.0,
            heatpump_setpoint=20.0,
            saving_cold_offset_c=1.0,
            virtual_temperature=17.0,
            warm_shutdown_outdoor=7.0,
            control_min_c=10.0,
            control_max_c=26.0,
        )
        self.assertEqual(target, 19.0)


class ComfortTargetTests(unittest.TestCase):
    def test_comfort_unsatisfied_follows_comfort_path(self) -> None:
        result = compute_comfort_target(
            room1_temp=21.0,
            room2_temp=21.0,
            storage_temp=25.0,
            outdoor_temp=2.0,
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
        self.assertAlmostEqual(result.target, 20.0)

    def test_comfort_satisfied_storage_needs_heat_prefers_storage_path(self) -> None:
        result = compute_comfort_target(
            room1_temp=22.0,
            room2_temp=22.2,
            storage_temp=24.0,
            outdoor_temp=2.0,
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
        self.assertAlmostEqual(result.target, 23.0)

    def test_comfort_satisfied_storage_ok_uses_maintenance(self) -> None:
        result = compute_comfort_target(
            room1_temp=22.0,
            room2_temp=22.2,
            storage_temp=25.5,
            outdoor_temp=2.0,
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
        self.assertAlmostEqual(result.target, 20.0)


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
        self.assertEqual(result.target, 18.0)
        self.assertEqual(result.source, "saving")

    def test_final_prefers_comfort_when_policy_off(self) -> None:
        result = compute_final_target(
            policy_on=False,
            saving_target=18.0,
            comfort_target=23.0,
            control_current=21.0,
            control_min_c=10.0,
            control_max_c=26.0,
        )
        self.assertEqual(result.target, 23.0)
        self.assertEqual(result.source, "comfort")

    def test_final_uses_default_min_when_policy_off_targets_missing(self) -> None:
        result = compute_final_target(
            policy_on=False,
            saving_target=18.0,
            comfort_target=None,
            control_current=None,
            control_min_c=10.0,
            control_max_c=26.0,
        )
        self.assertEqual(result.target, 10.0)
        self.assertEqual(result.source, "control_min_default")


class ConsumerTests(unittest.TestCase):
    def test_daikin_blocks_action_if_too_cold(self) -> None:
        result = compute_daikin(
            policy_on=True,
            current_temp=22.0,
            normal_temperature=22.0,
            saving_temperature=19.0,
            min_temp_change=0.5,
            outdoor_temp=-20.0,
            outdoor_temp_threshold=-10.0,
            outdoor_sensor_defined=True,
        )
        self.assertFalse(result.should_write)
        self.assertIsNone(result.target_temp)


if __name__ == "__main__":
    unittest.main()
