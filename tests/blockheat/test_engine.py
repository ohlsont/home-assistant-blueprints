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
ENGINE_PATH = ROOT / "custom_components" / "blockheat" / "engine.py"

if ENGINE_MODULE in sys.modules:
    engine = sys.modules[ENGINE_MODULE]
else:
    spec = importlib.util.spec_from_file_location(ENGINE_MODULE, ENGINE_PATH)
    assert spec
    assert spec.loader
    engine = importlib.util.module_from_spec(spec)
    sys.modules[ENGINE_MODULE] = engine
    spec.loader.exec_module(engine)

DEFAULT_POLICY_CUTOFF = engine.DEFAULT_POLICY_CUTOFF
compute_comfort_target = engine.compute_comfort_target
compute_daikin = engine.compute_daikin
compute_final_target = engine.compute_final_target
compute_policy = engine.compute_policy
compute_price_quartile = engine.compute_price_quartile
compute_saving_target = engine.compute_saving_target
estimate_cop = engine.estimate_cop
true_cost = engine.true_cost
rank_slots_true_cost = engine.rank_slots_true_cost


# ---------------------------------------------------------------------------
# compute_policy
# ---------------------------------------------------------------------------


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

    def test_policy_hysteresis_keeps_saving_on_at_cutoff(self) -> None:
        """When already ON and price equals cutoff, hysteresis prevents turn-off."""
        now = datetime(2026, 2, 18, 10, 0, tzinfo=UTC)
        # prices [1, 2, 3, 4], block 30 min = 2 slots → cutoff = 3.0
        # price 3.0 == cutoff, without hysteresis this would stay blocked_now=True
        # but price 2.9 < cutoff would turn off.
        # With 5% hysteresis, off_cutoff = 3.0 * 0.95 = 2.85
        # So price 2.9 >= 2.85 → stays ON
        result = compute_policy(
            price=2.9,
            prices_today=[1.0, 2.0, 3.0, 4.0],
            minutes_to_block=30,
            price_ignore_below=0.0,
            pv_now=0.0,
            pv_ignore_above_w=0.0,
            current_on=True,
            last_changed=now - timedelta(minutes=60),
            now=now,
            min_toggle_interval_min=15,
            price_hysteresis_fraction=0.05,
        )
        assert result.target_on  # stays on due to hysteresis
        assert not result.should_turn_off

    def test_policy_hysteresis_allows_turn_off_below_band(self) -> None:
        """When already ON and price drops well below cutoff, turn off."""
        now = datetime(2026, 2, 18, 10, 0, tzinfo=UTC)
        # cutoff = 3.0, off_cutoff = 2.85, price = 2.0 < 2.85 → turn off
        result = compute_policy(
            price=2.0,
            prices_today=[1.0, 2.0, 3.0, 4.0],
            minutes_to_block=30,
            price_ignore_below=0.0,
            pv_now=0.0,
            pv_ignore_above_w=0.0,
            current_on=True,
            last_changed=now - timedelta(minutes=60),
            now=now,
            min_toggle_interval_min=15,
            price_hysteresis_fraction=0.05,
        )
        assert not result.target_on
        assert result.should_turn_off

    def test_policy_hysteresis_not_applied_when_off(self) -> None:
        """Hysteresis only applies when currently ON — entry threshold unchanged."""
        now = datetime(2026, 2, 18, 10, 0, tzinfo=UTC)
        # cutoff = 3.0, price = 2.9 < cutoff → should not turn on
        result = compute_policy(
            price=2.9,
            prices_today=[1.0, 2.0, 3.0, 4.0],
            minutes_to_block=30,
            price_ignore_below=0.0,
            pv_now=0.0,
            pv_ignore_above_w=0.0,
            current_on=False,
            last_changed=now - timedelta(minutes=60),
            now=now,
            min_toggle_interval_min=15,
            price_hysteresis_fraction=0.05,
        )
        assert not result.target_on
        assert not result.should_turn_on


def test_policy_minutes_to_block_zero_never_blocks() -> None:
    now = datetime(2026, 2, 18, 10, 0, tzinfo=UTC)
    result = compute_policy(
        price=50.0,
        prices_today=[1.0, 2.0, 3.0, 4.0],
        minutes_to_block=0,
        price_ignore_below=0.0,
        pv_now=0.0,
        pv_ignore_above_w=0.0,
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
        current_on=False,
        last_changed=now - timedelta(minutes=30),
        now=now,
        min_toggle_interval_min=15,
    )
    assert result.blocked_now is True
    assert result.target_on is False
    assert result.ignore_by_price is True
    assert result.ignore_by_pv is True


