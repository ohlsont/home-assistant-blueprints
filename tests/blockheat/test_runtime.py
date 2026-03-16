"""Runtime adapter tests for Blockheat."""

from __future__ import annotations

import asyncio
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
    entry_data: dict[str, Any] | None = None,
    entry_options: dict[str, Any] | None = None,
    overrides: dict[str, Any] | None = None,
    seed_kwargs: dict[str, Any] | None = None,
) -> SimpleNamespace:
    base_entry_data = build_config() if entry_data is None else dict(entry_data)
    entry_options_data = {} if entry_options is None else dict(entry_options)
    if overrides:
        base_entry_data.update(overrides)
    config = {**base_entry_data, **entry_options_data}
    state_seed = seed_kwargs or {}
    seed_runtime_states(fake_hass, config, **state_seed)
    coordinator = blockheat_env.coordinator.BlockheatCoordinator(fake_hass)
    runtime = blockheat_env.runtime.BlockheatRuntime(
        fake_hass,
        "entry-test",
        config,
        coordinator,
        entry_data=base_entry_data,
        entry_options=entry_options_data,
    )

    if "policy_state" in state_seed:
        runtime._state.policy_on = str(state_seed["policy_state"]).lower() == "on"
        if runtime._state.policy_on:
            runtime._state.policy_last_changed = datetime.now(UTC) - timedelta(hours=2)

    if "saving_target" in state_seed:
        runtime._state.target_saving = float(state_seed["saving_target"])

    if "comfort_target" in state_seed:
        runtime._state.target_comfort = float(state_seed["comfort_target"])

    if "final_target" in state_seed:
        runtime._state.target_final = float(state_seed["final_target"])

    return SimpleNamespace(
        config=config,
        entry_data=base_entry_data,
        entry_options=entry_options_data,
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

    first_snapshot = await ctx.runtime.async_recompute("test_initial_write")
    first_calls = list(ctx.hass.services.calls)
    assert _service_calls_for(first_calls, "input_number", "set_value") == []
    assert _service_calls_for(
        first_calls,
        "number",
        "set_value",
        entity_id=ctx.config[ctx.const.CONF_CONTROL_NUMBER_ENTITY],
    )
    assert first_snapshot["trigger"]["reason"] == "test_initial_write"
    assert "saving_debug" in first_snapshot
    assert "comfort_debug" in first_snapshot
    assert "final_debug" in first_snapshot
    assert first_snapshot["final_debug"]["final_helper_write_performed"] is True
    assert first_snapshot["final_debug"]["control_write_performed"] is True
    assert first_snapshot["internal_state"][ctx.const.STATE_TARGET_SAVING] is not None
    assert first_snapshot["internal_state"][ctx.const.STATE_TARGET_COMFORT] is not None
    assert first_snapshot["internal_state"][ctx.const.STATE_TARGET_FINAL] is not None

    ctx.hass.services.calls.clear()
    second_snapshot = await ctx.runtime.async_recompute("test_no_delta_write")
    second_calls = list(ctx.hass.services.calls)
    assert _service_calls_for(second_calls, "input_number", "set_value") == []
    assert _service_calls_for(second_calls, "number", "set_value") == []
    assert second_snapshot["trigger"]["reason"] == "test_no_delta_write"
    assert second_snapshot["final_debug"]["final_helper_write_performed"] is False
    assert second_snapshot["final_debug"]["control_write_performed"] is False


@pytest.mark.asyncio
async def test_snapshot_contains_causal_debug_payload(
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
            blockheat_env.const.CONF_MINUTES_TO_BLOCK: 30,
        },
        seed_kwargs={
            "policy_state": "off",
            "price": 9.0,
            "prices_today": [1.0, 2.0, 9.0, 8.0],
        },
    )

    snapshot = await ctx.runtime.async_recompute("snapshot_debug")
    assert snapshot["trigger"] == {"reason": "snapshot_debug"}
    assert snapshot["saving_debug"]["source"] in {
        "heatpump_setpoint",
        "setpoint_minus_offset",
    }
    assert snapshot["comfort_debug"]["route"] in {
        "comfort",
        "maintenance",
        "storage_max",
    }
    assert snapshot["final_debug"]["source"] == "saving"
    assert snapshot["final_debug"]["control_write_performed"] is True


