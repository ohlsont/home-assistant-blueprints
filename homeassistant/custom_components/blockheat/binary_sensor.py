"""Diagnostic binary sensors for Blockheat runtime snapshot data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BlockheatCoordinator


@dataclass(frozen=True)
class BinarySensorSpec:
    """Mapping from coordinator snapshot path to a binary sensor entity."""

    entity_id: str
    name: str
    path: tuple[str, ...]


BINARY_SENSOR_SPECS: tuple[BinarySensorSpec, ...] = (
    BinarySensorSpec(
        "binary_sensor.blockheat_policy_blocked_now",
        "Blockheat Policy Blocked Now",
        ("policy", "blocked_now"),
    ),
    BinarySensorSpec(
        "binary_sensor.blockheat_policy_ignore_by_price",
        "Blockheat Policy Ignore By Price",
        ("policy", "ignore_by_price"),
    ),
    BinarySensorSpec(
        "binary_sensor.blockheat_policy_ignore_by_pv",
        "Blockheat Policy Ignore By PV",
        ("policy", "ignore_by_pv"),
    ),
    BinarySensorSpec(
        "binary_sensor.blockheat_policy_below_min_floor",
        "Blockheat Policy Below Min Floor",
        ("policy", "below_min_floor"),
    ),
    BinarySensorSpec(
        "binary_sensor.blockheat_policy_enough_time_passed",
        "Blockheat Policy Enough Time Passed",
        ("policy", "enough_time_passed"),
    ),
    BinarySensorSpec(
        "binary_sensor.blockheat_fallback_arm_condition",
        "Blockheat Fallback Arm Condition",
        ("fallback", "arm_condition"),
    ),
    BinarySensorSpec(
        "binary_sensor.blockheat_fallback_cooldown_ok",
        "Blockheat Fallback Cooldown OK",
        ("fallback", "cooldown_ok"),
    ),
    BinarySensorSpec(
        "binary_sensor.blockheat_control_write_applied",
        "Blockheat Control Write Applied",
        ("final_target_debug", "control_write_applied"),
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


class BlockheatDiagnosticBinarySensor(
    CoordinatorEntity[BlockheatCoordinator], BinarySensorEntity
):
    """Expose selected Blockheat diagnostics as binary sensors."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_should_poll = False

    def __init__(self, coordinator: BlockheatCoordinator, spec: BinarySensorSpec) -> None:
        super().__init__(coordinator)
        self._spec = spec
        self._attr_name = spec.name
        self._attr_unique_id = spec.entity_id.replace(".", "_")

    @property
    def entity_id(self) -> str:
        return self._spec.entity_id

    @property
    def is_on(self) -> bool | None:
        value = _extract_value(self.coordinator.data, self._spec.path)
        if value is None:
            return None
        return bool(value)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Any,
) -> None:
    """Set up Blockheat diagnostic binary sensors for one config entry."""
    coordinator: BlockheatCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(
        [BlockheatDiagnosticBinarySensor(coordinator, spec) for spec in BINARY_SENSOR_SPECS]
    )