# ---------------------------------------------------------------------------
# compute_saving_target
# ---------------------------------------------------------------------------


class SavingTargetTests(unittest.TestCase):
    def test_saving_warm_shutdown_uses_heatpump_setpoint(self) -> None:
        result = compute_saving_target(
            outdoor_temp=8.0,
            heatpump_setpoint=20.0,
            saving_cold_offset_c=1.0,
            warm_shutdown_outdoor=7.0,
            control_min_c=10.0,
            control_max_c=26.0,
        )
        assert result.target == 21.0
        assert result.warm_shutdown is True

    def test_saving_cold_mode_uses_setpoint_offset(self) -> None:
        result = compute_saving_target(
            outdoor_temp=0.0,
            heatpump_setpoint=20.0,
            saving_cold_offset_c=1.0,
            warm_shutdown_outdoor=7.0,
            control_min_c=10.0,
            control_max_c=26.0,
        )
        assert result.target == 19.0
        assert result.warm_shutdown is False

    def test_warm_shutdown_hysteresis_stays_in_warm_shutdown(self) -> None:
        """Once in warm shutdown, temp must drop below threshold - hysteresis to exit."""
        result = compute_saving_target(
            outdoor_temp=7.5,  # below threshold (8.0) but above threshold - hysteresis (7.0)
            heatpump_setpoint=21.0,
            saving_cold_offset_c=1.0,
            warm_shutdown_outdoor=8.0,
            control_min_c=10.0,
            control_max_c=26.0,
            warm_shutdown_hysteresis_c=1.0,
            currently_warm_shutdown=True,
        )
        # Should stay in warm shutdown due to hysteresis
        assert result.warm_shutdown is True
        assert result.target == 22.0  # heatpump_setpoint + 1.0

    def test_warm_shutdown_hysteresis_exits_below_band(self) -> None:
        """Exits warm shutdown when temp drops below threshold - hysteresis."""
        result = compute_saving_target(
            outdoor_temp=6.9,  # below threshold - hysteresis (8.0 - 1.0 = 7.0)
            heatpump_setpoint=21.0,
            saving_cold_offset_c=1.0,
            warm_shutdown_outdoor=8.0,
            control_min_c=10.0,
            control_max_c=26.0,
            warm_shutdown_hysteresis_c=1.0,
            currently_warm_shutdown=True,
        )
        assert result.warm_shutdown is False
        assert result.target == 20.0  # heatpump_setpoint - saving_cold_offset_c

    def test_warm_shutdown_hysteresis_does_not_enter_early(self) -> None:
        """When not in warm shutdown, the normal threshold applies (no early entry)."""
        result = compute_saving_target(
            outdoor_temp=7.5,  # below threshold (8.0)
            heatpump_setpoint=21.0,
            saving_cold_offset_c=1.0,
            warm_shutdown_outdoor=8.0,
            control_min_c=10.0,
            control_max_c=26.0,
            warm_shutdown_hysteresis_c=1.0,
            currently_warm_shutdown=False,
        )
        assert result.warm_shutdown is False
        assert result.target == 20.0


def test_saving_target_uses_setpoint_at_warm_boundary() -> None:
    target = compute_saving_target(
        outdoor_temp=7.0,
        heatpump_setpoint=20.0,
        saving_cold_offset_c=1.0,
        warm_shutdown_outdoor=7.0,
        control_min_c=10.0,
        control_max_c=26.0,
    )
    assert target.target == 21.0


@pytest.mark.parametrize(
    (
        "outdoor_temp",
        "heatpump_setpoint",
        "saving_cold_offset_c",
        "expected",
    ),
    [
        (-30.0, 5.0, 10.0, 10.0),
        (99.0, 30.0, 10.0, 26.0),
    ],
)
def test_saving_target_clamps_to_limits(
    outdoor_temp: float,
    heatpump_setpoint: float,
    saving_cold_offset_c: float,
    expected: float,
) -> None:
    target = compute_saving_target(
        outdoor_temp=outdoor_temp,
        heatpump_setpoint=heatpump_setpoint,
        saving_cold_offset_c=saving_cold_offset_c,
        warm_shutdown_outdoor=7.0,
        control_min_c=10.0,
        control_max_c=26.0,
    )
    assert target.target == expected