@pytest.mark.asyncio
async def test_snapshot_exposes_daikin_config_debug_views(
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
    disabled_snapshot = await disabled_ctx.runtime.async_recompute("config_debug_off")
    assert (
        disabled_snapshot["config_debug"]["entry_data"][
            disabled_ctx.const.CONF_ENABLE_DAIKIN_CONSUMER
        ]
        is False
    )
    assert (
        disabled_snapshot["config_debug"]["entry_options"][
            disabled_ctx.const.CONF_ENABLE_DAIKIN_CONSUMER
        ]
        is None
    )
    assert (
        disabled_snapshot["config_debug"]["effective"][
            disabled_ctx.const.CONF_ENABLE_DAIKIN_CONSUMER
        ]
        is False
    )

    enabled_ctx = _make_runtime_context(
        blockheat_env,
        fake_hass,
        build_config,
        seed_runtime_states,
        entry_options={
            blockheat_env.const.CONF_ENABLE_DAIKIN_CONSUMER: True,
            blockheat_env.const.CONF_DAIKIN_CLIMATE_ENTITY: "climate.daikin_upstairs",
            blockheat_env.const.CONF_DAIKIN_NORMAL_TEMPERATURE: 22.0,
            blockheat_env.const.CONF_DAIKIN_SAVING_TEMPERATURE: 20.0,
            blockheat_env.const.CONF_DAIKIN_OUTDOOR_TEMP_THRESHOLD: -10.0,
        },
        seed_kwargs={
            "policy_state": "off",
            "price": 0.0,
            "prices_today": [0.0, 0.0, 0.0, 0.0],
        },
    )
    enabled_ctx.hass.states.set(
        "climate.daikin_upstairs",
        "heat",
        attributes={"temperature": 19.0},
    )
    enabled_ctx.hass.states.set("sensor.daikin_outdoor", "5.0")
    enabled_snapshot = await enabled_ctx.runtime.async_recompute("config_debug_on")
    assert (
        enabled_snapshot["config_debug"]["entry_options"][
            enabled_ctx.const.CONF_ENABLE_DAIKIN_CONSUMER
        ]
        is True
    )
    assert (
        enabled_snapshot["config_debug"]["effective"][
            enabled_ctx.const.CONF_DAIKIN_CLIMATE_ENTITY
        ]
        == "climate.daikin_upstairs"
    )


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
            blockheat_env.const.CONF_MINUTES_TO_BLOCK: 30,
        },
        seed_kwargs={
            "price": 9.0,
            "prices_today": [1.0, 2.0, 9.0, 8.0],
            "policy_state": "off",
        },
    )

    on_snapshot = await ctx.runtime.async_recompute("policy_turn_on")
    assert _service_calls_for(ctx.hass.services.calls, "input_boolean", "turn_on") == []
    assert on_snapshot["policy"]["transition"] == "on"
    assert on_snapshot["internal_state"][ctx.const.STATE_POLICY_ON] is True
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
    # Push last_changed back so the hardcoded 15-min debounce is satisfied.
    ctx.runtime._state.policy_last_changed = datetime.now(UTC) - timedelta(hours=1)
    off_snapshot = await ctx.runtime.async_recompute("policy_turn_off")
    assert (
        _service_calls_for(ctx.hass.services.calls, "input_boolean", "turn_off") == []
    )
    assert off_snapshot["policy"]["transition"] == "off"
    assert off_snapshot["internal_state"][ctx.const.STATE_POLICY_ON] is False
    off_events = [
        item
        for item in ctx.hass.bus.fired
        if item["event_type"] == ctx.const.EVENT_BLOCKHEAT_POLICY_CHANGED
    ]
    assert off_events
    assert off_events[-1]["event_data"]["state"] == "off"


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

    missing_ctx = _make_runtime_context(
        blockheat_env,
        fake_hass,
        build_config,
        seed_runtime_states,
        overrides={
            blockheat_env.const.CONF_ENABLE_DAIKIN_CONSUMER: True,
            blockheat_env.const.CONF_DAIKIN_CLIMATE_ENTITY: "",
        },
    )
    missing_snapshot = await missing_ctx.runtime.async_recompute(
        "consumers_missing_entity"
    )
    assert missing_snapshot["daikin"]["skipped"] == "missing_climate_entity"

    write_ctx = _make_runtime_context(
        blockheat_env,
        fake_hass,
        build_config,
        seed_runtime_states,
        overrides={
            blockheat_env.const.CONF_ENABLE_DAIKIN_CONSUMER: True,
            blockheat_env.const.CONF_DAIKIN_CLIMATE_ENTITY: "climate.daikin_upstairs",
            blockheat_env.const.CONF_MINUTES_TO_BLOCK: 30,
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
    await write_ctx.runtime.async_recompute("consumers_write")

    daikin_calls = _service_calls_for(
        write_ctx.hass.services.calls,
        "climate",
        "set_temperature",
        entity_id="climate.daikin_upstairs",
    )
    assert daikin_calls


@pytest.mark.asyncio
async def test_state_change_event_populates_trigger_context(
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
            blockheat_env.const.CONF_ENABLE_DAIKIN_CONSUMER: True,
            blockheat_env.const.CONF_DAIKIN_CLIMATE_ENTITY: "climate.daikin_upstairs",
        },
    )
    await ctx.runtime.async_setup()

    for task in list(ctx.hass.created_tasks):
        await task
    ctx.hass.created_tasks.clear()

    tracker = ctx.hass.state_trackers[0]
    tracked_entities = set(tracker["entity_ids"])
    assert ctx.config[ctx.const.CONF_CONTROL_NUMBER_ENTITY] not in tracked_entities
    assert "climate.daikin_upstairs" not in tracked_entities
    tracker["callback"](
        SimpleNamespace(
            data={"entity_id": ctx.config[ctx.const.CONF_COMFORT_ROOM_1_SENSOR]}
        )
    )
    await asyncio.gather(*ctx.hass.created_tasks)

    snapshot = ctx.coordinator.data
    assert snapshot is not None
    assert snapshot["trigger"]["reason"] == "state_change"
    assert snapshot["trigger"]["source"] == "state_change"
    assert (
        snapshot["trigger"]["entity_id"]
        == ctx.config[ctx.const.CONF_COMFORT_ROOM_1_SENSOR]
    )


@pytest.mark.asyncio
async def test_logbook_only_records_meaningful_changes(
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
            blockheat_env.const.CONF_MINUTES_TO_BLOCK: 30,
        },
        seed_kwargs={
            "policy_state": "off",
            "price": 9.0,
            "prices_today": [1.0, 2.0, 9.0, 8.0],
        },
    )
    ctx.hass.services.available.add(("logbook", "log"))

    await ctx.runtime.async_recompute("change_pass")
    first_logs = _service_calls_for(ctx.hass.services.calls, "logbook", "log")
    assert first_logs
    assert any(
        "trigger=change_pass" in item["payload"].get("message", "")
        for item in first_logs
    )

    ctx.hass.services.calls.clear()
    await ctx.runtime.async_recompute("no_change_pass")
    second_logs = _service_calls_for(ctx.hass.services.calls, "logbook", "log")
    assert second_logs == []


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

    snapshot = await ctx.runtime.async_recompute("logbook_missing")
    assert snapshot["internal_state"][ctx.const.STATE_POLICY_ON] is True


