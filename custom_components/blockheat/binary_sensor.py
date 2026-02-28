"""Blockheat binary sensor entities."""

from __future__ import annotations

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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Blockheat binary sensors from a config entry."""
    coordinator: BlockheatCoordinator = hass.data[DOMAIN][entry.entry_id][ENTRY_COORDINATOR]
    async_add_entities(
        [
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
    )


class BlockheatBinarySensor(CoordinatorEntity[BlockheatCoordinator], BinarySensorEntity):
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