# ---------------------------------------------------------------------------
# compute_comfort_target
# ---------------------------------------------------------------------------


class ComfortTargetTests(unittest.TestCase):
    def test_comfort_unsatisfied_follows_comfort_path(self) -> None:
        result = compute_comfort_target(
            room1_temp=21.0,
            room2_temp=21.0,
            storage_temp=25.0,
            outdoor_temp=2.0,
            comfort_target_c=22.0,
            storage_target_c=25.0,
            heatpump_setpoint=20.0,
            comfort_margin_c=0.2,
            cold_threshold=0.0,
            max_boost=3.0,
            boost_slope_c=5.0,
            control_min_c=10.0,
            control_max_c=26.0,
        )
        assert result.target == pytest.approx(22.0)

    def test_comfort_satisfied_storage_needs_heat_prefers_storage_path(self) -> None:
        result = compute_comfort_target(
            room1_temp=22.0,
            room2_temp=22.2,
            storage_temp=24.0,
            outdoor_temp=2.0,
            comfort_target_c=22.0,
            storage_target_c=25.0,
            heatpump_setpoint=20.0,
            comfort_margin_c=0.2,
            cold_threshold=0.0,
            max_boost=3.0,
            boost_slope_c=5.0,
            control_min_c=10.0,
            control_max_c=26.0,
        )
        assert result.target == pytest.approx(25.0)

    def test_comfort_satisfied_storage_ok_uses_maintenance(self) -> None:
        result = compute_comfort_target(
            room1_temp=22.0,
            room2_temp=22.2,
            storage_temp=25.5,
            outdoor_temp=2.0,
            comfort_target_c=22.0,
            storage_target_c=25.0,
            heatpump_setpoint=20.0,
            comfort_margin_c=0.2,
            cold_threshold=0.0,
            max_boost=3.0,
            boost_slope_c=5.0,
            control_min_c=10.0,
            control_max_c=26.0,
        )
        assert result.target == pytest.approx(21.0)


def test_comfort_no_boost_exactly_at_threshold() -> None:
    result = compute_comfort_target(
        room1_temp=21.0,
        room2_temp=21.0,
        storage_temp=24.0,
        outdoor_temp=0.0,
        comfort_target_c=22.0,
        storage_target_c=25.0,
        heatpump_setpoint=20.0,
        comfort_margin_c=0.2,
        cold_threshold=0.0,
        max_boost=3.0,
        boost_slope_c=5.0,
        control_min_c=10.0,
        control_max_c=26.0,
    )
    assert result.boost_clamped == 0.0
    assert result.target == 22.0


def test_comfort_boost_saturates_at_max() -> None:
    result = compute_comfort_target(
        room1_temp=21.0,
        room2_temp=21.0,
        storage_temp=24.0,
        outdoor_temp=-50.0,
        comfort_target_c=22.0,
        storage_target_c=25.0,
        heatpump_setpoint=20.0,
        comfort_margin_c=0.2,
        cold_threshold=0.0,
        max_boost=3.0,
        boost_slope_c=5.0,
        control_min_c=10.0,
        control_max_c=26.0,
    )
    assert result.boost_clamped == 3.0
    assert result.target == 25.0


def test_comfort_zero_boost_slope_uses_max_boost_without_crash() -> None:
    result = compute_comfort_target(
        room1_temp=21.0,
        room2_temp=21.0,
        storage_temp=24.0,
        outdoor_temp=-5.0,
        comfort_target_c=22.0,
        storage_target_c=25.0,
        heatpump_setpoint=20.0,
        comfort_margin_c=0.2,
        cold_threshold=0.0,
        max_boost=3.0,
        boost_slope_c=0.0,
        control_min_c=10.0,
        control_max_c=26.0,
    )
    assert result.boost_clamped == 3.0
    assert result.target == 25.0


