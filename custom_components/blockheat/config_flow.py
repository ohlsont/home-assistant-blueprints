"""Config flow for Blockheat."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_COLD_THRESHOLD,
    CONF_COMFORT_ROOM_1_SENSOR,
    CONF_COMFORT_ROOM_2_SENSOR,
    CONF_COMFORT_TARGET_C,
    CONF_CONTROL_NUMBER_ENTITY,
    CONF_DAIKIN_CLIMATE_ENTITY,
    CONF_DAIKIN_MILD_THRESHOLD,
    CONF_DAIKIN_NORMAL_TEMPERATURE,
    CONF_DAIKIN_PREHEAT_OFFSET,
    CONF_ENABLE_DAIKIN_CONSUMER,
    CONF_ENABLE_FORECAST_OPTIMIZATION,
    CONF_ENERGY_SAVING_WARM_SHUTDOWN_OUTDOOR,
    CONF_HEATPUMP_SETPOINT,
    CONF_MAX_BOOST,
    CONF_MINUTES_TO_BLOCK,
    CONF_NORDPOOL_PRICE,
    CONF_OUTDOOR_TEMPERATURE_SENSOR,
    CONF_PRICE_IGNORE_BELOW,
    CONF_PV_IGNORE_ABOVE_W,
    CONF_PV_SENSOR,
    CONF_SAVING_COLD_OFFSET_C,
    CONF_STORAGE_ROOM_SENSOR,
    CONF_STORAGE_TARGET_C,
    CONF_WEATHER_ENTITY,
    DEFAULTS,
    DOMAIN,
    normalize_entry_data,
)

if TYPE_CHECKING:
    from collections.abc import Callable

_NON_NEGATIVE_KEYS: tuple[str, ...] = (
    "minutes_to_block",
    "price_ignore_below",
    "pv_ignore_above_w",
    "daikin_preheat_offset",
)


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def validate_tuning_values(values: dict[str, Any]) -> str | None:
    """Return an error key when tuning values are invalid."""
    for key in _NON_NEGATIVE_KEYS:
        value = _as_float(values.get(key))
        if value is not None and value < 0:
            return "invalid_non_negative"

    return None


TUNING_TARGETS_STEP = "tuning_targets"
TUNING_DAIKIN_STEP = "tuning_daikin"

_REQUIRED_USER_SCHEMA_KEYS: tuple[str, ...] = (
    CONF_NORDPOOL_PRICE,
    CONF_COMFORT_ROOM_1_SENSOR,
    CONF_COMFORT_ROOM_2_SENSOR,
    CONF_STORAGE_ROOM_SENSOR,
    CONF_OUTDOOR_TEMPERATURE_SENSOR,
    CONF_CONTROL_NUMBER_ENTITY,
)


def _cfg_value(data: dict[str, Any], key: str) -> Any:
    if key in data:
        return data[key]
    return DEFAULTS.get(key, "")


def _required_marker(current: dict[str, Any], key: str) -> vol.Required:
    default = _cfg_value(current, key)
    if default in ("", None):
        return vol.Required(key)
    return vol.Required(key, default=default)


def _optional_marker(current: dict[str, Any], key: str) -> vol.Optional:
    default = _cfg_value(current, key)
    if default in ("", None):
        return vol.Optional(key)
    return vol.Optional(key, default=default)


def _entity_selector(domains: str | list[str]) -> selector.EntitySelector:
    return selector.EntitySelector(selector.EntitySelectorConfig(domain=domains))


def _bounded_float(min_value: float, max_value: float) -> Any:
    return vol.All(vol.Coerce(float), vol.Range(min=min_value, max=max_value))


def _bounded_int(min_value: int, max_value: int) -> Any:
    return vol.All(vol.Coerce(int), vol.Range(min=min_value, max=max_value))


def _is_enabled(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _ordered_tuning_steps(current: dict[str, Any]) -> list[str]:
    steps = [TUNING_TARGETS_STEP]
    if _is_enabled(current.get(CONF_ENABLE_DAIKIN_CONSUMER, False)):
        steps.append(TUNING_DAIKIN_STEP)
    return steps


def _next_tuning_step(current: dict[str, Any], step_id: str) -> str | None:
    steps = _ordered_tuning_steps(current)
    idx = steps.index(step_id)
    if idx + 1 >= len(steps):
        return None
    return steps[idx + 1]


def _user_schema(current: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            # Core inputs
            _required_marker(current, CONF_NORDPOOL_PRICE): _entity_selector("sensor"),
            _required_marker(current, CONF_COMFORT_ROOM_1_SENSOR): _entity_selector(
                "sensor"
            ),
            _required_marker(current, CONF_COMFORT_ROOM_2_SENSOR): _entity_selector(
                "sensor"
            ),
            _required_marker(current, CONF_STORAGE_ROOM_SENSOR): _entity_selector(
                "sensor"
            ),
            _required_marker(
                current, CONF_OUTDOOR_TEMPERATURE_SENSOR
            ): _entity_selector("sensor"),
            # Control output
            _required_marker(current, CONF_CONTROL_NUMBER_ENTITY): _entity_selector(
                "number"
            ),
            # Optional signals
            _optional_marker(current, CONF_PV_SENSOR): _entity_selector("sensor"),
            # Optional consumers
            _optional_marker(current, CONF_ENABLE_DAIKIN_CONSUMER): bool,
            _optional_marker(current, CONF_DAIKIN_CLIMATE_ENTITY): _entity_selector(
                "climate"
            ),
        }
    )


def _tuning_targets_schema(current: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_MINUTES_TO_BLOCK,
                default=_cfg_value(current, CONF_MINUTES_TO_BLOCK),
            ): _bounded_int(0, 1440),
            vol.Required(
                CONF_PRICE_IGNORE_BELOW,
                default=_cfg_value(current, CONF_PRICE_IGNORE_BELOW),
            ): _bounded_float(0, 100),
            vol.Required(
                CONF_PV_IGNORE_ABOVE_W,
                default=_cfg_value(current, CONF_PV_IGNORE_ABOVE_W),
            ): _bounded_float(0, 1_000_000),
            vol.Required(
                CONF_HEATPUMP_SETPOINT,
                default=_cfg_value(current, CONF_HEATPUMP_SETPOINT),
            ): _bounded_float(0, 50),
            vol.Required(
                CONF_SAVING_COLD_OFFSET_C,
                default=_cfg_value(current, CONF_SAVING_COLD_OFFSET_C),
            ): _bounded_float(0, 20),
            vol.Required(
                CONF_ENERGY_SAVING_WARM_SHUTDOWN_OUTDOOR,
                default=_cfg_value(current, CONF_ENERGY_SAVING_WARM_SHUTDOWN_OUTDOOR),
            ): _bounded_float(-50, 50),
            vol.Required(
                CONF_COMFORT_TARGET_C,
                default=_cfg_value(current, CONF_COMFORT_TARGET_C),
            ): _bounded_float(0, 50),
            vol.Required(
                CONF_STORAGE_TARGET_C,
                default=_cfg_value(current, CONF_STORAGE_TARGET_C),
            ): _bounded_float(0, 60),
            vol.Required(
                CONF_COLD_THRESHOLD, default=_cfg_value(current, CONF_COLD_THRESHOLD)
            ): _bounded_float(-50, 30),
            vol.Required(
                CONF_MAX_BOOST, default=_cfg_value(current, CONF_MAX_BOOST)
            ): _bounded_float(0, 20),
            vol.Optional(
                CONF_ENABLE_FORECAST_OPTIMIZATION,
                default=_cfg_value(current, CONF_ENABLE_FORECAST_OPTIMIZATION),
            ): bool,
            vol.Optional(
                CONF_WEATHER_ENTITY,
                default=_cfg_value(current, CONF_WEATHER_ENTITY),
            ): _entity_selector("weather"),
        }
    )


def _tuning_daikin_schema(current: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_DAIKIN_NORMAL_TEMPERATURE,
                default=_cfg_value(current, CONF_DAIKIN_NORMAL_TEMPERATURE),
            ): _bounded_float(0, 50),
            vol.Required(
                CONF_DAIKIN_PREHEAT_OFFSET,
                default=_cfg_value(current, CONF_DAIKIN_PREHEAT_OFFSET),
            ): _bounded_float(0, 10),
            vol.Required(
                CONF_DAIKIN_MILD_THRESHOLD,
                default=_cfg_value(current, CONF_DAIKIN_MILD_THRESHOLD),
            ): _bounded_float(-50, 50),
        }
    )


_STEP_SCHEMAS: dict[str, Callable[[dict[str, Any]], vol.Schema]] = {
    TUNING_TARGETS_STEP: _tuning_targets_schema,
    TUNING_DAIKIN_STEP: _tuning_daikin_schema,
}


def _tuning_schema_for_step(step_id: str, current: dict[str, Any]) -> vol.Schema:
    return _STEP_SCHEMAS[step_id](current)


def _validate_required_entities(data: dict[str, Any]) -> bool:
    # Validate against required fields shown in the entity mapping step.
    return all(str(data.get(key, "")).strip() for key in _REQUIRED_USER_SCHEMA_KEYS)


class BlockheatConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]
    """Blockheat config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._entity_data: dict[str, Any] = {}
        self._tuning_data: dict[str, Any] = {}

    def _current_state(self) -> dict[str, Any]:
        return {**DEFAULTS, **self._entity_data, **self._tuning_data}

    async def _async_handle_tuning_step(
        self, step_id: str, user_input: dict[str, Any] | None
    ) -> dict[str, Any]:
        current = self._current_state()

        if user_input is not None:
            self._tuning_data.update(user_input)
            current = self._current_state()
            next_step = _next_tuning_step(current, step_id)
            if next_step is None:
                return self.async_create_entry(  # type: ignore[no-any-return]
                    title="Blockheat",
                    data=normalize_entry_data(current),
                )
            return self.async_show_form(  # type: ignore[no-any-return]
                step_id=next_step,
                data_schema=_tuning_schema_for_step(next_step, current),
            )

        return self.async_show_form(  # type: ignore[no-any-return]
            step_id=step_id,
            data_schema=_tuning_schema_for_step(step_id, current),
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        errors: dict[str, str] = {}

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")  # type: ignore[no-any-return]

        if user_input is not None:
            if not _validate_required_entities(user_input):
                errors["base"] = "invalid_required_entities"
            else:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                self._entity_data = user_input
                self._tuning_data = {}
                return await self.async_step_tuning_targets()

        return self.async_show_form(  # type: ignore[no-any-return]
            step_id="user",
            data_schema=_user_schema(self._current_state()),
            errors=errors,
        )

    async def async_step_tuning_targets(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return await self._async_handle_tuning_step(TUNING_TARGETS_STEP, user_input)

    async def async_step_tuning_daikin(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return await self._async_handle_tuning_step(TUNING_DAIKIN_STEP, user_input)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> BlockheatOptionsFlow:
        return BlockheatOptionsFlow(config_entry)


class BlockheatOptionsFlow(config_entries.OptionsFlow):
    """Options flow for Blockheat."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry
        self._entity_data: dict[str, Any] = {}
        self._tuning_data: dict[str, Any] = {}

    def _base_state(self) -> dict[str, Any]:
        return {**DEFAULTS, **self._config_entry.data, **self._config_entry.options}

    def _current_state(self) -> dict[str, Any]:
        return {**self._base_state(), **self._entity_data, **self._tuning_data}

    async def _async_handle_tuning_step(
        self, step_id: str, user_input: dict[str, Any] | None
    ) -> dict[str, Any]:
        current = self._current_state()

        if user_input is not None:
            self._tuning_data.update(user_input)
            current = self._current_state()
            next_step = _next_tuning_step(current, step_id)
            if next_step is None:
                return self.async_create_entry(  # type: ignore[no-any-return]
                    title="",
                    data=normalize_entry_data(current),
                )
            return self.async_show_form(  # type: ignore[no-any-return]
                step_id=next_step,
                data_schema=_tuning_schema_for_step(next_step, current),
            )

        return self.async_show_form(  # type: ignore[no-any-return]
            step_id=step_id,
            data_schema=_tuning_schema_for_step(step_id, current),
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        current = self._current_state()

        if user_input is not None:
            if not _validate_required_entities(user_input):
                return self.async_show_form(  # type: ignore[no-any-return]
                    step_id="init",
                    data_schema=_user_schema(current),
                    errors={"base": "invalid_required_entities"},
                )
            self._entity_data = user_input
            self._tuning_data = {}
            return await self.async_step_tuning_targets()

        return self.async_show_form(  # type: ignore[no-any-return]
            step_id="init",
            data_schema=_user_schema(current),
        )

    async def async_step_tuning_targets(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return await self._async_handle_tuning_step(TUNING_TARGETS_STEP, user_input)

    async def async_step_tuning_daikin(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return await self._async_handle_tuning_step(TUNING_DAIKIN_STEP, user_input)
