from __future__ import annotations

import asyncio
import importlib
import sys
import types
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HOMEASSISTANT_DIR = REPO_ROOT / "homeassistant"
CUSTOM_COMPONENTS_DIR = REPO_ROOT / "custom_components"


@dataclass
class FakeState:
    state: str
    attributes: dict[str, Any] = field(default_factory=dict)
    last_changed: datetime = field(default_factory=lambda: datetime.now(UTC))


class FakeStates:
    def __init__(self) -> None:
        self._states: dict[str, FakeState] = {}

    def get(self, entity_id: str | None) -> FakeState | None:
        if not entity_id:
            return None
        return self._states.get(entity_id)

    def set(
        self,
        entity_id: str,
        state: str,
        *,
        attributes: dict[str, Any] | None = None,
        last_changed: datetime | None = None,
    ) -> FakeState:
        item = FakeState(
            state=str(state),
            attributes={} if attributes is None else dict(attributes),
            last_changed=last_changed or datetime.now(UTC),
        )
        self._states[entity_id] = item
        return item


@dataclass
class FakeServiceCall:
    data: dict[str, Any]


class FakeServices:
    def __init__(self, hass: FakeHass, service_not_found_cls: type[Exception]) -> None:
        self._hass = hass
        self._service_not_found_cls = service_not_found_cls
        self._handlers: dict[tuple[str, str], Any] = {}
        self.calls: list[dict[str, Any]] = []
        self.register_calls: list[tuple[str, str]] = []
        self.remove_calls: list[tuple[str, str]] = []
        self.available: set[tuple[str, str]] = set()
        self.raise_not_found: set[tuple[str, str]] = set()

    def has_service(self, domain: str, service: str) -> bool:
        return (domain, service) in self.available

    def async_register(
        self,
        domain: str,
        service: str,
        handler: Any,
        *,
        schema: Any = None,
    ) -> None:
        self._handlers[(domain, service)] = handler
        self.available.add((domain, service))
        self.register_calls.append((domain, service))

    def async_remove(self, domain: str, service: str) -> None:
        self._handlers.pop((domain, service), None)
        self.available.discard((domain, service))
        self.remove_calls.append((domain, service))

    async def async_call(
        self,
        domain: str,
        service: str,
        payload: dict[str, Any],
        *,
        blocking: bool = True,
    ) -> None:
        self.calls.append(
            {
                "domain": domain,
                "service": service,
                "payload": dict(payload),
                "blocking": blocking,
            }
        )

        if (domain, service) in self.raise_not_found:
            raise self._service_not_found_cls()

        handler = self._handlers.get((domain, service))
        if handler is not None:
            result = handler(FakeServiceCall(data=dict(payload)))
            if asyncio.iscoroutine(result):
                await result

        self._apply_side_effects(domain, service, payload)

    def _apply_side_effects(
        self, domain: str, service: str, payload: dict[str, Any]
    ) -> None:
        entity_id = payload.get("entity_id")
        if not entity_id:
            return

        existing = self._hass.states.get(entity_id)
        attributes = {} if existing is None else dict(existing.attributes)
        last_changed = datetime.now(UTC)

        if domain == "input_boolean" and service in {"turn_on", "turn_off"}:
            new_state = "on" if service == "turn_on" else "off"
            self._hass.states.set(
                entity_id, new_state, attributes=attributes, last_changed=last_changed
            )
            return

        if service == "set_value" and domain in {"input_number", "number"}:
            value = payload.get("value")
            self._hass.states.set(
                entity_id,
                str(value),
                attributes=attributes,
                last_changed=last_changed,
            )
            return

        if domain == "input_datetime" and service == "set_datetime":
            if "timestamp" in payload:
                value = datetime.fromtimestamp(
                    int(payload["timestamp"]), tz=UTC
                ).isoformat()
            elif "datetime" in payload:
                value = str(payload["datetime"])
            else:
                value = ""
            self._hass.states.set(
                entity_id, value, attributes=attributes, last_changed=last_changed
            )
            return

        if domain == "climate" and service == "set_temperature":
            attributes["temperature"] = payload.get("temperature")
            self._hass.states.set(
                entity_id,
                existing.state if existing else "heat",
                attributes=attributes,
                last_changed=last_changed,
            )
            return

        if domain == "climate" and service == "set_hvac_mode":
            attributes["hvac_mode"] = payload.get("hvac_mode")
            self._hass.states.set(
                entity_id,
                existing.state if existing else "heat",
                attributes=attributes,
                last_changed=last_changed,
            )
            return

        if domain == "climate" and service == "set_preset_mode":
            attributes["preset_mode"] = payload.get("preset_mode")
            self._hass.states.set(
                entity_id,
                existing.state if existing else "heat",
                attributes=attributes,
                last_changed=last_changed,
            )


