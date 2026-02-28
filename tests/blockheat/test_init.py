"""Integration setup tests for blockheat.__init__."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest


class _FakeRuntime:
    def __init__(self, hass: Any, config: dict[str, Any], coordinator: Any) -> None:
        self.hass = hass
        self.config = config
        self.coordinator = coordinator
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
