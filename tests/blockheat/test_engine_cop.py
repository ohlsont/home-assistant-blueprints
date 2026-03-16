"""Unit tests for COP-weighted true cost engine functions."""

from __future__ import annotations

import importlib.util
import sys
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

estimate_cop = engine.estimate_cop
true_cost = engine.true_cost
rank_slots_true_cost = engine.rank_slots_true_cost
compute_policy = engine.compute_policy


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
        # 4 slots, block top 1 (15 min). Slot 0 (hour 8) is where we are.
        # Prices: [2.0, 1.0, 1.0, 1.0] for hours 0..3 but we need 24 slots.
        # Simplify: 24 slots, current hour = 8, price at 8 = 2.0, rest = 1.0
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
        # True cost at slot 8: 2.0 / COP(-20) = 2.0/1.5 ~ 1.333
        # All others: 1.0 / COP(5) = 1.0/3.4 ~ 0.294
        # So slot 8 is the most expensive → blocked
        assert result.blocked_now
        assert result.target_on

    def test_cop_enabled_warm_expensive_not_blocked(self) -> None:
        """A warm slot with higher raw price may not be blocked due to high COP."""
        prices = [1.0] * 24
        prices[8] = 1.5  # slightly higher raw price
        prices[20] = 1.0  # lower raw price

        temps: list[float | None] = [0.0] * 24
        temps[8] = 20.0  # very warm → high COP → low true cost
        temps[20] = -20.0  # very cold → low COP → high true cost

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
        # True cost at slot 8: 1.5 / COP(20) = 1.5/4.6 ~ 0.326
        # True cost at slot 20: 1.0 / COP(-20) = 1.0/1.5 ~ 0.667
        # Slot 20 has higher true cost → it's blocked, not slot 8
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
        # All None temps → effective costs = raw prices → same as original
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
        prices_today = [1.0] * 24
        prices_tomorrow = [0.5] * 24
        prices_tomorrow[2] = 3.0  # expensive tomorrow slot
        prices = prices_today + prices_tomorrow

        temps: list[float | None] = [0.0] * 48
        temps[26] = -15.0  # cold at tomorrow 02:00

        kwargs = self._base_kwargs()
        result = compute_policy(
            price=1.0,
            prices_today=prices,
            minutes_to_block=15,
            use_cop_weighting=True,
            outdoor_temps_by_slot=temps,
            current_hour_index=8,
            **kwargs,
        )
        assert result.cop_weighting_active
        # The expensive cold tomorrow slot should be blocked, not current
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
        # Falls back to current_price >= cutoff
        assert result.blocked_now