class FakeBus:
    def __init__(self) -> None:
        self.fired: list[dict[str, Any]] = []
        self.once_listeners: list[dict[str, Any]] = []

    def async_fire(
        self, event_type: str, event_data: dict[str, Any] | None = None
    ) -> None:
        self.fired.append({"event_type": event_type, "event_data": event_data or {}})

    def async_listen_once(self, event_type: str, callback: Any) -> Any:
        entry = {"event_type": event_type, "callback": callback, "active": True}
        self.once_listeners.append(entry)

        def _unsub() -> None:
            entry["active"] = False

        return _unsub


class FakeHass:
    def __init__(self, service_not_found_cls: type[Exception]) -> None:
        self.data: dict[str, Any] = {}
        self.states = FakeStates()
        self.services = FakeServices(self, service_not_found_cls)
        self.bus = FakeBus()
        self.config_entries = FakeConfigEntries()
        self.state_trackers: list[dict[str, Any]] = []
        self.interval_trackers: list[dict[str, Any]] = []
        self.later_calls: list[dict[str, Any]] = []
        self.created_tasks: list[asyncio.Task[Any]] = []

    def async_create_task(self, coro: Any) -> asyncio.Task[Any]:
        task = asyncio.create_task(coro)
        self.created_tasks.append(task)
        return task


class FakeConfigEntry:
    def __init__(
        self,
        entry_id: str,
        *,
        data: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
    ) -> None:
        self.entry_id = entry_id
        self.data = {} if data is None else dict(data)
        self.options = {} if options is None else dict(options)
        self._listener_unsubscribed = False

    def add_update_listener(self, listener: Any) -> Any:
        self._listener = listener

        def _unsub() -> None:
            self._listener_unsubscribed = True

        return _unsub


class FakeConfigEntries:
    def __init__(self) -> None:
        self.forward_calls: list[tuple[str, tuple[str, ...]]] = []
        self.unload_calls: list[tuple[str, tuple[str, ...]]] = []

    async def async_forward_entry_setups(
        self, entry: FakeConfigEntry, platforms: list[str]
    ) -> None:
        self.forward_calls.append((entry.entry_id, tuple(platforms)))

    async def async_unload_platforms(
        self, entry: FakeConfigEntry, platforms: list[str]
    ) -> bool:
        self.unload_calls.append((entry.entry_id, tuple(platforms)))
        return True


