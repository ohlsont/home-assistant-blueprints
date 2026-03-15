"""Blockheat custom integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers import entity_registry as er

from .const import (
    DOMAIN,
    ENTITY_ID_POLICY_ACTIVE,
    ENTITY_ID_TARGET_COMFORT,
    ENTITY_ID_TARGET_FINAL,
    ENTITY_ID_TARGET_SAVING,
    PLATFORMS,
    SERVICE_DUMP_DIAGNOSTICS,
    SERVICE_RECOMPUTE,
)
from .coordinator import BlockheatCoordinator
from .runtime import BlockheatRuntime

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)

ENTRY_RUNTIME = "runtime"
ENTRY_COORDINATOR = "coordinator"
ENTRY_UNSUB_RELOAD = "unsub_reload"

SERVICE_SCHEMA = vol.Schema({vol.Optional("entry_id"): str})

_LEGACY_ENTITY_MIGRATIONS: tuple[tuple[str, str], ...] = (
    ("binary_sensor.energy_saving_active", ENTITY_ID_POLICY_ACTIVE),
    ("sensor.target_saving", ENTITY_ID_TARGET_SAVING),
    ("sensor.target_comfort", ENTITY_ID_TARGET_COMFORT),
    ("sensor.target_final", ENTITY_ID_TARGET_FINAL),
)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up Blockheat domain."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Blockheat from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    await _async_migrate_internal_entity_ids(hass, entry)

    coordinator = BlockheatCoordinator(hass)
    config = {**entry.data, **entry.options}
    runtime = BlockheatRuntime(
        hass,
        entry.entry_id,
        config,
        coordinator,
        entry_data=entry.data,
        entry_options=entry.options,
    )
    await runtime.async_setup()

    unsub_reload = entry.add_update_listener(async_reload_entry)

    hass.data[DOMAIN][entry.entry_id] = {
        ENTRY_RUNTIME: runtime,
        ENTRY_COORDINATOR: coordinator,
        ENTRY_UNSUB_RELOAD: unsub_reload,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await _async_register_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Blockheat entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    entry_data = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if not entry_data:
        return True

    runtime: BlockheatRuntime = entry_data[ENTRY_RUNTIME]
    unsub_reload = entry_data[ENTRY_UNSUB_RELOAD]
    await runtime.async_unload()
    unsub_reload()

    if not hass.data.get(DOMAIN):
        await _async_unregister_services(hass)

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload an entry when options change."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


async def _async_migrate_internal_entity_ids(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Promote pre-v1 public entity IDs to the canonical blockheat_* IDs."""
    registry = er.async_get(hass)
    for legacy_entity_id, canonical_entity_id in _LEGACY_ENTITY_MIGRATIONS:
        legacy_entry = registry.async_get(legacy_entity_id)
        if legacy_entry is None:
            continue
        if getattr(legacy_entry, "config_entry_id", None) != entry.entry_id:
            continue
        if legacy_entity_id == canonical_entity_id:
            continue
        if registry.async_get(canonical_entity_id) is not None:
            _LOGGER.warning(
                "Skipping Blockheat internal entity migration for %s -> %s because "
                "the target ID is already occupied; manual cleanup required.",
                legacy_entity_id,
                canonical_entity_id,
            )
            continue
        registry.async_update_entity(
            legacy_entity_id,
            new_entity_id=canonical_entity_id,
        )


async def _async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_RECOMPUTE):
        return

    async def _handle_recompute(call: ServiceCall) -> dict[str, Any]:
        entry_id = call.data.get("entry_id")
        targets = _resolve_runtimes(hass, entry_id)
        entries: dict[str, dict[str, Any]] = {}
        for runtime in targets:
            entries[runtime.entry_id] = await runtime.async_recompute(
                "service_recompute"
            )
        return {"entries": entries}

    async def _handle_dump_diagnostics(call: ServiceCall) -> dict[str, Any]:
        entry_id = call.data.get("entry_id")
        targets = _resolve_runtimes(hass, entry_id)
        entries: dict[str, dict[str, Any]] = {}
        for runtime in targets:
            entries[runtime.entry_id] = await runtime.async_recompute(
                "service_dump_diagnostics"
            )
        return {"entries": entries}

    hass.services.async_register(
        DOMAIN,
        SERVICE_RECOMPUTE,
        _handle_recompute,
        schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DUMP_DIAGNOSTICS,
        _handle_dump_diagnostics,
        schema=SERVICE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )


async def _async_unregister_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_RECOMPUTE):
        hass.services.async_remove(DOMAIN, SERVICE_RECOMPUTE)
    if hass.services.has_service(DOMAIN, SERVICE_DUMP_DIAGNOSTICS):
        hass.services.async_remove(DOMAIN, SERVICE_DUMP_DIAGNOSTICS)


def _resolve_runtimes(
    hass: HomeAssistant, entry_id: str | None
) -> list[BlockheatRuntime]:
    runtimes: list[BlockheatRuntime] = []
    domain_data = hass.data.get(DOMAIN, {})
    if entry_id:
        entry_data = domain_data.get(entry_id)
        if entry_data:
            runtimes.append(entry_data[ENTRY_RUNTIME])
        return runtimes

    for entry_data in domain_data.values():
        runtimes.append(entry_data[ENTRY_RUNTIME])
    return runtimes
