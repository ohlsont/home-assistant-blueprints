"""Blockheat custom integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall

from .const import (
    DOMAIN,
    PLATFORMS,
    SERVICE_DUMP_DIAGNOSTICS,
    SERVICE_RECOMPUTE,
)
from .coordinator import BlockheatCoordinator
from .runtime import BlockheatRuntime

ENTRY_RUNTIME = "runtime"
ENTRY_COORDINATOR = "coordinator"
ENTRY_UNSUB_RELOAD = "unsub_reload"

SERVICE_SCHEMA = vol.Schema({vol.Optional("entry_id"): str})


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up Blockheat domain."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Blockheat from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = BlockheatCoordinator(hass)
    config = {**entry.data, **entry.options}
    runtime = BlockheatRuntime(hass, config, coordinator)
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
    entry_data = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if not entry_data:
        return True

    runtime: BlockheatRuntime = entry_data[ENTRY_RUNTIME]
    unsub_reload = entry_data[ENTRY_UNSUB_RELOAD]
    await runtime.async_unload()
    unsub_reload()
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    if not hass.data.get(DOMAIN):
        await _async_unregister_services(hass)

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload an entry when options change."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


async def _async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_RECOMPUTE):
        return

    async def _handle_recompute(call: ServiceCall) -> None:
        entry_id = call.data.get("entry_id")
        targets = _resolve_runtimes(hass, entry_id)
        for runtime in targets:
            await runtime.async_recompute("service_recompute")

    async def _handle_dump_diagnostics(call: ServiceCall) -> None:
        entry_id = call.data.get("entry_id")
        targets = _resolve_runtimes(hass, entry_id)
        for runtime in targets:
            await runtime.async_recompute("service_dump_diagnostics")

    hass.services.async_register(
        DOMAIN,
        SERVICE_RECOMPUTE,
        _handle_recompute,
        schema=SERVICE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DUMP_DIAGNOSTICS,
        _handle_dump_diagnostics,
        schema=SERVICE_SCHEMA,
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