@pytest.mark.asyncio
async def test_recompute_tolerates_unavailable_service(
    blockheat_env: SimpleNamespace,
    fake_hass: Any,
    build_config: Any,
    seed_runtime_states: Any,
) -> None:
    """Setup completes when number.set_value is not yet registered (boot race)."""
    fake_hass.services.available.discard(("number", "set_value"))
    ctx = _make_runtime_context(
        blockheat_env,
        fake_hass,
        build_config,
        seed_runtime_states,
        overrides={
            blockheat_env.const.CONF_MINUTES_TO_BLOCK: 30,
        },
        seed_kwargs={
            "policy_state": "off",
            "price": 9.0,
            "prices_today": [1.0, 2.0, 9.0, 8.0],
        },
    )

    snapshot = await ctx.runtime.async_recompute("boot_race")
    assert snapshot["final_target"] is not None
    assert _service_calls_for(ctx.hass.services.calls, "number", "set_value") == []


@pytest.mark.asyncio
async def test_recompute_tolerates_service_error_on_entity(
    blockheat_env: SimpleNamespace,
    fake_hass: Any,
    build_config: Any,
    seed_runtime_states: Any,
) -> None:
    """Recompute completes when climate.set_temperature raises HomeAssistantError."""
    ctx = _make_runtime_context(
        blockheat_env,
        fake_hass,
        build_config,
        seed_runtime_states,
        overrides={
            blockheat_env.const.CONF_ENABLE_DAIKIN_CONSUMER: True,
            blockheat_env.const.CONF_DAIKIN_CLIMATE_ENTITY: "climate.daikin_upstairs",
            blockheat_env.const.CONF_MINUTES_TO_BLOCK: 30,
        },
        seed_kwargs={
            "policy_state": "off",
            "price": 9.0,
            "prices_today": [1.0, 2.0, 9.0, 8.0],
        },
    )
    ctx.hass.states.set(
        "climate.daikin_upstairs",
        "heat",
        attributes={"temperature": 22.0},
    )
    ctx.hass.services.raise_ha_error.add(("climate", "set_temperature"))

    snapshot = await ctx.runtime.async_recompute("bad_entity")
    assert snapshot["daikin"]["enabled"] is True
    assert snapshot["daikin"]["written"] is True
    assert snapshot["final_target"] is not None


