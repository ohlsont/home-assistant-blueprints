"""Blockheat sensor entities."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import ENTRY_COORDINATOR
from .const import (
    DOMAIN,
    ENTITY_ID_FALLBACK_LAST_TRIGGER,
    ENTITY_ID_TARGET_COMFORT,
    ENTITY_ID_TARGET_FINAL,
    ENTITY_ID_TARGET_SAVING,
    STATE_FALLBACK_LAST_TRIGGER,
    STATE_TARGET_COMFORT,
    STATE_TARGET_FINAL,
    STATE_TARGET_SAVING,
)
from .coordinator import BlockheatCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Blockheat sensors from a config entry."""
    coordinator: BlockheatCoordinator = hass.data[DOMAIN][entry.entry_id][
        ENTRY_COORDINATOR
    ]
    async_add_entities(
        [
            BlockheatTemperatureSensor(
                coordinator=coordinator,
                entry_id=entry.entry_id,
                entity_id=ENTITY_ID_TARGET_SAVING,
                name="Target saving",
                state_key=STATE_TARGET_SAVING,
                icon="mdi:thermometer-minus",
            ),
            BlockheatTemperatureSensor(
                coordinator=coordinator,
                entry_id=entry.entry_id,
                entity_id=ENTITY_ID_TARGET_COMFORT,
                name="Target comfort",
                state_key=STATE_TARGET_COMFORT,
                icon="mdi:thermometer-plus",
            ),
            BlockheatTemperatureSensor(
                coordinator=coordinator,
                entry_id=entry.entry_id,
                entity_id=ENTITY_ID_TARGET_FINAL,
                name="Target final",
                state_key=STATE_TARGET_FINAL,
                icon="mdi:thermometer",
            ),
            BlockheatFallbackLastTriggerSensor(
                coordinator=coordinator,
                entry_id=entry.entry_id,
                entity_id=ENTITY_ID_FALLBACK_LAST_TRIGGER,
                state_key=STATE_FALLBACK_LAST_TRIGGER,
            ),
        ]
    )


class BlockheatBaseSensor(CoordinatorEntity[BlockheatCoordinator], SensorEntity):
    """Base read-only sensor fed by Blockheat runtime state."""

    _attr_should_poll = False

    def __init__(
        self,
        *,
        coordinator: BlockheatCoordinator,
        entry_id: str,
        entity_id: str,
        name: str,
        state_key: str,
    ) -> None:
        super().__init__(coordinator)
        self._state_key = state_key
        self._attr_name = name
        self._attr_entity_id = entity_id
        self._attr_unique_id = f"{entry_id}_{state_key}"

    @property
    def available(self) -> bool:
        return self.coordinator.data is not None

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


class BlockheatTemperatureSensor(BlockheatBaseSensor):
    """Read-only temperature sensor for Blockheat target outputs."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 2

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
        super().__init__(
            coordinator=coordinator,
            entry_id=entry_id,
            entity_id=entity_id,
            name=name,
            state_key=state_key,
        )
        self._attr_icon = icon

    @property
    def native_value(self) -> float | None:
        state = self._internal_state().get(self._state_key)
        if state is None:
            return None
        try:
            return float(state)
        except (TypeError, ValueError):
            return None


class BlockheatFallbackLastTriggerSensor(BlockheatBaseSensor):
    """Read-only timestamp sensor for fallback last trigger."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-outline"

    def __init__(
        self,
        *,
        coordinator: BlockheatCoordinator,
        entry_id: str,
        entity_id: str,
        state_key: str,
    ) -> None:
        super().__init__(
            coordinator=coordinator,
            entry_id=entry_id,
            entity_id=entity_id,
            name="Fallback last trigger",
            state_key=state_key,
        )

    @property
    def native_value(self) -> datetime | None:
        value = self._internal_state().get(self._state_key)
        if value is None:
            return None
        return dt_util.parse_datetime(str(value))
