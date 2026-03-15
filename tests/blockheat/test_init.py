"""Integration setup tests for blockheat.__init__."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from types import SimpleNamespace


class _FakeRuntime:
    def __init__(
        self,
        hass: Any,
        entry_id: str,
        config: dict[str, Any],
        coordinator: Any,
        *,
        entry_data: dict[str, Any] | None = None,
        entry_options: dict[str, Any] | None = None,
    ) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self.config = config
        self.coordinator = coordinator
        self.entry_data = {} if entry_data is None else dict(entry_data)
        self.entry_options = {} if entry_options is None else dict(entry_options)
        self.setup_calls = 0
        self.unload_calls = 0
        self.recompute_calls: list[str] = []

    async def async_setup(self) -> None:
        self.setup_calls += 1

    async def async_unload(self) -> None:
        self.unload_calls += 1

    async def async_recompute(self, reason: str = "manual") -> dict[str, Any]:
        self.recompute_calls.append(reason)
        return {"reason": reason}


class _FakeCoordinator:
    def __init__(self, hass: Any) -> None:
        self.hass = hass
        self.data: dict[str, Any] | None = None

    def async_set_updated_data(self, data: dict[str, Any]) -> None:
        self.data = data


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
async def test_setup_entry_registers_services_once_and_resolves_runtimes(
    blockheat_env: SimpleNamespace,
    fake_hass: Any,
    build_config: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = blockheat_env.package
    const = blockheat_env.const
    monkeypatch.setattr(package, "BlockheatRuntime", _FakeRuntime)
    monkeypatch.setattr(package, "BlockheatCoordinator", _FakeCoordinator)

    await package.async_setup(fake_hass, {})

    entry_1 = blockheat_env.FakeConfigEntry("entry-1", data=build_config())
    entry_2 = blockheat_env.FakeConfigEntry("entry-2", data=build_config())
    assert await package.async_setup_entry(fake_hass, entry_1) is True
    assert await package.async_setup_entry(fake_hass, entry_2) is True

    assert fake_hass.services.has_service(const.DOMAIN, const.SERVICE_RECOMPUTE)
    assert fake_hass.services.has_service(const.DOMAIN, const.SERVICE_DUMP_DIAGNOSTICS)
    assert (
        fake_hass.services.register_calls.count((const.DOMAIN, const.SERVICE_RECOMPUTE))
        == 1
    )
    assert (
        fake_hass.services.register_calls.count(
            (const.DOMAIN, const.SERVICE_DUMP_DIAGNOSTICS)
        )
        == 1
    )

    all_runtimes = package._resolve_runtimes(fake_hass, None)
    one_runtime = package._resolve_runtimes(fake_hass, "entry-1")
    missing_runtime = package._resolve_runtimes(fake_hass, "missing")
    assert len(all_runtimes) == 2
    assert len(one_runtime) == 1
    assert missing_runtime == []


@pytest.mark.asyncio
async def test_unload_entry_unregisters_services_only_after_last_entry(
    blockheat_env: SimpleNamespace,
    fake_hass: Any,
    build_config: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = blockheat_env.package
    const = blockheat_env.const
    monkeypatch.setattr(package, "BlockheatRuntime", _FakeRuntime)
    monkeypatch.setattr(package, "BlockheatCoordinator", _FakeCoordinator)

    await package.async_setup(fake_hass, {})

    entry_1 = blockheat_env.FakeConfigEntry("entry-1", data=build_config())
    entry_2 = blockheat_env.FakeConfigEntry("entry-2", data=build_config())
    await package.async_setup_entry(fake_hass, entry_1)
    await package.async_setup_entry(fake_hass, entry_2)

    assert await package.async_unload_entry(fake_hass, entry_1) is True
    assert fake_hass.services.has_service(const.DOMAIN, const.SERVICE_RECOMPUTE)
    assert fake_hass.services.has_service(const.DOMAIN, const.SERVICE_DUMP_DIAGNOSTICS)

    assert await package.async_unload_entry(fake_hass, entry_2) is True
    assert not fake_hass.services.has_service(const.DOMAIN, const.SERVICE_RECOMPUTE)
    assert not fake_hass.services.has_service(
        const.DOMAIN, const.SERVICE_DUMP_DIAGNOSTICS
    )
    assert entry_1._listener_unsubscribed is True
    assert entry_2._listener_unsubscribed is True


@pytest.mark.asyncio
async def test_recompute_service_invokes_selected_runtime(
    blockheat_env: SimpleNamespace,
    fake_hass: Any,
    build_config: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = blockheat_env.package
    const = blockheat_env.const
    monkeypatch.setattr(package, "BlockheatRuntime", _FakeRuntime)
    monkeypatch.setattr(package, "BlockheatCoordinator", _FakeCoordinator)

    await package.async_setup(fake_hass, {})

    entry_1 = blockheat_env.FakeConfigEntry("entry-1", data=build_config())
    entry_2 = blockheat_env.FakeConfigEntry("entry-2", data=build_config())
    await package.async_setup_entry(fake_hass, entry_1)
    await package.async_setup_entry(fake_hass, entry_2)

    await fake_hass.services.async_call(
        const.DOMAIN,
        const.SERVICE_RECOMPUTE,
        {"entry_id": "entry-2"},
        blocking=True,
    )

    runtime_1 = fake_hass.data[const.DOMAIN]["entry-1"][package.ENTRY_RUNTIME]
    runtime_2 = fake_hass.data[const.DOMAIN]["entry-2"][package.ENTRY_RUNTIME]
    assert runtime_1.recompute_calls == []
    assert runtime_2.recompute_calls == ["service_recompute"]


@pytest.mark.asyncio
async def test_services_can_optionally_return_snapshot_payloads(
    blockheat_env: SimpleNamespace,
    fake_hass: Any,
    build_config: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = blockheat_env.package
    const = blockheat_env.const
    monkeypatch.setattr(package, "BlockheatRuntime", _FakeRuntime)
    monkeypatch.setattr(package, "BlockheatCoordinator", _FakeCoordinator)

    await package.async_setup(fake_hass, {})

    entry_1 = blockheat_env.FakeConfigEntry("entry-1", data=build_config())
    entry_2 = blockheat_env.FakeConfigEntry("entry-2", data=build_config())
    await package.async_setup_entry(fake_hass, entry_1)
    await package.async_setup_entry(fake_hass, entry_2)

    recompute_response = await fake_hass.services.async_call(
        const.DOMAIN,
        const.SERVICE_RECOMPUTE,
        {"entry_id": "entry-2"},
        blocking=True,
        return_response=True,
    )
    diagnostics_response = await fake_hass.services.async_call(
        const.DOMAIN,
        const.SERVICE_DUMP_DIAGNOSTICS,
        {"entry_id": "entry-1"},
        blocking=True,
        return_response=True,
    )

    assert recompute_response == {
        "entries": {"entry-2": {"reason": "service_recompute"}}
    }
    assert diagnostics_response == {
        "entries": {"entry-1": {"reason": "service_dump_diagnostics"}}
    }


@pytest.mark.asyncio
async def test_options_flow_saved_daikin_options_survive_reload_and_recompute(
    blockheat_env: SimpleNamespace,
    fake_hass: Any,
    build_config: Any,
    seed_runtime_states: Any,
) -> None:
    package = blockheat_env.package
    const = blockheat_env.const

    await package.async_setup(fake_hass, {})

    entry = blockheat_env.FakeConfigEntry("entry-1", data=build_config())
    seed_runtime_states(
        fake_hass,
        entry.data,
        price=0.0,
        prices_today=[0.0, 0.0, 0.0, 0.0],
        policy_state="off",
        control_value=20.0,
    )
    fake_hass.states.set(
        "climate.daikin_upstairs",
        "heat",
        attributes={"temperature": 19.0},
    )
    fake_hass.states.set("sensor.daikin_outdoor", "5.0")

    assert await package.async_setup_entry(fake_hass, entry) is True
    assert (
        _service_calls_for(
            fake_hass.services.calls,
            "climate",
            "set_temperature",
            entity_id="climate.daikin_upstairs",
        )
        == []
    )

    flow = blockheat_env.config_flow.BlockheatOptionsFlow(entry)
    result = await flow.async_step_init(
        {
            const.CONF_NORDPOOL_PRICE: "sensor.nordpool_price",
            const.CONF_COMFORT_ROOM_1_SENSOR: "sensor.comfort_room_1",
            const.CONF_COMFORT_ROOM_2_SENSOR: "sensor.comfort_room_2",
            const.CONF_STORAGE_ROOM_SENSOR: "sensor.storage_room",
            const.CONF_OUTDOOR_TEMPERATURE_SENSOR: "sensor.outdoor_temp",
            const.CONF_CONTROL_NUMBER_ENTITY: "number.block_heat_control",
            const.CONF_PV_SENSOR: "",
            const.CONF_ENABLE_DAIKIN_CONSUMER: True,
            const.CONF_DAIKIN_CLIMATE_ENTITY: "climate.daikin_upstairs",
        }
    )
    assert result["step_id"] == "tuning_targets"
    result = await flow.async_step_tuning_targets(
        {
            const.CONF_MINUTES_TO_BLOCK: 210,
            const.CONF_PRICE_IGNORE_BELOW: 0.6,
            const.CONF_PV_IGNORE_ABOVE_W: 0.0,
            const.CONF_HEATPUMP_SETPOINT: 20.0,
            const.CONF_SAVING_COLD_OFFSET_C: 1.0,
            const.CONF_ENERGY_SAVING_WARM_SHUTDOWN_OUTDOOR: 8.0,
            const.CONF_COMFORT_TARGET_C: 22.0,
            const.CONF_STORAGE_TARGET_C: 24.5,
            const.CONF_HEATPUMP_OFFSET_C: 2.0,
            const.CONF_COLD_THRESHOLD: 1.0,
            const.CONF_MAX_BOOST: 3.0,
        }
    )
    assert result["step_id"] == "tuning_daikin"
    result = await flow.async_step_tuning_daikin(
        {
            const.CONF_DAIKIN_NORMAL_TEMPERATURE: 22.0,
            const.CONF_DAIKIN_SAVING_TEMPERATURE: 20.0,
            const.CONF_DAIKIN_OUTDOOR_TEMP_THRESHOLD: -10.0,
        }
    )
    assert result["type"] == "create_entry"

    entry.options = dict(result["data"])
    fake_hass.services.calls.clear()

    await package.async_reload_entry(fake_hass, entry)

    fake_hass.services.calls.clear()
    fake_hass.states.set(
        "climate.daikin_upstairs",
        "heat",
        attributes={"temperature": 19.0},
    )
    await fake_hass.services.async_call(
        const.DOMAIN,
        const.SERVICE_RECOMPUTE,
        {"entry_id": entry.entry_id},
        blocking=True,
    )

    daikin_calls = _service_calls_for(
        fake_hass.services.calls,
        "climate",
        "set_temperature",
        entity_id="climate.daikin_upstairs",
    )
    assert daikin_calls
    assert daikin_calls[-1]["payload"]["temperature"] == 22.0


@pytest.mark.asyncio
async def test_setup_entry_migrates_exact_legacy_internal_entity_ids(
    blockheat_env: SimpleNamespace,
    fake_hass: Any,
    build_config: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = blockheat_env.package
    const = blockheat_env.const
    registry = blockheat_env.entity_registry
    monkeypatch.setattr(package, "BlockheatRuntime", _FakeRuntime)
    monkeypatch.setattr(package, "BlockheatCoordinator", _FakeCoordinator)

    await package.async_setup(fake_hass, {})

    entry_id = "entry-migrate"
    entry = blockheat_env.FakeConfigEntry(entry_id, data=build_config())
    registry.add(
        entity_id="binary_sensor.energy_saving_active",
        unique_id=f"{entry_id}_{const.STATE_POLICY_ON}",
        config_entry_id=entry_id,
    )
    registry.add(
        entity_id="sensor.target_saving",
        unique_id=f"{entry_id}_{const.STATE_TARGET_SAVING}",
        config_entry_id=entry_id,
    )
    registry.add(
        entity_id="sensor.target_comfort",
        unique_id=f"{entry_id}_{const.STATE_TARGET_COMFORT}",
        config_entry_id=entry_id,
    )
    registry.add(
        entity_id="sensor.target_final",
        unique_id=f"{entry_id}_{const.STATE_TARGET_FINAL}",
        config_entry_id=entry_id,
    )

    assert await package.async_setup_entry(fake_hass, entry) is True

    assert registry.async_get("binary_sensor.energy_saving_active") is None
    assert registry.async_get("sensor.target_saving") is None
    assert registry.async_get("sensor.target_comfort") is None
    assert registry.async_get("sensor.target_final") is None
    assert registry.async_get(const.ENTITY_ID_POLICY_ACTIVE) is not None
    assert registry.async_get(const.ENTITY_ID_TARGET_SAVING) is not None
    assert registry.async_get(const.ENTITY_ID_TARGET_COMFORT) is not None
    final_entry = registry.async_get(const.ENTITY_ID_TARGET_FINAL)
    assert final_entry is not None
    assert final_entry.unique_id == f"{entry_id}_{const.STATE_TARGET_FINAL}"
    assert len(registry.update_calls) == 4


@pytest.mark.asyncio
async def test_setup_entry_skips_migration_when_canonical_id_is_occupied(
    blockheat_env: SimpleNamespace,
    fake_hass: Any,
    build_config: Any,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    package = blockheat_env.package
    const = blockheat_env.const
    registry = blockheat_env.entity_registry
    monkeypatch.setattr(package, "BlockheatRuntime", _FakeRuntime)
    monkeypatch.setattr(package, "BlockheatCoordinator", _FakeCoordinator)

    await package.async_setup(fake_hass, {})

    entry_id = "entry-occupied"
    entry = blockheat_env.FakeConfigEntry(entry_id, data=build_config())
    registry.add(
        entity_id="sensor.target_final",
        unique_id=f"{entry_id}_{const.STATE_TARGET_FINAL}",
        config_entry_id=entry_id,
    )
    registry.add(
        entity_id=const.ENTITY_ID_TARGET_FINAL,
        unique_id="other-entry_target_final",
        config_entry_id="other-entry",
    )

    caplog.set_level(logging.WARNING)
    assert await package.async_setup_entry(fake_hass, entry) is True

    assert registry.async_get("sensor.target_final") is not None
    assert registry.async_get(const.ENTITY_ID_TARGET_FINAL) is not None
    assert registry.update_calls == []
    assert "manual cleanup" in caplog.text
    assert const.ENTITY_ID_TARGET_FINAL in caplog.text


@pytest.mark.asyncio
async def test_setup_entry_leaves_user_custom_entity_ids_untouched(
    blockheat_env: SimpleNamespace,
    fake_hass: Any,
    build_config: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = blockheat_env.package
    const = blockheat_env.const
    registry = blockheat_env.entity_registry
    monkeypatch.setattr(package, "BlockheatRuntime", _FakeRuntime)
    monkeypatch.setattr(package, "BlockheatCoordinator", _FakeCoordinator)

    await package.async_setup(fake_hass, {})

    entry_id = "entry-custom"
    entry = blockheat_env.FakeConfigEntry(entry_id, data=build_config())
    registry.add(
        entity_id="sensor.my_target_final",
        unique_id=f"{entry_id}_{const.STATE_TARGET_FINAL}",
        config_entry_id=entry_id,
    )

    assert await package.async_setup_entry(fake_hass, entry) is True

    custom_entry = registry.async_get("sensor.my_target_final")
    assert custom_entry is not None
    assert custom_entry.unique_id == f"{entry_id}_{const.STATE_TARGET_FINAL}"
    assert registry.update_calls == []
