"""Scenario parity suite for Blockheat core behavior."""

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
compute_fallback_conditions = engine.compute_fallback_conditions
compute_final_target = engine.compute_final_target
compute_saving_target = engine.compute_saving_target


class ParitySuite(unittest.TestCase):
    def test_policy_on_warm_shutdown_path(self) -> None:
        saving = compute_saving_target(
            outdoor_temp=10.0,
            heatpump_setpoint=20.0,
            saving_cold_offset_c=1.0,
            virtual_temperature=20.0,
            warm_shutdown_outdoor=7.0,
            control_min_c=10.0,
            control_max_c=26.0,
        )
        final = compute_final_target(
            policy_on=True,
            fallback_active=False,
            saving_target=saving,
            comfort_target=23.0,
            control_current=20.0,
            control_min_c=10.0,
            control_max_c=26.0,
        )
        self.assertEqual(saving, 20.0)
        self.assertEqual(final.target, 20.0)

    def test_policy_on_cold_saving_path(self) -> None:
        saving = compute_saving_target(
            outdoor_temp=-5.0,
            heatpump_setpoint=20.0,
            saving_cold_offset_c=1.0,
            virtual_temperature=20.0,
            warm_shutdown_outdoor=7.0,
            control_min_c=10.0,
            control_max_c=26.0,
        )
        self.assertEqual(saving, 19.0)

    def test_policy_off_comfort_unsatisfied(self) -> None:
        comfort = compute_comfort_target(
            room1_temp=21.0,
            room2_temp=21.0,
            storage_temp=25.0,
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
        final = compute_final_target(
            policy_on=False,
            fallback_active=False,
            saving_target=19.0,
            comfort_target=comfort.target,
            control_current=20.0,
            control_min_c=10.0,
            control_max_c=26.0,
        )
        self.assertAlmostEqual(final.target, comfort.target)

    def test_policy_off_storage_needs_heat(self) -> None:
        comfort = compute_comfort_target(
            room1_temp=22.2,
            room2_temp=22.2,
            storage_temp=23.5,
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
        self.assertGreaterEqual(comfort.target, 23.0)

    def test_policy_off_storage_ok(self) -> None:
        comfort = compute_comfort_target(
            room1_temp=22.2,
            room2_temp=22.2,
            storage_temp=25.2,
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
        self.assertEqual(comfort.target, 20.0)

    def test_extreme_clamp_behavior(self) -> None:
        comfort = compute_comfort_target(
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
        self.assertEqual(comfort.target, 26.0)

    def test_cold_boost_raises_target_below_threshold(self) -> None:
        at_threshold = compute_comfort_target(
            room1_temp=21.0,
            room2_temp=21.0,
            storage_temp=25.0,
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
            storage_temp=25.0,
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
        self.assertEqual(at_threshold.boost_clamped, 0.0)
        self.assertGreater(colder.boost_clamped, 0.0)
        self.assertGreater(colder.target, at_threshold.target)

    def test_fallback_arm_and_release(self) -> None:
        now = datetime(2026, 2, 18, 10, 0, tzinfo=UTC)
        armed = compute_fallback_conditions(
            policy_on=False,
            fallback_active=False,
            room1_temp=20.0,
            room2_temp=20.0,
            comfort_target_c=22.0,
            trigger_delta_c=0.5,
            release_delta_c=0.1,
            cooldown_minutes=60,
            last_trigger=now - timedelta(hours=5),
            now=now,
        )
        self.assertTrue(armed.arm_condition)

        released = compute_fallback_conditions(
            policy_on=False,
            fallback_active=True,
            room1_temp=22.0,
            room2_temp=22.0,
            comfort_target_c=22.0,
            trigger_delta_c=0.5,
            release_delta_c=0.1,
            cooldown_minutes=60,
            last_trigger=now - timedelta(minutes=30),
            now=now,
        )
        self.assertTrue(released.release_by_recovery)


if __name__ == "__main__":
    unittest.main()