def test_comfort_colder_outdoor_increases_target() -> None:
    at_threshold = compute_comfort_target(
        room1_temp=21.0,
        room2_temp=21.0,
        storage_temp=24.0,
        outdoor_temp=0.0,
        comfort_target_c=22.0,
        storage_target_c=25.0,
        heatpump_setpoint=20.0,
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
        storage_target_c=25.0,
        heatpump_setpoint=20.0,
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
        storage_target_c=25.0,
        heatpump_setpoint=20.0,
        comfort_margin_c=0.2,
        cold_threshold=0.0,
        max_boost=3.0,
        boost_slope_c=5.0,
        control_min_c=10.0,
        control_max_c=26.0,
    )
    assert result.boost_clamped == 2.0
    assert result.comfort_target_unclamped == 24.0
    assert result.storage_target_unclamped == 27.0
    assert result.target == 26.0


def test_comfort_extreme_cold_clamps_to_control_max() -> None:
    result = compute_comfort_target(
        room1_temp=20.0,
        room2_temp=20.0,
        storage_temp=20.0,
        outdoor_temp=-100.0,
        comfort_target_c=22.0,
        storage_target_c=25.0,
        heatpump_setpoint=20.0,
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
        storage_target_c=25.0,
        heatpump_setpoint=20.0,
        comfort_margin_c=0.2,
        cold_threshold=0.0,
        max_boost=3.0,
        boost_slope_c=5.0,
        control_min_c=10.0,
        control_max_c=26.0,
    )
    assert result.comfort_satisfied is False
    assert result.target == 22.0


def test_comfort_storage_vs_comfort_tie_is_stable() -> None:
    result = compute_comfort_target(
        room1_temp=22.0,
        room2_temp=22.0,
        storage_temp=20.0,
        outdoor_temp=0.0,
        comfort_target_c=22.0,
        storage_target_c=22.0,
        heatpump_setpoint=20.0,
        comfort_margin_c=0.2,
        cold_threshold=0.0,
        max_boost=3.0,
        boost_slope_c=5.0,
        control_min_c=10.0,
        control_max_c=26.0,
    )
    assert result.comfort_target_unclamped == result.storage_target_unclamped
    assert result.target == result.comfort_target_unclamped


# ---------------------------------------------------------------------------
# compute_final_target
# ---------------------------------------------------------------------------


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


def test_final_target_policy_on_missing_saving_falls_back_to_control_current() -> None:
    result = compute_final_target(
        policy_on=True,
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
        saving_target=None,
        comfort_target=None,
        control_current=None,
        control_min_c=10.0,
        control_max_c=26.0,
    )
    assert result.source == "control_min_default"
    assert result.target == 10.0


# ---------------------------------------------------------------------------
# compute_price_quartile
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# compute_daikin
# ---------------------------------------------------------------------------


_DAIKIN_DEFAULTS: dict[str, object] = {
    "current_temp": 22.0,
    "current_hvac_mode": "off",
    "normal_temperature": 22.0,
    "preheat_offset": 2.0,
    "min_temp_change": 0.5,
    "outdoor_temp": 0.0,
    "mild_threshold": 5.0,
    "outdoor_sensor_defined": True,
    "price_quartile": "low",
}


def _daikin(**overrides: object) -> object:
    kwargs = {**_DAIKIN_DEFAULTS, **overrides}
    return compute_daikin(**kwargs)


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

    def test_cold_weather_normal_mode(self) -> None:
        result = _daikin(outdoor_temp=-10.0)
        assert result.mode == "normal"
        assert result.target_temp == 22.0
        assert result.target_hvac_mode == "heat"

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


def test_daikin_without_outdoor_sensor_uses_default_allow_path() -> None:
    result = compute_daikin(
        current_temp=22.0,
        current_hvac_mode="off",
        normal_temperature=22.0,
        preheat_offset=2.0,
        min_temp_change=0.5,
        outdoor_temp=None,
        mild_threshold=5.0,
        outdoor_sensor_defined=False,
        price_quartile="low",
    )
    assert result.mode == "normal"
    assert result.target_hvac_mode == "heat"


# ---------------------------------------------------------------------------
# estimate_cop / true_cost / rank_slots_true_cost
# ---------------------------------------------------------------------------