class FakeConfigFlow:
    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__()

    def _async_current_entries(self) -> list[Any]:
        return getattr(self, "_current_entries", [])

    async def async_set_unique_id(self, unique_id: str) -> None:
        self._unique_id = unique_id

    def _abort_if_unique_id_configured(self) -> None:
        if getattr(self, "_unique_id_already_configured", False):
            raise RuntimeError("unique_id_already_configured")

    def async_abort(self, *, reason: str) -> dict[str, Any]:
        return {"type": "abort", "reason": reason}

    def async_show_form(
        self,
        *,
        step_id: str,
        data_schema: Any,
        errors: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return {
            "type": "form",
            "step_id": step_id,
            "data_schema": data_schema,
            "errors": errors or {},
        }

    def async_create_entry(self, *, title: str, data: dict[str, Any]) -> dict[str, Any]:
        return {"type": "create_entry", "title": title, "data": data}


class FakeOptionsFlow:
    def async_show_form(
        self,
        *,
        step_id: str,
        data_schema: Any,
        errors: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return {
            "type": "form",
            "step_id": step_id,
            "data_schema": data_schema,
            "errors": errors or {},
        }

    def async_create_entry(self, *, title: str, data: dict[str, Any]) -> dict[str, Any]:
        return {"type": "create_entry", "title": title, "data": data}


class FakeDataUpdateCoordinator:
    @classmethod
    def __class_getitem__(cls, item: Any) -> type[FakeDataUpdateCoordinator]:
        return cls

    def __init__(self, hass: FakeHass, **kwargs: Any) -> None:
        self.hass = hass
        self.data: dict[str, Any] | None = None
        self.kwargs = kwargs

    def async_set_updated_data(self, data: dict[str, Any]) -> None:
        self.data = data


class FakeCoordinatorEntity:
    @classmethod
    def __class_getitem__(cls, item: Any) -> type[FakeCoordinatorEntity]:
        return cls

    def __init__(self, coordinator: FakeDataUpdateCoordinator) -> None:
        self.coordinator = coordinator


class FakeEntityCategory:
    DIAGNOSTIC = "diagnostic"


class FakeSensorEntity:
    pass


class FakeBinarySensorEntity:
    pass


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


@pytest.fixture
def blockheat_env(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    service_not_found_cls = type("ServiceNotFound", (Exception,), {})

    homeassistant_module = types.ModuleType("homeassistant")
    homeassistant_module.__path__ = [str(HOMEASSISTANT_DIR)]
    custom_components_module = types.ModuleType("homeassistant.custom_components")
    custom_components_module.__path__ = [str(CUSTOM_COMPONENTS_DIR)]

    const_module = types.ModuleType("homeassistant.const")
    const_module.EVENT_HOMEASSISTANT_START = "homeassistant_start"

    core_module = types.ModuleType("homeassistant.core")
    core_module.HomeAssistant = FakeHass
    core_module.Event = type("Event", (), {})
    core_module.State = FakeState
    core_module.ServiceCall = FakeServiceCall
    core_module.callback = lambda fn: fn

    exceptions_module = types.ModuleType("homeassistant.exceptions")
    exceptions_module.ServiceNotFound = service_not_found_cls

    helpers_module = types.ModuleType("homeassistant.helpers")
    helpers_module.__path__ = []
    event_module = types.ModuleType("homeassistant.helpers.event")
    selector_module = types.ModuleType("homeassistant.helpers.selector")
    update_coordinator_module = types.ModuleType(
        "homeassistant.helpers.update_coordinator"
    )
    update_coordinator_module.DataUpdateCoordinator = FakeDataUpdateCoordinator
    update_coordinator_module.CoordinatorEntity = FakeCoordinatorEntity
    entity_module = types.ModuleType("homeassistant.helpers.entity")
    entity_module.EntityCategory = FakeEntityCategory
    components_module = types.ModuleType("homeassistant.components")
    components_module.__path__ = []
    sensor_module = types.ModuleType("homeassistant.components.sensor")
    sensor_module.SensorEntity = FakeSensorEntity
    binary_sensor_module = types.ModuleType("homeassistant.components.binary_sensor")
    binary_sensor_module.BinarySensorEntity = FakeBinarySensorEntity

    class FakeEntitySelectorConfig:
        def __init__(self, *, domain: str | list[str] | None = None) -> None:
            self.domain = domain

    class FakeEntitySelector:
        def __init__(self, config: FakeEntitySelectorConfig) -> None:
            self.config = config

        def __call__(self, value: Any) -> Any:
            return value

    selector_module.EntitySelectorConfig = FakeEntitySelectorConfig
    selector_module.EntitySelector = FakeEntitySelector

    util_module = types.ModuleType("homeassistant.util")
    util_module.__path__ = []
    dt_module = types.ModuleType("homeassistant.util.dt")
    dt_module.UTC = UTC
    dt_module.utcnow = lambda: datetime.now(UTC)
    dt_module.parse_datetime = _parse_datetime

    config_entries_module = types.ModuleType("homeassistant.config_entries")
    config_entries_module.ConfigEntry = FakeConfigEntry
    config_entries_module.ConfigFlow = FakeConfigFlow
    config_entries_module.OptionsFlow = FakeOptionsFlow

    def _unsub(entry: dict[str, Any]) -> Any:
        def _inner() -> None:
            entry["active"] = False

        return _inner

    def async_track_state_change_event(
        hass: FakeHass, entity_ids: list[str], callback: Any
    ) -> Any:
        entry = {"entity_ids": list(entity_ids), "callback": callback, "active": True}
        hass.state_trackers.append(entry)
        return _unsub(entry)

    def async_track_time_interval(
        hass: FakeHass, callback: Any, interval: timedelta
    ) -> Any:
        entry = {"interval": interval, "callback": callback, "active": True}
        hass.interval_trackers.append(entry)
        return _unsub(entry)

    def async_call_later(hass: FakeHass, seconds: int, callback: Any) -> Any:
        entry = {"seconds": seconds, "callback": callback, "active": True}
        hass.later_calls.append(entry)
        return _unsub(entry)

    event_module.async_track_state_change_event = async_track_state_change_event
    event_module.async_track_time_interval = async_track_time_interval
    event_module.async_call_later = async_call_later

    monkeypatch.setitem(sys.modules, "homeassistant", homeassistant_module)
    monkeypatch.setitem(
        sys.modules,
        "homeassistant.custom_components",
        custom_components_module,
    )
    monkeypatch.setitem(sys.modules, "homeassistant.const", const_module)
    monkeypatch.setitem(sys.modules, "homeassistant.core", core_module)
    monkeypatch.setitem(sys.modules, "homeassistant.exceptions", exceptions_module)
    monkeypatch.setitem(sys.modules, "homeassistant.helpers", helpers_module)
    monkeypatch.setitem(sys.modules, "homeassistant.helpers.event", event_module)
    monkeypatch.setitem(sys.modules, "homeassistant.helpers.selector", selector_module)
    monkeypatch.setitem(sys.modules, "homeassistant.helpers.entity", entity_module)
    monkeypatch.setitem(
        sys.modules,
        "homeassistant.helpers.update_coordinator",
        update_coordinator_module,
    )
    monkeypatch.setitem(sys.modules, "homeassistant.components", components_module)
    monkeypatch.setitem(sys.modules, "homeassistant.components.sensor", sensor_module)
    monkeypatch.setitem(
        sys.modules, "homeassistant.components.binary_sensor", binary_sensor_module
    )
    monkeypatch.setitem(sys.modules, "homeassistant.util", util_module)
    monkeypatch.setitem(sys.modules, "homeassistant.util.dt", dt_module)
    monkeypatch.setitem(
        sys.modules, "homeassistant.config_entries", config_entries_module
    )

    monkeypatch.syspath_prepend(str(REPO_ROOT))

    for name in list(sys.modules):
        if name.startswith("homeassistant.custom_components.blockheat"):
            sys.modules.pop(name, None)

    package_module = importlib.import_module(
        "homeassistant.custom_components.blockheat"
    )
    package_path = Path(package_module.__file__).resolve()
    expected_package_dir = (CUSTOM_COMPONENTS_DIR / "blockheat").resolve()
    if expected_package_dir not in package_path.parents:
        raise AssertionError(
            "blockheat tests must load from installable custom_components tree: "
            f"expected under {expected_package_dir}, got {package_path}"
        )
    const = importlib.import_module("homeassistant.custom_components.blockheat.const")
    coordinator = importlib.import_module(
        "homeassistant.custom_components.blockheat.coordinator"
    )
    runtime = importlib.import_module(
        "homeassistant.custom_components.blockheat.runtime"
    )
    config_flow = importlib.import_module(
        "homeassistant.custom_components.blockheat.config_flow"
    )
    engine = importlib.import_module("homeassistant.custom_components.blockheat.engine")

    return SimpleNamespace(
        package=package_module,
        const=const,
        coordinator=coordinator,
        runtime=runtime,
        config_flow=config_flow,
        engine=engine,
        FakeHass=FakeHass,
        FakeConfigEntry=FakeConfigEntry,
        service_not_found_cls=service_not_found_cls,
    )


@pytest.fixture
def fake_hass(blockheat_env: SimpleNamespace) -> FakeHass:
    return blockheat_env.FakeHass(blockheat_env.service_not_found_cls)


@pytest.fixture
def build_config(blockheat_env: SimpleNamespace) -> Any:
    const = blockheat_env.const

    required_entities = {
        const.CONF_TARGET_BOOLEAN: "input_boolean.block_heat_energy_saving",
        const.CONF_NORDPOOL_PRICE: "sensor.nordpool_price",
        const.CONF_COMFORT_ROOM_1_SENSOR: "sensor.comfort_room_1",
        const.CONF_COMFORT_ROOM_2_SENSOR: "sensor.comfort_room_2",
        const.CONF_STORAGE_ROOM_SENSOR: "sensor.storage_room",
        const.CONF_OUTDOOR_TEMPERATURE_SENSOR: "sensor.outdoor_temp",
        const.CONF_TARGET_SAVING_HELPER: "input_number.block_heat_target_saving",
        const.CONF_TARGET_COMFORT_HELPER: "input_number.block_heat_target_comfort",
        const.CONF_TARGET_FINAL_HELPER: "input_number.block_heat_target_final",
        const.CONF_FALLBACK_ACTIVE_BOOLEAN: "input_boolean.block_heat_fallback_active",
        const.CONF_ELECTRIC_FALLBACK_LAST_TRIGGER: "input_datetime.block_heat_fallback_last_trigger",
        const.CONF_CONTROL_NUMBER_ENTITY: "number.block_heat_control",
    }

    def _build(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        config = {**const.DEFAULTS, **required_entities}
        if overrides:
            config.update(overrides)
        return config

    return _build


@pytest.fixture
def seed_runtime_states(blockheat_env: SimpleNamespace) -> Any:
    const = blockheat_env.const

    def _seed(
        hass: FakeHass,
        config: dict[str, Any],
        *,
        price: float = 1.0,
        prices_today: list[float] | None = None,
        policy_state: str = "off",
        room1_temp: float = 21.0,
        room2_temp: float = 21.0,
        storage_temp: float = 24.0,
        outdoor_temp: float = 0.0,
        saving_target: float = 19.0,
        comfort_target: float = 20.0,
        final_target: float = 20.0,
        control_value: float = 20.0,
        fallback_active: str = "off",
        fallback_last_trigger: str = "2026-02-18T00:00:00+00:00",
    ) -> None:
        changed = datetime.now(UTC) - timedelta(hours=2)
        hass.states.set(
            config[const.CONF_TARGET_BOOLEAN], policy_state, last_changed=changed
        )
        hass.states.set(
            config[const.CONF_NORDPOOL_PRICE],
            str(price),
            attributes={"today": prices_today or [1.0, 2.0, 3.0, 4.0]},
            last_changed=changed,
        )
        hass.states.set(
            config[const.CONF_COMFORT_ROOM_1_SENSOR],
            str(room1_temp),
            last_changed=changed,
        )
        hass.states.set(
            config[const.CONF_COMFORT_ROOM_2_SENSOR],
            str(room2_temp),
            last_changed=changed,
        )
        hass.states.set(
            config[const.CONF_STORAGE_ROOM_SENSOR],
            str(storage_temp),
            last_changed=changed,
        )
        hass.states.set(
            config[const.CONF_OUTDOOR_TEMPERATURE_SENSOR],
            str(outdoor_temp),
            last_changed=changed,
        )
        hass.states.set(
            config[const.CONF_TARGET_SAVING_HELPER],
            str(saving_target),
            last_changed=changed,
        )
        hass.states.set(
            config[const.CONF_TARGET_COMFORT_HELPER],
            str(comfort_target),
            last_changed=changed,
        )
        hass.states.set(
            config[const.CONF_TARGET_FINAL_HELPER],
            str(final_target),
            last_changed=changed,
        )
        hass.states.set(
            config[const.CONF_CONTROL_NUMBER_ENTITY],
            str(control_value),
            last_changed=changed,
        )
        hass.states.set(
            config[const.CONF_FALLBACK_ACTIVE_BOOLEAN],
            fallback_active,
            last_changed=changed,
        )
        hass.states.set(
            config[const.CONF_ELECTRIC_FALLBACK_LAST_TRIGGER],
            fallback_last_trigger,
            last_changed=changed,
        )

        pv_sensor = config.get(const.CONF_PV_SENSOR, "")
        if pv_sensor:
            hass.states.set(pv_sensor, "0", last_changed=changed)

        floor_sensor = config.get(const.CONF_FLOOR_TEMP_SENSOR, "")
        if floor_sensor:
            hass.states.set(floor_sensor, "21", last_changed=changed)

    return _seed


@pytest.fixture
def service_calls(fake_hass: FakeHass) -> list[dict[str, Any]]:
    return fake_hass.services.calls
