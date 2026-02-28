"""Diagnostic sensors for Blockheat runtime snapshot data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BlockheatCoordinator


@dataclass(frozen=True)
class SensorSpec:
    """Mapping from coordinator snapshot path to a sensor entity."""

    entity_id: str
    name: str
    path: tuple[str, ...]


SENSOR_SPECS: tuple[SensorSpec, ...] = (
    SensorSpec("sensor.blockheat_policy_price", "Blockheat Policy Price", ("policy", "price")),
    SensorSpec("sensor.blockheat_policy_cutoff", "Blockheat Policy Cutoff", ("policy", "cutoff")),
    SensorSpec(
        "sensor.blockheat_policy_transition",
        "Blockheat Policy Transition",
        ("policy", "transition"),
    ),
    SensorSpec(
        "sensor.blockheat_final_source",
        "Blockheat Final Target Source",
        ("final_target_debug", "source"),
    ),
    SensorSpec(
        "sensor.blockheat_fallback_comfort_min",
        "Blockheat Fallback Comfort Min",
        ("fallback", "comfort_min"),
    ),
    SensorSpec(
        "sensor.blockheat_fallback_trigger_threshold",
        "Blockheat Fallback Trigger Threshold",
        ("fallback", "trigger_threshold"),
    ),
    SensorSpec(
        "sensor.blockheat_fallback_release_threshold",
        "Blockheat Fallback Release Threshold",
        ("fallback", "release_threshold"),
    ),
    SensorSpec(
        "sensor.blockheat_control_write_delta",
        "Blockheat Control Write Delta",
        ("final_target_debug", "control_write_delta"),
    ),
    SensorSpec(
        "sensor.blockheat_daikin_action",
        "Blockheat Daikin Action",
        ("daikin", "debug", "action"),
    ),
    SensorSpec(
        "sensor.blockheat_floor_action",
        "Blockheat Floor Action",
        ("floor", "debug", "action"),
    ),
)


def _extract_value(data: dict[str, Any] | None, path: tuple[str, ...]) -> Any:
    value: Any = data
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
        if value is None:
            return None
    return value


class BlockheatDiagnosticSensor(CoordinatorEntity[BlockheatCoordinator], SensorEntity):
    """Expose selected Blockheat diagnostics as native sensors."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_should_poll = False

    def __init__(self, coordinator: BlockheatCoordinator, spec: SensorSpec) -> None:
        super().__init__(coordinator)
        self._spec = spec
        self._attr_name = spec.name
        self._attr_unique_id = spec.entity_id.replace(".", "_")

    @property
    def entity_id(self) -> str:
        return self._spec.entity_id

    @property
    def native_value(self) -> Any:
        return _extract_value(self.coordinator.data, self._spec.path)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Any,
) -> None:
    """Set up Blockheat diagnostic sensors for one config entry."""
    coordinator: BlockheatCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(
        [BlockheatDiagnosticSensor(coordinator, spec) for spec in SENSOR_SPECS]
    )