class TestEstimateCop:
    def test_at_zero_degrees(self) -> None:
        assert estimate_cop(0.0) == pytest.approx(3.0)

    def test_warm_weather_above_base(self) -> None:
        # At +10C: 3.0 + 0.08 * 10 = 3.8
        assert estimate_cop(10.0) == pytest.approx(3.8)

    def test_very_cold_floors_at_minimum(self) -> None:
        # At -25C: 3.0 + 0.08 * (-25) = 1.0, floored to 1.5
        assert estimate_cop(-25.0) == pytest.approx(1.5)

    def test_exactly_at_floor_boundary(self) -> None:
        # At -18.75C: 3.0 + 0.08 * (-18.75) = 1.5 (exactly at floor)
        assert estimate_cop(-18.75) == pytest.approx(1.5)

    def test_always_positive(self) -> None:
        for t in [-50.0, -30.0, -20.0, -10.0, 0.0, 10.0, 30.0]:
            assert estimate_cop(t) >= 1.5


class TestTrueCost:
    def test_warm_reduces_cost(self) -> None:
        # Warm = higher COP = lower true cost
        warm_cost = true_cost(1.0, 10.0)
        cold_cost = true_cost(1.0, -10.0)
        assert warm_cost < cold_cost

    def test_at_zero_degrees(self) -> None:
        # COP = 3.0, so true_cost = 1.0 / 3.0
        assert true_cost(1.0, 0.0) == pytest.approx(1.0 / 3.0)

    def test_at_floor_temp(self) -> None:
        # Very cold, COP = 1.5, so true_cost = price / 1.5
        assert true_cost(3.0, -30.0) == pytest.approx(3.0 / 1.5)

    def test_zero_price(self) -> None:
        assert true_cost(0.0, 5.0) == pytest.approx(0.0)


class TestRankSlotsTrueCost:
    def test_basic_ranking(self) -> None:
        prices = [1.0, 2.0, 3.0, 4.0]
        temps = [5.0, 5.0, 5.0, 5.0]
        cutoff, effective = rank_slots_true_cost(prices, temps, 30)
        # nslots = 30 // 15 = 2, so top-2 effective costs blocked
        sorted_desc = sorted(effective, reverse=True)
        assert cutoff == pytest.approx(sorted_desc[1])

    def test_none_temps_fall_back_to_raw_price(self) -> None:
        prices = [1.0, 2.0, 3.0]
        temps: list[float | None] = [None, None, None]
        _cutoff, effective = rank_slots_true_cost(prices, temps, 15)
        # With None temps, effective = raw prices
        assert effective == prices

    def test_mixed_temps(self) -> None:
        prices = [2.0, 2.0, 2.0]
        temps: list[float | None] = [10.0, None, -20.0]
        _, effective = rank_slots_true_cost(prices, temps, 15)
        # Slot 0: 2.0 / COP(10) = 2.0/3.8
        # Slot 1: 2.0 (raw, no temp)
        # Slot 2: 2.0 / COP(-20) = 2.0/1.5
        assert effective[0] == pytest.approx(2.0 / 3.8)
        assert effective[1] == pytest.approx(2.0)
        assert effective[2] == pytest.approx(2.0 / 1.5)

    def test_short_temps_list(self) -> None:
        prices = [1.0, 2.0, 3.0]
        temps: list[float | None] = [5.0]
        _, effective = rank_slots_true_cost(prices, temps, 15)
        # Only first slot gets COP weighting, rest fall back to raw
        assert effective[0] == pytest.approx(true_cost(1.0, 5.0))
        assert effective[1] == pytest.approx(2.0)
        assert effective[2] == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# compute_policy with COP weighting
# ---------------------------------------------------------------------------


