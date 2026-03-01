"""Config flow for Blockheat."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_BOOST_SLOPE_C,
    CONF_COLD_THRESHOLD,
    CONF_COMFORT_HELPER_WRITE_DELTA_C,
    CONF_COMFORT_MARGIN_C,
    CONF_COMFORT_ROOM_1_SENSOR,
    CONF_COMFORT_ROOM_2_SENSOR,
    CONF_COMFORT_TARGET_C,
    CONF_COMFORT_TO_HEATPUMP_OFFSET_C,
    CONF_CONTROL_MAX_C,
    CONF_CONTROL_MIN_C,
    CONF_CONTROL_NUMBER_ENTITY,
    CONF_CONTROL_WRITE_DELTA_C,
    CONF_DAIKIN_CLIMATE_ENTITY,
    CONF_DAIKIN_MIN_TEMP_CHANGE,
    CONF_DAIKIN_NORMAL_TEMPERATURE,
    CONF_DAIKIN_OUTDOOR_TEMP_SENSOR,
    CONF_DAIKIN_OUTDOOR_TEMP_THRESHOLD,
    CONF_DAIKIN_SAVING_TEMPERATURE,
    CONF_ELECTRIC_FALLBACK_COOLDOWN_MINUTES,
    CONF_ELECTRIC_FALLBACK_DELTA_C,
    CONF_ELECTRIC_FALLBACK_LAST_TRIGGER,
    CONF_ELECTRIC_FALLBACK_MINUTES,
    CONF_ENABLE_DAIKIN_CONSUMER,
    CONF_ENABLE_FLOOR_CONSUMER,
    CONF_ENERGY_SAVING_WARM_SHUTDOWN_OUTDOOR,
    CONF_FALLBACK_ACTIVE_BOOLEAN,
    CONF_FINAL_HELPER_WRITE_DELTA_C,
    CONF_FLOOR_CLIMATE_ENTITY,
    CONF_FLOOR_COMFORT_SCHEDULE,
    CONF_FLOOR_COMFORT_TEMP_C,
    CONF_FLOOR_HVAC_MODE_WHEN_ON,
    CONF_FLOOR_MIN_KEEP_TEMP_C,
    CONF_FLOOR_MIN_SWITCH_INTERVAL_MIN,
    CONF_FLOOR_PREFER_PRESET_MANUAL,
    CONF_FLOOR_SOFT_OFF_TEMP_OVERRIDE_C,
    CONF_FLOOR_TEMP_SENSOR,
    CONF_HEATPUMP_SETPOINT,
    CONF_MAINTENANCE_TARGET_C,
    CONF_MAX_BOOST,
    CONF_MIN_FLOOR_TEMP,
    CONF_MIN_TOGGLE_INTERVAL_MIN,
    CONF_MINUTES_TO_BLOCK,
    CONF_NORDPOOL_PRICE,
    CONF_OUTDOOR_TEMPERATURE_SENSOR,
    CONF_PRICE_IGNORE_BELOW,
    CONF_PV_IGNORE_ABOVE_W,
    CONF_PV_SENSOR,
    CONF_RELEASE_DELTA_C,
    CONF_SAVING_COLD_OFFSET_C,
    CONF_SAVING_HELPER_WRITE_DELTA_C,
    CONF_STORAGE_ROOM_SENSOR,
    CONF_STORAGE_TARGET_C,
    CONF_STORAGE_TO_HEATPUMP_OFFSET_C,
    CONF_TARGET_BOOLEAN,
    CONF_TARGET_COMFORT_HELPER,
    CONF_TARGET_FINAL_HELPER,
    CONF_TARGET_SAVING_HELPER,
    CONF_VIRTUAL_TEMPERATURE,
    DEFAULTS,
    DOMAIN,
)

TUNING_POLICY_STEP = "tuning_policy"
TUNING_SAVING_STEP = "tuning_saving"
TUNING_COMFORT_STEP = "tuning_comfort"
TUNING_BOOST_STEP = "tuning_boost"
TUNING_FALLBACK_STEP = "tuning_fallback"
TUNING_LIMITS_STEP = "tuning_limits"
TUNING_DAIKIN_STEP = "tuning_daikin"
TUNING_FLOOR_STEP = "tuning_floor"

_REQUIRED_USER_SCHEMA_KEYS: tuple[str, ...] = (
    CONF_TARGET_BOOLEAN,
    CONF_NORDPOOL_PRICE,
    CONF_COMFORT_ROOM_1_SENSOR,
    CONF_COMFORT_ROOM_2_SENSOR,
    CONF_STORAGE_ROOM_SENSOR,
    CONF_OUTDOOR_TEMPERATURE_SENSOR,
    CONF_TARGET_SAVING_HELPER,
    CONF_TARGET_COMFORT_HELPER,
    CONF_TARGET_FINAL_HELPER,
    CONF_FALLBACK_ACTIVE_BOOLEAN,
    CONF_ELECTRIC_FALLBACK_LAST_TRIGGER,
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
    steps = [
        TUNING_POLICY_STEP,
        TUNING_SAVING_STEP,
        TUNING_COMFORT_STEP,
        TUNING_BOOST_STEP,
        TUNING_FALLBACK_STEP,
        TUNING_LIMITS_STEP,
    ]
    if _is_enabled(current.get(CONF_ENABLE_DAIKIN_CONSUMER, False)):
        steps.append(TUNING_DAIKIN_STEP)
    if _is_enabled(current.get(CONF_ENABLE_FLOOR_CONSUMER, False)):
        steps.append(TUNING_FLOOR_STEP)
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
            _required_marker(current, CONF_TARGET_BOOLEAN): _entity_selector(
                "input_boolean"
            ),
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
            _required_marker(current, CONF_TARGET_SAVING_HELPER): _entity_selector(
                "input_number"
            ),
            _required_marker(current, CONF_TARGET_COMFORT_HELPER): _entity_selector(
                "input_number"
            ),
            _required_marker(current, CONF_TARGET_FINAL_HELPER): _entity_selector(
                "input_number"
            ),
            _required_marker(current, CONF_FALLBACK_ACTIVE_BOOLEAN): _entity_selector(
                "input_boolean"
            ),
            _required_marker(
                current, CONF_ELECTRIC_FALLBACK_LAST_TRIGGER
            ): _entity_selector("input_datetime"),
            _required_marker(current, CONF_CONTROL_NUMBER_ENTITY): _entity_selector(
                "number"
            ),
            _optional_marker(current, CONF_PV_SENSOR): _entity_selector("sensor"),
            _optional_marker(current, CONF_FLOOR_TEMP_SENSOR): _entity_selector(
                "sensor"
            ),
            _optional_marker(current, CONF_ENABLE_DAIKIN_CONSUMER): bool,
            _optional_marker(current, CONF_DAIKIN_CLIMATE_ENTITY): _entity_selector(
                "climate"
            ),
            _optional_marker(
                current, CONF_DAIKIN_OUTDOOR_TEMP_SENSOR
            ): _entity_selector("sensor"),
            _optional_marker(current, CONF_ENABLE_FLOOR_CONSUMER): bool,
            _optional_marker(current, CONF_FLOOR_CLIMATE_ENTITY): _entity_selector(
                "climate"
            ),
            _optional_marker(current, CONF_FLOOR_COMFORT_SCHEDULE): _entity_selector(
                ["schedule", "input_boolean"]
            ),
        }
    )


def _tuning_policy_schema(current: dict[str, Any]) -> vol.Schema:
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
                CONF_MIN_FLOOR_TEMP, default=_cfg_value(current, CONF_MIN_FLOOR_TEMP)
            ): _bounded_float(0, 50),
            vol.Required(
                CONF_MIN_TOGGLE_INTERVAL_MIN,
                default=_cfg_value(current, CONF_MIN_TOGGLE_INTERVAL_MIN),
            ): _bounded_int(0, 720),
        }
    )


def _tuning_saving_schema(current: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_HEATPUMP_SETPOINT,
                default=_cfg_value(current, CONF_HEATPUMP_SETPOINT),
            ): _bounded_float(0, 50),
            vol.Required(
                CONF_SAVING_COLD_OFFSET_C,
                default=_cfg_value(current, CONF_SAVING_COLD_OFFSET_C),
            ): _bounded_float(0, 20),
            vol.Required(
                CONF_VIRTUAL_TEMPERATURE,
                default=_cfg_value(current, CONF_VIRTUAL_TEMPERATURE),
            ): _bounded_float(0, 50),
            vol.Required(
                CONF_ENERGY_SAVING_WARM_SHUTDOWN_OUTDOOR,
                default=_cfg_value(current, CONF_ENERGY_SAVING_WARM_SHUTDOWN_OUTDOOR),
            ): _bounded_float(-50, 50),
        }
    )


def _tuning_comfort_schema(current: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_COMFORT_TARGET_C,
                default=_cfg_value(current, CONF_COMFORT_TARGET_C),
            ): _bounded_float(0, 50),
            vol.Required(
                CONF_COMFORT_TO_HEATPUMP_OFFSET_C,
                default=_cfg_value(current, CONF_COMFORT_TO_HEATPUMP_OFFSET_C),
            ): _bounded_float(0, 20),
            vol.Required(
                CONF_STORAGE_TARGET_C, default=_cfg_value(current, CONF_STORAGE_TARGET_C)
            ): _bounded_float(0, 60),
            vol.Required(
                CONF_STORAGE_TO_HEATPUMP_OFFSET_C,
                default=_cfg_value(current, CONF_STORAGE_TO_HEATPUMP_OFFSET_C),
            ): _bounded_float(0, 20),
            vol.Required(
                CONF_MAINTENANCE_TARGET_C,
                default=_cfg_value(current, CONF_MAINTENANCE_TARGET_C),
            ): _bounded_float(0, 50),
            vol.Required(
                CONF_COMFORT_MARGIN_C,
                default=_cfg_value(current, CONF_COMFORT_MARGIN_C),
            ): _bounded_float(0, 5),
        }
    )


def _tuning_boost_schema(current: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_COLD_THRESHOLD, default=_cfg_value(current, CONF_COLD_THRESHOLD)
            ): _bounded_float(-50, 30),
            vol.Required(
                CONF_MAX_BOOST, default=_cfg_value(current, CONF_MAX_BOOST)
            ): _bounded_float(0, 20),
            vol.Required(
                CONF_BOOST_SLOPE_C, default=_cfg_value(current, CONF_BOOST_SLOPE_C)
            ): _bounded_float(0.01, 100),
        }
    )


def _tuning_fallback_schema(current: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_ELECTRIC_FALLBACK_DELTA_C,
                default=_cfg_value(current, CONF_ELECTRIC_FALLBACK_DELTA_C),
            ): _bounded_float(0, 20),
            vol.Required(
                CONF_RELEASE_DELTA_C, default=_cfg_value(current, CONF_RELEASE_DELTA_C)
            ): _bounded_float(0, 20),
            vol.Required(
                CONF_ELECTRIC_FALLBACK_MINUTES,
                default=_cfg_value(current, CONF_ELECTRIC_FALLBACK_MINUTES),
            ): _bounded_int(0, 1440),
            vol.Required(
                CONF_ELECTRIC_FALLBACK_COOLDOWN_MINUTES,
                default=_cfg_value(current, CONF_ELECTRIC_FALLBACK_COOLDOWN_MINUTES),
            ): _bounded_int(0, 1440),
        }
    )


def _tuning_limits_schema(current: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_CONTROL_MIN_C, default=_cfg_value(current, CONF_CONTROL_MIN_C)
            ): _bounded_float(0, 50),
            vol.Required(
                CONF_CONTROL_MAX_C, default=_cfg_value(current, CONF_CONTROL_MAX_C)
            ): _bounded_float(0, 50),
            vol.Required(
                CONF_SAVING_HELPER_WRITE_DELTA_C,
                default=_cfg_value(current, CONF_SAVING_HELPER_WRITE_DELTA_C),
            ): _bounded_float(0, 5),
            vol.Required(
                CONF_COMFORT_HELPER_WRITE_DELTA_C,
                default=_cfg_value(current, CONF_COMFORT_HELPER_WRITE_DELTA_C),
            ): _bounded_float(0, 5),
            vol.Required(
                CONF_FINAL_HELPER_WRITE_DELTA_C,
                default=_cfg_value(current, CONF_FINAL_HELPER_WRITE_DELTA_C),
            ): _bounded_float(0, 5),
            vol.Required(
                CONF_CONTROL_WRITE_DELTA_C,
                default=_cfg_value(current, CONF_CONTROL_WRITE_DELTA_C),
            ): _bounded_float(0, 5),
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
                CONF_DAIKIN_SAVING_TEMPERATURE,
                default=_cfg_value(current, CONF_DAIKIN_SAVING_TEMPERATURE),
            ): _bounded_float(0, 50),
            vol.Required(
                CONF_DAIKIN_OUTDOOR_TEMP_THRESHOLD,
                default=_cfg_value(current, CONF_DAIKIN_OUTDOOR_TEMP_THRESHOLD),
            ): _bounded_float(-50, 50),
            vol.Required(
                CONF_DAIKIN_MIN_TEMP_CHANGE,
                default=_cfg_value(current, CONF_DAIKIN_MIN_TEMP_CHANGE),
            ): _bounded_float(0, 20),
        }
    )


def _tuning_floor_schema(current: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_FLOOR_COMFORT_TEMP_C,
                default=_cfg_value(current, CONF_FLOOR_COMFORT_TEMP_C),
            ): _bounded_float(0, 50),
            vol.Required(
                CONF_FLOOR_PREFER_PRESET_MANUAL,
                default=_cfg_value(current, CONF_FLOOR_PREFER_PRESET_MANUAL),
            ): bool,
            vol.Required(
                CONF_FLOOR_HVAC_MODE_WHEN_ON,
                default=_cfg_value(current, CONF_FLOOR_HVAC_MODE_WHEN_ON),
            ): str,
            vol.Optional(
                CONF_FLOOR_SOFT_OFF_TEMP_OVERRIDE_C,
                default=_cfg_value(current, CONF_FLOOR_SOFT_OFF_TEMP_OVERRIDE_C),
            ): str,
            vol.Optional(
                CONF_FLOOR_MIN_KEEP_TEMP_C,
                default=_cfg_value(current, CONF_FLOOR_MIN_KEEP_TEMP_C),
            ): str,
            vol.Required(
                CONF_FLOOR_MIN_SWITCH_INTERVAL_MIN,
                default=_cfg_value(current, CONF_FLOOR_MIN_SWITCH_INTERVAL_MIN),
            ): _bounded_int(0, 720),
        }
    )


_STEP_SCHEMAS: dict[str, Callable[[dict[str, Any]], vol.Schema]] = {
    TUNING_POLICY_STEP: _tuning_policy_schema,
    TUNING_SAVING_STEP: _tuning_saving_schema,
    TUNING_COMFORT_STEP: _tuning_comfort_schema,
    TUNING_BOOST_STEP: _tuning_boost_schema,
    TUNING_FALLBACK_STEP: _tuning_fallback_schema,
    TUNING_LIMITS_STEP: _tuning_limits_schema,
    TUNING_DAIKIN_STEP: _tuning_daikin_schema,
    TUNING_FLOOR_STEP: _tuning_floor_schema,
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

    async def _async_handle_tuning_step(self, step_id: str, user_input: dict[str, Any] | None) -> dict[str, Any]:
        current = self._current_state()

        if user_input is not None:
            self._tuning_data.update(user_input)
            current = self._current_state()
            next_step = _next_tuning_step(current, step_id)
            if next_step is None:
                return self.async_create_entry(title="Blockheat", data=current)
            return self.async_show_form(
                step_id=next_step,
                data_schema=_tuning_schema_for_step(next_step, current),
            )

        return self.async_show_form(
            step_id=step_id,
            data_schema=_tuning_schema_for_step(step_id, current),
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
        errors: dict[str, str] = {}

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            if not _validate_required_entities(user_input):
                errors["base"] = "invalid_required_entities"
            else:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                self._entity_data = user_input
                self._tuning_data = {}
                return await self.async_step_tuning_policy()

        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(self._current_state()),
            errors=errors,
        )

    async def async_step_tuning_policy(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._async_handle_tuning_step(TUNING_POLICY_STEP, user_input)

    async def async_step_tuning_saving(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._async_handle_tuning_step(TUNING_SAVING_STEP, user_input)

    async def async_step_tuning_comfort(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._async_handle_tuning_step(TUNING_COMFORT_STEP, user_input)

    async def async_step_tuning_boost(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._async_handle_tuning_step(TUNING_BOOST_STEP, user_input)

    async def async_step_tuning_fallback(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._async_handle_tuning_step(TUNING_FALLBACK_STEP, user_input)

    async def async_step_tuning_limits(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._async_handle_tuning_step(TUNING_LIMITS_STEP, user_input)

    async def async_step_tuning_daikin(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._async_handle_tuning_step(TUNING_DAIKIN_STEP, user_input)

    async def async_step_tuning_floor(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._async_handle_tuning_step(TUNING_FLOOR_STEP, user_input)

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

    async def _async_handle_tuning_step(self, step_id: str, user_input: dict[str, Any] | None) -> dict[str, Any]:
        current = self._current_state()

        if user_input is not None:
            self._tuning_data.update(user_input)
            current = self._current_state()
            next_step = _next_tuning_step(current, step_id)
            if next_step is None:
                return self.async_create_entry(title="", data=current)
            return self.async_show_form(
                step_id=next_step,
                data_schema=_tuning_schema_for_step(next_step, current),
            )

        return self.async_show_form(
            step_id=step_id,
            data_schema=_tuning_schema_for_step(step_id, current),
        )

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
        current = self._current_state()

        if user_input is not None:
            if not _validate_required_entities(user_input):
                return self.async_show_form(
                    step_id="init",
                    data_schema=_user_schema(current),
                    errors={"base": "invalid_required_entities"},
                )
            self._entity_data = user_input
            self._tuning_data = {}
            return await self.async_step_tuning_policy()

        return self.async_show_form(step_id="init", data_schema=_user_schema(current))

    async def async_step_tuning_policy(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._async_handle_tuning_step(TUNING_POLICY_STEP, user_input)

    async def async_step_tuning_saving(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._async_handle_tuning_step(TUNING_SAVING_STEP, user_input)

    async def async_step_tuning_comfort(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._async_handle_tuning_step(TUNING_COMFORT_STEP, user_input)

    async def async_step_tuning_boost(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._async_handle_tuning_step(TUNING_BOOST_STEP, user_input)

    async def async_step_tuning_fallback(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._async_handle_tuning_step(TUNING_FALLBACK_STEP, user_input)

    async def async_step_tuning_limits(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._async_handle_tuning_step(TUNING_LIMITS_STEP, user_input)

    async def async_step_tuning_daikin(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._async_handle_tuning_step(TUNING_DAIKIN_STEP, user_input)

    async def async_step_tuning_floor(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._async_handle_tuning_step(TUNING_FLOOR_STEP, user_input)
