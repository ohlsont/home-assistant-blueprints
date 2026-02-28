"""Blockheat binary sensor entities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ENTRY_COORDINATOR
from .const import (
    DOMAIN,
    ENTITY_ID_FALLBACK_ACTIVE,
    ENTITY_ID_POLICY_ACTIVE,
    STATE_FALLBACK_ACTIVE,
    STATE_POLICY_ON,
)
from .coordinator import BlockheatCoordinator


@dataclass(frozen=True)
class DiagnosticBinarySensorSpec:
    """Mapping from snapshot path to a diagnostic binary sensor."""

    entity_id: str
    name: str
    path: tuple[str, ...]


DIAGNOSTIC_BINARY_SENSOR_SPECS: tuple[DiagnosticBinarySensorSpec, ...] = (
    DiagnosticBinarySensorSpec(
        "binary_sensor.blockheat_policy_blocked_now",
        "Policy blocked now",
        ("policy", "blocked_now"),
    ),
    DiagnosticBinarySensorSpec(
        "binary_sensor.blockheat_policy_ignore_by_price",
        "Policy ignore by price",
        ("policy", "ignore_by_price"),
    ),
    DiagnosticBinarySensorSpec(
        "binary_sensor.blockheat_policy_ignore_by_pv",
        "Policy ignore by pv",
        ("policy", "ignore_by_pv"),
    ),
    DiagnosticBinarySensorSpec(
        "binary_sensor.blockheat_policy_below_min_floor",
        "Policy below min floor",
        ("policy", "below_min_floor"),
    ),
    DiagnosticBinarySensorSpec(
        "binary_sensor.blockheat_policy_enough_time_passed",
        "Policy enough time passed",
        ("policy", "enough_time_passed"),
    ),
    DiagnosticBinarySensorSpec(
        "binary_sensor.blockheat_fallback_arm_condition",
        "Fallback arm condition",
        ("fallback", "arm_condition"),
    ),
    DiagnosticBinarySensorSpec(
        "binary_sensor.blockheat_fallback_cooldown_ok",
        "Fallback cooldown ok",
        ("fallback", "cooldown_ok"),
    ),
    DiagnosticBinarySensorSpec(
        "binary_sensor.blockheat_control_write_applied",
        "Control write applied",
        ("final_target_debug", "control_write_applied"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Blockheat binary sensors from a config entry."""
    coordinator: BlockheatCoordinator = hass.data[DOMAIN][entry.entry_id][
        ENTRY_COORDINATOR
    ]

    entities: list[BinarySensorEntity] = [
        BlockheatBinarySensor(
            coordinator=coordinator,
            entry_id=entry.entry_id,
            entity_id=ENTITY_ID_POLICY_ACTIVE,
            name="Energy saving active",
            state_key=STATE_POLICY_ON,
            icon="mdi:flash",
        ),
        BlockheatBinarySensor(
            coordinator=coordinator,
            entry_id=entry.entry_id,
            entity_id=ENTITY_ID_FALLBACK_ACTIVE,
            name="Fallback active",
            state_key=STATE_FALLBACK_ACTIVE,
            icon="mdi:shield-alert",
        ),
    ]
    entities.extend(
        BlockheatDiagnosticBinarySensor(coordinator=coordinator, spec=spec)
        for spec in DIAGNOSTIC_BINARY_SENSOR_SPECS
    )
    async_add_entities(entities)


class BlockheatBinarySensor(
    CoordinatorEntity[BlockheatCoordinator], BinarySensorEntity
):
    """Read-only binary sensor fed by Blockheat runtime state."""

    _attr_should_poll = False

    def __init__(
        self,
        *,
        coordinator: BlockheatCoordinator,
        entry_id: str,
        entity_id: str,
        name: str,
        state_key: str,
        icon: str,
    ) -> None:
        super().__init__(coordinator)
        self._state_key = state_key
        self._attr_name = name
        self._attr_entity_id = entity_id
        self._attr_unique_id = f"{entry_id}_{state_key}"
        self._attr_icon = icon

    @property
    def available(self) -> bool:
        return self.coordinator.data is not None

    @property
    def is_on(self) -> bool:
        state = self._internal_state()
        return bool(state.get(self._state_key, False))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        state = self._internal_state()
        return {
            "source": "blockheat_internal_state",
            "updated_at": (self.coordinator.data or {}).get("at"),
            "reason": (self.coordinator.data or {}).get("reason"),
            "raw": state.get(self._state_key),
        }

    def _internal_state(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        internal = data.get("internal_state", {})
        return internal if isinstance(internal, dict) else {}


def _extract_path_value(data: dict[str, Any] | None, path: tuple[str, ...]) -> Any:
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
    """Read-only diagnostic binary sensor based on snapshot values."""

    _attr_should_poll = False
    _attr_entity_category = "diagnostic"

    def __init__(
        self,
        *,
        coordinator: BlockheatCoordinator,
        spec: DiagnosticBinarySensorSpec,
    ) -> None:
        super().__init__(coordinator)
        self._spec = spec
        self._attr_name = spec.name
        self._attr_unique_id = spec.entity_id.replace(".", "_")

    @property
    def entity_id(self) -> str:
        return self._spec.entity_id

    @property
    def available(self) -> bool:
        if self.coordinator.data is None:
            return False
        return _extract_path_value(self.coordinator.data, self._spec.path) is not None

    @property
    def is_on(self) -> bool | None:
        value = _extract_path_value(self.coordinator.data, self._spec.path)
        if value is None:
            return None
        return bool(value)
