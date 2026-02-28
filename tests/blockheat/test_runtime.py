"""Runtime adapter tests for Blockheat."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest


def _make_runtime_context(
    blockheat_env: SimpleNamespace,
    fake_hass: Any,
    build_config: Any,
    seed_runtime_states: Any,
    *,
    overrides: dict[str, Any] | None = None,
    seed_kwargs: dict[str, Any] | None = None,
) -> SimpleNamespace:
    config = build_config(overrides or {})
    seed_runtime_states(fake_hass, config, **(seed_kwargs or {}))
    coordinator = blockheat_env.coordinator.BlockheatCoordinator(fake_hass)
    runtime = blockheat_env.runtime.BlockheatRuntime(fake_hass, config, coordinator)
    return SimpleNamespace(
        config=config,
        const=blockheat_env.const,
        runtime_module=blockheat_env.runtime,
        runtime=runtime,
        coordinator=coordinator,
        hass=fake_hass,
    )


def _service_calls_for(
    calls: list[dict[str, Any]],
    domain: str,
    service: str,
    *,
    entity_id: str | None = None,
) -> list[dict[str, Any]]:
    return [
        item
        for item in calls
        if item["domain"] == domain
        and item["service"] == service
        and (entity_id is None or item["payload"].get("entity_id") == entity_id)
    ]


@pytest.mark.asyncio
async def test_async_recompute_writes_expected_targets_then_skips_small_deltas(
    blockheat_env: SimpleNamespace,
    fake_hass: Any,
    build_config: Any,
    seed_runtime_states: Any,
) -> None:
    ctx = _make_runtime_context(
        blockheat_env,
        fake_hass,
        build_config,
        seed_runtime_states,
        overrides={
            blockheat_env.const.CONF_MINUTES_TO_BLOCK: 0,
            blockheat_env.const.CONF_MIN_TOGGLE_INTERVAL_MIN: 0,
        },
        seed_kwargs={
            "saving_target": 0.0,
            "comfort_target": 0.0,
            "final_target": 0.0,
            "control_value": 0.0,
            "price": 0.0,
            "prices_today": [0.0, 0.0, 0.0, 0.0],
        },
    )

    await ctx.runtime.async_recompute("test_initial_write")
    first_calls = list(ctx.hass.services.calls)
    assert _service_calls_for(
        first_calls,
        "input_number",
        "set_value",
        entity_id=ctx.config[ctx.const.CONF_TARGET_SAVING_HELPER],
    )
    assert _service_calls_for(
        first_calls,
        "input_number",
        "set_value",
        entity_id=ctx.config[ctx.const.CONF_TARGET_COMFORT_HELPER],
    )
    assert _service_calls_for(
        first_calls,
        "input_number",
        "set_value",
        entity_id=ctx.config[ctx.const.CONF_TARGET_FINAL_HELPER],
    )
    assert _service_calls_for(
        first_calls,
        "number",
        "set_value",
        entity_id=ctx.config[ctx.const.CONF_CONTROL_NUMBER_ENTITY],
    )

    ctx.hass.services.calls.clear()
    await ctx.runtime.async_recompute("test_no_delta_write")
    second_calls = list(ctx.hass.services.calls)
    assert _service_calls_for(second_calls, "input_number", "set_value") == []
    assert _service_calls_for(second_calls, "number", "set_value") == []


@pytest.mark.asyncio
async def test_snapshot_includes_additive_debug_fields(
    blockheat_env: SimpleNamespace,
    fake_hass: Any,
    build_config: Any,
    seed_runtime_states: Any,
) -> None:
    ctx = _make_runtime_context(
        blockheat_env,
        fake_hass,
        build_config,
        seed_runtime_states,
        overrides={
            blockheat_env.const.CONF_MIN_TOGGLE_INTERVAL_MIN: 0,
            blockheat_env.const.CONF_MINUTES_TO_BLOCK: 30,
        },
        seed_kwargs={
            "policy_state": "off",
            "price": 9.0,
            "prices_today": [1.0, 2.0, 9.0, 8.0],
            "control_value": 20.0,
        },
    )

    snapshot = await ctx.runtime.async_recompute("debug_snapshot")
    assert snapshot["snapshot_schema_version"] == 1
    assert snapshot["policy"]["transition_reason"] == "top_n_blocked"
    assert snapshot["comfort_target_debug"]["comfort_satisfied"] is False
    assert "boost_clamped" in snapshot["comfort_target_debug"]
    assert snapshot["final_target_debug"]["source"] == "saving"
    assert snapshot["final_target_debug"]["control_write_applied"] is True
    assert isinstance(snapshot["final_target_debug"]["control_write_delta"], float)
    assert snapshot["daikin"]["debug"]["action"] == "disabled"
    assert snapshot["floor"]["debug"]["action"] == "disabled"


@pytest.mark.asyncio
async def test_policy_transition_fires_events_and_toggles_boolean(
    blockheat_env: SimpleNamespace,
    fake_hass: Any,
    build_config: Any,
    seed_runtime_states: Any,
) -> None:
    ctx = _make_runtime_context(
        blockheat_env,
        fake_hass,
        build_config,
        seed_runtime_states,
        overrides={
            blockheat_env.const.CONF_MIN_TOGGLE_INTERVAL_MIN: 0,
            blockheat_env.const.CONF_MINUTES_TO_BLOCK: 30,
        },
        seed_kwargs={
            "price": 9.0,
            "prices_today": [1.0, 2.0, 9.0, 8.0],
            "policy_state": "off",
        },
    )

    await ctx.runtime.async_recompute("policy_turn_on")
    assert _service_calls_for(
        ctx.hass.services.calls,
        "input_boolean",
        "turn_on",
        entity_id=ctx.config[ctx.const.CONF_TARGET_BOOLEAN],
    )
    fired_types = [item["event_type"] for item in ctx.hass.bus.fired]
    assert ctx.const.EVENT_ENERGY_SAVING_STATE_CHANGED in fired_types
    assert ctx.const.EVENT_BLOCKHEAT_POLICY_CHANGED in fired_types

    ctx.hass.services.calls.clear()
    ctx.hass.bus.fired.clear()
    ctx.hass.states.set(
        ctx.config[ctx.const.CONF_NORDPOOL_PRICE],
        "0.0",
        attributes={"today": [1.0, 2.0, 9.0, 8.0]},
    )
    await ctx.runtime.async_recompute("policy_turn_off")
    assert _service_calls_for(
        ctx.hass.services.calls,
        "input_boolean",
        "turn_off",
        entity_id=ctx.config[ctx.const.CONF_TARGET_BOOLEAN],
    )
    off_events = [
        item
        for item in ctx.hass.bus.fired
        if item["event_type"] == ctx.const.EVENT_BLOCKHEAT_POLICY_CHANGED
    ]
    assert off_events
    assert off_events[-1]["event_data"]["state"] == "off"


@pytest.mark.asyncio
async def test_fallback_arms_after_delay_and_writes_last_trigger(
    blockheat_env: SimpleNamespace,
    fake_hass: Any,
    build_config: Any,
    seed_runtime_states: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = _make_runtime_context(
        blockheat_env,
        fake_hass,
        build_config,
        seed_runtime_states,
        overrides={
            blockheat_env.const.CONF_MINUTES_TO_BLOCK: 0,
            blockheat_env.const.CONF_ELECTRIC_FALLBACK_MINUTES: 30,
        },
        seed_kwargs={
            "room1_temp": 20.0,
            "room2_temp": 20.0,
            "fallback_active": "off",
            "price": 0.0,
            "prices_today": [0.0, 0.0, 0.0, 0.0],
        },
    )

    start_time = datetime(2026, 2, 19, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(ctx.runtime_module.dt_util, "utcnow", lambda: start_time)
    await ctx.runtime.async_recompute("fallback_wait_start")

    assert ctx.runtime._fallback_arm_since is not None
    assert any(item["active"] for item in ctx.hass.later_calls)
    assert (
        ctx.hass.states.get(ctx.config[ctx.const.CONF_FALLBACK_ACTIVE_BOOLEAN]).state
        == "off"
    )

    monkeypatch.setattr(
        ctx.runtime_module.dt_util,
        "utcnow",
        lambda: start_time + timedelta(minutes=31),
    )
    await ctx.runtime.async_recompute("fallback_wait_elapsed")
    assert (
        ctx.hass.states.get(ctx.config[ctx.const.CONF_FALLBACK_ACTIVE_BOOLEAN]).state
        == "on"
    )
    assert _service_calls_for(
        ctx.hass.services.calls,
        "input_datetime",
        "set_datetime",
        entity_id=ctx.config[ctx.const.CONF_ELECTRIC_FALLBACK_LAST_TRIGGER],
    )


@pytest.mark.asyncio
async def test_fallback_release_by_policy_and_recovery(
    blockheat_env: SimpleNamespace,
    fake_hass: Any,
    build_config: Any,
    seed_runtime_states: Any,
) -> None:
    policy_ctx = _make_runtime_context(
        blockheat_env,
        fake_hass,
        build_config,
        seed_runtime_states,
        overrides={
            blockheat_env.const.CONF_MIN_TOGGLE_INTERVAL_MIN: 0,
            blockheat_env.const.CONF_MINUTES_TO_BLOCK: 30,
        },
        seed_kwargs={
            "policy_state": "on",
            "fallback_active": "on",
            "price": 9.0,
            "prices_today": [1.0, 2.0, 9.0, 8.0],
        },
    )
    await policy_ctx.runtime.async_recompute("release_by_policy")
    assert _service_calls_for(
        policy_ctx.hass.services.calls,
        "input_boolean",
        "turn_off",
        entity_id=policy_ctx.config[policy_ctx.const.CONF_FALLBACK_ACTIVE_BOOLEAN],
    )

    policy_ctx.hass.services.calls.clear()
    policy_ctx.hass.states.set(
        policy_ctx.config[policy_ctx.const.CONF_TARGET_BOOLEAN], "off"
    )
    policy_ctx.hass.states.set(
        policy_ctx.config[policy_ctx.const.CONF_NORDPOOL_PRICE],
        "0.0",
        attributes={"today": [0.0, 0.0, 0.0, 0.0]},
    )
    policy_ctx.hass.states.set(
        policy_ctx.config[policy_ctx.const.CONF_FALLBACK_ACTIVE_BOOLEAN], "on"
    )
    policy_ctx.hass.states.set(
        policy_ctx.config[policy_ctx.const.CONF_COMFORT_ROOM_1_SENSOR], "22.0"
    )
    policy_ctx.hass.states.set(
        policy_ctx.config[policy_ctx.const.CONF_COMFORT_ROOM_2_SENSOR], "22.0"
    )
    await policy_ctx.runtime.async_recompute("release_by_recovery")
    assert _service_calls_for(
        policy_ctx.hass.services.calls,
        "input_boolean",
        "turn_off",
        entity_id=policy_ctx.config[policy_ctx.const.CONF_FALLBACK_ACTIVE_BOOLEAN],
    )


@pytest.mark.asyncio
async def test_optional_consumers_disabled_missing_and_write_paths(
    blockheat_env: SimpleNamespace,
    fake_hass: Any,
    build_config: Any,
    seed_runtime_states: Any,
) -> None:
    disabled_ctx = _make_runtime_context(
        blockheat_env,
        fake_hass,
        build_config,
        seed_runtime_states,
    )
    disabled_snapshot = await disabled_ctx.runtime.async_recompute("consumers_disabled")
    assert disabled_snapshot["daikin"]["enabled"] is False
    assert disabled_snapshot["floor"]["enabled"] is False
    assert disabled_snapshot["daikin"]["debug"]["action"] == "disabled"
    assert disabled_snapshot["floor"]["debug"]["action"] == "disabled"

    missing_ctx = _make_runtime_context(
        blockheat_env,
        fake_hass,
        build_config,
        seed_runtime_states,
        overrides={
            blockheat_env.const.CONF_ENABLE_DAIKIN_CONSUMER: True,
            blockheat_env.const.CONF_DAIKIN_CLIMATE_ENTITY: "",
            blockheat_env.const.CONF_ENABLE_FLOOR_CONSUMER: True,
            blockheat_env.const.CONF_FLOOR_CLIMATE_ENTITY: "",
        },
    )
    missing_snapshot = await missing_ctx.runtime.async_recompute(
        "consumers_missing_entity"
    )
    assert missing_snapshot["daikin"]["skipped"] == "missing_climate_entity"
    assert missing_snapshot["floor"]["skipped"] == "missing_climate_entity"
    assert missing_snapshot["daikin"]["debug"]["skip_reason"] == "missing_climate_entity"
    assert missing_snapshot["floor"]["debug"]["skip_reason"] == "missing_climate_entity"

    write_ctx = _make_runtime_context(
        blockheat_env,
        fake_hass,
        build_config,
        seed_runtime_states,
        overrides={
            blockheat_env.const.CONF_ENABLE_DAIKIN_CONSUMER: True,
            blockheat_env.const.CONF_DAIKIN_CLIMATE_ENTITY: "climate.daikin_upstairs",
            blockheat_env.const.CONF_ENABLE_FLOOR_CONSUMER: True,
            blockheat_env.const.CONF_FLOOR_CLIMATE_ENTITY: "climate.floor_heat",
            blockheat_env.const.CONF_MIN_TOGGLE_INTERVAL_MIN: 0,
            blockheat_env.const.CONF_MINUTES_TO_BLOCK: 30,
            blockheat_env.const.CONF_FLOOR_MIN_SWITCH_INTERVAL_MIN: 0,
        },
        seed_kwargs={
            "policy_state": "off",
            "price": 9.0,
            "prices_today": [1.0, 2.0, 9.0, 8.0],
        },
    )
    write_ctx.hass.states.set(
        "climate.daikin_upstairs",
        "heat",
        attributes={"temperature": 22.0},
    )
    write_ctx.hass.states.set(
        "climate.floor_heat",
        "heat",
        attributes={
            "temperature": 22.5,
            "min_temp": 5.0,
            "hvac_modes": ["heat", "auto"],
            "preset_modes": ["manual"],
        },
    )
    await write_ctx.runtime.async_recompute("consumers_write")

    daikin_calls = _service_calls_for(
        write_ctx.hass.services.calls,
        "climate",
        "set_temperature",
        entity_id="climate.daikin_upstairs",
    )
    floor_calls = _service_calls_for(
        write_ctx.hass.services.calls,
        "climate",
        "set_temperature",
        entity_id="climate.floor_heat",
    )
    assert daikin_calls
    assert floor_calls
    write_snapshot = write_ctx.coordinator.data
    assert write_snapshot is not None
    assert write_snapshot["daikin"]["debug"]["action"] == "write"
    assert write_snapshot["floor"]["debug"]["action"] == "set_soft_off"


@pytest.mark.asyncio
async def test_logbook_service_not_found_is_tolerated(
    blockheat_env: SimpleNamespace,
    fake_hass: Any,
    build_config: Any,
    seed_runtime_states: Any,
) -> None:
    ctx = _make_runtime_context(
        blockheat_env,
        fake_hass,
        build_config,
        seed_runtime_states,
        overrides={
            blockheat_env.const.CONF_MIN_TOGGLE_INTERVAL_MIN: 0,
            blockheat_env.const.CONF_MINUTES_TO_BLOCK: 30,
        },
        seed_kwargs={
            "policy_state": "off",
            "price": 9.0,
            "prices_today": [1.0, 2.0, 9.0, 8.0],
        },
    )
    ctx.hass.services.available.add(("logbook", "log"))
    ctx.hass.services.raise_not_found.add(("logbook", "log"))

    await ctx.runtime.async_recompute("logbook_missing")
    assert ctx.hass.states.get(ctx.config[ctx.const.CONF_TARGET_BOOLEAN]).state == "on"


@pytest.mark.asyncio
async def test_async_unload_clears_timers_and_subscriptions(
    blockheat_env: SimpleNamespace,
    fake_hass: Any,
    build_config: Any,
    seed_runtime_states: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ctx = _make_runtime_context(
        blockheat_env,
        fake_hass,
        build_config,
        seed_runtime_states,
        overrides={blockheat_env.const.CONF_MINUTES_TO_BLOCK: 0},
        seed_kwargs={
            "room1_temp": 20.0,
            "room2_temp": 20.0,
            "price": 0.0,
            "prices_today": [0.0, 0.0, 0.0, 0.0],
        },
    )

    monkeypatch.setattr(
        ctx.runtime_module.dt_util,
        "utcnow",
        lambda: datetime(2026, 2, 19, 12, 0, tzinfo=UTC),
    )
    await ctx.runtime.async_setup()

    assert ctx.hass.state_trackers
    assert ctx.hass.interval_trackers
    assert ctx.hass.bus.once_listeners
    assert any(item["active"] for item in ctx.hass.later_calls)

    await ctx.runtime.async_unload()
    assert all(not item["active"] for item in ctx.hass.state_trackers)
    assert all(not item["active"] for item in ctx.hass.interval_trackers)
    assert all(not item["active"] for item in ctx.hass.bus.once_listeners)
    assert all(not item["active"] for item in ctx.hass.later_calls)
    assert ctx.runtime._fallback_arm_timer_unsub is None