class TestComputePolicyCopWeighting:
    """Test compute_policy with COP weighting enabled."""

    def _base_kwargs(self) -> dict:
        return {
            "price_ignore_below": 0.0,
            "pv_now": 0.0,
            "pv_ignore_above_w": 0.0,
            "current_on": False,
            "last_changed": datetime(2026, 2, 18, 8, 0, tzinfo=UTC)
            - timedelta(hours=1),
            "now": datetime(2026, 2, 18, 8, 0, tzinfo=UTC),
            "min_toggle_interval_min": 15,
        }

    def test_cop_disabled_identical_to_original(self) -> None:
        """With COP disabled, behavior is identical to original."""
        kwargs = self._base_kwargs()
        result = compute_policy(
            price=4.0,
            prices_today=[1.0, 2.0, 3.0, 4.0],
            minutes_to_block=30,
            use_cop_weighting=False,
            outdoor_temps_by_slot=None,
            **kwargs,
        )
        assert not result.cop_weighting_active
        assert result.current_true_cost is None
        assert result.blocked_now
        assert result.target_on

    def test_cop_enabled_cold_expensive_blocked(self) -> None:
        """A cold expensive slot has higher true cost and gets blocked."""
        prices = [1.0] * 24
        prices[8] = 2.0  # current hour
        temps: list[float | None] = [5.0] * 24
        temps[8] = -20.0  # very cold at current hour

        kwargs = self._base_kwargs()
        result = compute_policy(
            price=2.0,
            prices_today=prices,
            minutes_to_block=15,  # block top 1 slot
            use_cop_weighting=True,
            outdoor_temps_by_slot=temps,
            current_hour_index=8,
            **kwargs,
        )
        assert result.cop_weighting_active
        assert result.current_true_cost is not None
        assert result.blocked_now
        assert result.target_on

    def test_cop_enabled_warm_expensive_not_blocked(self) -> None:
        """A warm slot with higher raw price may not be blocked due to high COP."""
        prices = [1.0] * 24
        prices[8] = 1.5  # slightly higher raw price
        prices[20] = 1.0  # lower raw price

        temps: list[float | None] = [0.0] * 24
        temps[8] = 20.0  # very warm -> high COP -> low true cost
        temps[20] = -20.0  # very cold -> low COP -> high true cost

        kwargs = self._base_kwargs()
        result = compute_policy(
            price=1.5,
            prices_today=prices,
            minutes_to_block=15,  # block top 1 slot
            use_cop_weighting=True,
            outdoor_temps_by_slot=temps,
            current_hour_index=8,
            **kwargs,
        )
        assert result.cop_weighting_active
        assert not result.blocked_now
        assert not result.target_on

    def test_cop_enabled_none_temps_graceful_fallback(self) -> None:
        """With COP enabled but all None temps, falls back to raw price."""
        prices = [1.0, 2.0, 3.0, 4.0]
        temps: list[float | None] = [None, None, None, None]

        kwargs = self._base_kwargs()
        result = compute_policy(
            price=4.0,
            prices_today=prices,
            minutes_to_block=30,
            use_cop_weighting=True,
            outdoor_temps_by_slot=temps,
            current_hour_index=3,
            **kwargs,
        )
        assert result.cop_weighting_active
        assert result.blocked_now

    def test_cop_enabled_outdoor_temps_none_disables(self) -> None:
        """With outdoor_temps_by_slot=None, COP weighting is not active."""
        kwargs = self._base_kwargs()
        result = compute_policy(
            price=4.0,
            prices_today=[1.0, 2.0, 3.0, 4.0],
            minutes_to_block=30,
            use_cop_weighting=True,
            outdoor_temps_by_slot=None,
            **kwargs,
        )
        assert not result.cop_weighting_active

    def test_cop_enabled_with_tomorrow_prices(self) -> None:
        """Extended 48-slot window with tomorrow prices."""
        prices_today = [0.5] * 24
        prices_today[12] = 2.0
        prices_tomorrow = [0.5] * 24
        prices_tomorrow[2] = 3.0

        prices = prices_today + prices_tomorrow

        temps: list[float | None] = [0.0] * 48
        temps[12] = -15.0
        temps[26] = -15.0

        kwargs = self._base_kwargs()
        result = compute_policy(
            price=0.5,
            prices_today=prices,
            minutes_to_block=15,
            use_cop_weighting=True,
            outdoor_temps_by_slot=temps,
            current_hour_index=8,
            **kwargs,
        )
        assert result.cop_weighting_active
        assert not result.blocked_now

    def test_current_hour_index_out_of_range(self) -> None:
        """When current_hour_index is out of range, falls back to raw price."""
        prices = [1.0, 2.0, 3.0, 4.0]
        temps: list[float | None] = [0.0, 0.0, 0.0, 0.0]

        kwargs = self._base_kwargs()
        result = compute_policy(
            price=4.0,
            prices_today=prices,
            minutes_to_block=30,
            use_cop_weighting=True,
            outdoor_temps_by_slot=temps,
            current_hour_index=99,
            **kwargs,
        )
        assert result.cop_weighting_active
        assert result.blocked_now


if __name__ == "__main__":
    unittest.main()