@pytest.mark.asyncio
async def test_forecast_disabled_by_default(
    blockheat_env: SimpleNamespace,
    fake_hass: Any,
    build_config: Any,
    seed_runtime_states: Any,
) -> None:
    """Default config has forecast optimization off — COP weighting inactive."""
    ctx = _make_runtime_context(
        blockheat_env,
        fake_hass,
        build_config,
        seed_runtime_states,
        overrides={
            blockheat_env.const.CONF_MINUTES_TO_BLOCK: 30,
        },
        seed_kwargs={
            "price": 9.0,
            "prices_today": [1.0, 2.0, 9.0, 8.0],
            "policy_state": "off",
        },
    )

    snapshot = await ctx.runtime.async_recompute("forecast_default")
    assert snapshot["policy"]["cop_weighting_active"] is False
    assert snapshot["policy"]["current_true_cost"] is None


@pytest.mark.asyncio
async def test_forecast_enabled_with_weather_entity(
    blockheat_env: SimpleNamespace,
    fake_hass: Any,
    build_config: Any,
    seed_runtime_states: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Forecast enabled + weather entity + forecast service → COP weighting active."""
    fixed_now = datetime(2026, 3, 16, 10, 0, tzinfo=UTC)
    monkeypatch.setattr(blockheat_env.runtime.dt_util, "utcnow", lambda: fixed_now)

    prices_today = [1.0] * 24
    prices_today[10] = 9.0  # expensive at hour 10 (the current hour)

    ctx = _make_runtime_context(
        blockheat_env,
        fake_hass,
        build_config,
        seed_runtime_states,
        overrides={
            blockheat_env.const.CONF_ENABLE_FORECAST_OPTIMIZATION: True,
            blockheat_env.const.CONF_WEATHER_ENTITY: "weather.smhi",
            blockheat_env.const.CONF_MINUTES_TO_BLOCK: 30,
        },
        seed_kwargs={
            "price": 9.0,
            "prices_today": prices_today,
            "policy_state": "off",
        },
    )

    # Seed nordpool tomorrow prices so the window extends.
    ctx.hass.states.set(
        ctx.config[ctx.const.CONF_NORDPOOL_PRICE],
        "9.0",
        attributes={
            "today": prices_today,
            "tomorrow": [1.0] * 24,
        },
    )

    # Build forecast entries for all 48 hours.
    forecast_entries = [
        {
            "datetime": f"2026-03-16T{h:02d}:00:00+00:00",
            "temperature": 0.0,
        }
        for h in range(24)
    ] + [
        {
            "datetime": f"2026-03-17T{h:02d}:00:00+00:00",
            "temperature": 0.0,
        }
        for h in range(24)
    ]

    def _forecast_handler(call: Any) -> dict[str, Any]:
        return {"weather.smhi": {"forecast": forecast_entries}}

    ctx.hass.services.async_register("weather", "get_forecasts", _forecast_handler)

    snapshot = await ctx.runtime.async_recompute("forecast_enabled")
    assert snapshot["policy"]["cop_weighting_active"] is True
    assert isinstance(snapshot["policy"]["current_true_cost"], float)


@pytest.mark.asyncio
async def test_forecast_enabled_service_unavailable(
    blockheat_env: SimpleNamespace,
    fake_hass: Any,
    build_config: Any,
    seed_runtime_states: Any,
) -> None:
    """Forecast enabled but weather service raises → graceful fallback."""
    ctx = _make_runtime_context(
        blockheat_env,
        fake_hass,
        build_config,
        seed_runtime_states,
        overrides={
            blockheat_env.const.CONF_ENABLE_FORECAST_OPTIMIZATION: True,
            blockheat_env.const.CONF_WEATHER_ENTITY: "weather.smhi",
            blockheat_env.const.CONF_MINUTES_TO_BLOCK: 30,
        },
        seed_kwargs={
            "price": 9.0,
            "prices_today": [1.0, 2.0, 9.0, 8.0],
            "policy_state": "off",
        },
    )

    # Register service but make it raise.
    ctx.hass.services.available.add(("weather", "get_forecasts"))
    ctx.hass.services.raise_not_found.add(("weather", "get_forecasts"))

    snapshot = await ctx.runtime.async_recompute("forecast_error")
    assert snapshot["policy"]["cop_weighting_active"] is False


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

    await ctx.runtime.async_unload()
    assert all(not item["active"] for item in ctx.hass.state_trackers)
    assert all(not item["active"] for item in ctx.hass.interval_trackers)
    assert all(not item["active"] for item in ctx.hass.bus.once_listeners)
    assert all(not item["active"] for item in ctx.hass.later_calls)
