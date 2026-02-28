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
compute_fallback_conditions = engine.compute_fallback_conditions
compute_final_target = engine.compute_final_target
compute_floor = engine.compute_floor
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
            floor_temp=21.0,
            min_floor_temp=0.0,
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
            floor_temp=21.0,
            min_floor_temp=0.0,
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


class FallbackTests(unittest.TestCase):
    def test_fallback_arm_condition(self) -> None:
        now = datetime(2026, 2, 18, 10, 0, tzinfo=UTC)
        result = compute_fallback_conditions(
            policy_on=False,
            fallback_active=False,
            room1_temp=20.0,
            room2_temp=20.2,
            comfort_target_c=22.0,
            trigger_delta_c=0.5,
            release_delta_c=0.1,
            cooldown_minutes=60,
            last_trigger=now - timedelta(minutes=180),
            now=now,
        )
        self.assertTrue(result.arm_condition)

    def test_fallback_release_by_policy(self) -> None:
        now = datetime(2026, 2, 18, 10, 0, tzinfo=UTC)
        result = compute_fallback_conditions(
            policy_on=True,
            fallback_active=True,
            room1_temp=20.0,
            room2_temp=20.0,
            comfort_target_c=22.0,
            trigger_delta_c=0.5,
            release_delta_c=0.1,
            cooldown_minutes=60,
            last_trigger=now - timedelta(minutes=30),
            now=now,
        )
        self.assertTrue(result.release_by_policy)


class FinalTargetTests(unittest.TestCase):
    def test_final_prefers_saving_when_policy_on(self) -> None:
        result = compute_final_target(
            policy_on=True,
            fallback_active=False,
            saving_target=18.0,
            comfort_target=23.0,
            control_current=21.0,
            control_min_c=10.0,
            control_max_c=26.0,
        )
        self.assertEqual(result.target, 18.0)
        self.assertEqual(result.source, "saving")

    def test_final_forces_min_when_fallback_active(self) -> None:
        result = compute_final_target(
            policy_on=False,
            fallback_active=True,
            saving_target=18.0,
            comfort_target=23.0,
            control_current=21.0,
            control_min_c=10.0,
            control_max_c=26.0,
        )
        self.assertEqual(result.target, 10.0)
        self.assertEqual(result.source, "fallback_min")


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

    def test_floor_soft_off_in_policy_saving(self) -> None:
        now = datetime(2026, 2, 18, 10, 0, tzinfo=UTC)
        result = compute_floor(
            policy_on=True,
            cur_temp=22.0,
            dev_min=5.0,
            comfort_temp_c=22.0,
            prefer_preset_manual=True,
            hvac_mode_when_on="heat",
            supported_hvac_modes=["heat", "auto"],
            preset_modes=["manual"],
            soft_off_temp_override_c="",
            min_keep_temp_c="",
            schedule_defined=False,
            schedule_on=True,
            last_changed=now - timedelta(minutes=20),
            min_switch_interval_min=15,
            now=now,
        )
        self.assertEqual(result.action, "set_soft_off")


if __name__ == "__main__":
    unittest.main()
