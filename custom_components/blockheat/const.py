"""Constants for Blockheat integration."""

from __future__ import annotations

from typing import Any

DOMAIN = "blockheat"
PLATFORMS: list[str] = ["binary_sensor", "sensor"]

CONF_TARGET_BOOLEAN = "target_boolean"
CONF_NORDPOOL_PRICE = "nordpool_price"
CONF_PV_SENSOR = "pv_sensor"
CONF_PV_IGNORE_ABOVE_W = "pv_ignore_above_w"
CONF_MINUTES_TO_BLOCK = "minutes_to_block"
CONF_PRICE_IGNORE_BELOW = "price_ignore_below"

CONF_COMFORT_ROOM_1_SENSOR = "comfort_room_1_sensor"
CONF_COMFORT_ROOM_2_SENSOR = "comfort_room_2_sensor"
CONF_STORAGE_ROOM_SENSOR = "storage_room_sensor"
CONF_OUTDOOR_TEMPERATURE_SENSOR = "outdoor_temperature_sensor"

CONF_TARGET_SAVING_HELPER = "target_saving_helper"
CONF_TARGET_COMFORT_HELPER = "target_comfort_helper"
CONF_TARGET_FINAL_HELPER = "target_final_helper"
CONF_CONTROL_NUMBER_ENTITY = "control_number_entity"

CONF_HEATPUMP_SETPOINT = "heatpump_setpoint"
CONF_SAVING_COLD_OFFSET_C = "saving_cold_offset_c"
CONF_ENERGY_SAVING_WARM_SHUTDOWN_OUTDOOR = "energy_saving_warm_shutdown_outdoor"

CONF_COMFORT_TARGET_C = "comfort_target_c"
CONF_STORAGE_TARGET_C = "storage_target_c"
CONF_HEATPUMP_OFFSET_C = "heatpump_offset_c"
CONF_COLD_THRESHOLD = "cold_threshold"
CONF_MAX_BOOST = "max_boost"

CONF_ENABLE_FORECAST_OPTIMIZATION = "enable_forecast_optimization"
CONF_WEATHER_ENTITY = "weather_entity"

CONF_ENABLE_DAIKIN_CONSUMER = "enable_daikin_consumer"
CONF_DAIKIN_CLIMATE_ENTITY = "daikin_climate_entity"
CONF_DAIKIN_NORMAL_TEMPERATURE = "daikin_normal_temperature"
CONF_DAIKIN_PREHEAT_OFFSET = "daikin_preheat_offset"
CONF_DAIKIN_MILD_THRESHOLD = "daikin_mild_threshold"
CONF_DAIKIN_COLD_THRESHOLD = "daikin_cold_threshold"
CONF_DAIKIN_DISABLE_THRESHOLD = "daikin_disable_threshold"

EVENT_ENERGY_SAVING_STATE_CHANGED = "energy_saving_state_changed"
EVENT_BLOCKHEAT_POLICY_CHANGED = "blockheat_policy_changed"
EVENT_BLOCKHEAT_SNAPSHOT = "blockheat_snapshot"

SERVICE_RECOMPUTE = "recompute"
SERVICE_DUMP_DIAGNOSTICS = "dump_diagnostics"

DEFAULT_RECOMPUTE_MINUTES = 5

HARDCODED: dict[str, object] = {
    "min_toggle_interval_min": 15,
    "comfort_margin_c": 0.25,
    "boost_slope_c": 4.0,
    "control_min_c": 10.0,
    "control_max_c": 26.0,
    "saving_helper_write_delta_c": 0.05,
    "comfort_helper_write_delta_c": 0.05,
    "final_helper_write_delta_c": 0.05,
    "control_write_delta_c": 0.2,
    "daikin_min_temp_change": 0.5,
}

LEGACY_INTERNAL_ENTITY_KEYS: tuple[str, ...] = (
    CONF_TARGET_BOOLEAN,
    CONF_TARGET_SAVING_HELPER,
    CONF_TARGET_COMFORT_HELPER,
    CONF_TARGET_FINAL_HELPER,
)

STATE_POLICY_ON = "policy_on"
STATE_POLICY_LAST_CHANGED = "policy_last_changed"
STATE_TARGET_SAVING = "target_saving"
STATE_TARGET_COMFORT = "target_comfort"
STATE_TARGET_FINAL = "target_final"

STATE_STORAGE_VERSION = 1
STATE_STORAGE_KEY_PREFIX = "blockheat.internal_state"

ENTITY_ID_POLICY_ACTIVE = "binary_sensor.blockheat_energy_saving_active"
ENTITY_ID_TARGET_SAVING = "sensor.blockheat_target_saving"
ENTITY_ID_TARGET_COMFORT = "sensor.blockheat_target_comfort"
ENTITY_ID_TARGET_FINAL = "sensor.blockheat_target_final"

DEFAULTS: dict[str, object] = {
    CONF_MINUTES_TO_BLOCK: 240,
    CONF_PRICE_IGNORE_BELOW: 0.6,
    CONF_PV_SENSOR: "",
    CONF_PV_IGNORE_ABOVE_W: 0.0,
    CONF_HEATPUMP_SETPOINT: 20.0,
    CONF_SAVING_COLD_OFFSET_C: 1.0,
    CONF_ENERGY_SAVING_WARM_SHUTDOWN_OUTDOOR: 8.0,
    CONF_COMFORT_TARGET_C: 22.0,
    CONF_STORAGE_TARGET_C: 24.5,
    CONF_HEATPUMP_OFFSET_C: 2.0,
    CONF_COLD_THRESHOLD: 1.0,
    CONF_MAX_BOOST: 3.0,
    CONF_ENABLE_FORECAST_OPTIMIZATION: False,
    CONF_WEATHER_ENTITY: "",
    CONF_ENABLE_DAIKIN_CONSUMER: False,
    CONF_DAIKIN_CLIMATE_ENTITY: "",
    CONF_DAIKIN_NORMAL_TEMPERATURE: 22.0,
    CONF_DAIKIN_PREHEAT_OFFSET: 2.0,
    CONF_DAIKIN_MILD_THRESHOLD: 5.0,
    CONF_DAIKIN_COLD_THRESHOLD: -5.0,
    CONF_DAIKIN_DISABLE_THRESHOLD: -22.0,
}

REQUIRED_ENTITY_KEYS: tuple[str, ...] = (
    CONF_NORDPOOL_PRICE,
    CONF_COMFORT_ROOM_1_SENSOR,
    CONF_COMFORT_ROOM_2_SENSOR,
    CONF_STORAGE_ROOM_SENSOR,
    CONF_OUTDOOR_TEMPERATURE_SENSOR,
    CONF_CONTROL_NUMBER_ENTITY,
)

OPTIONAL_ENTITY_KEYS: tuple[str, ...] = (
    CONF_PV_SENSOR,
    CONF_WEATHER_ENTITY,
    CONF_DAIKIN_CLIMATE_ENTITY,
)

# Legacy config keys that may exist in saved entries and need migration.
_LEGACY_REMOVED_KEYS = (
    "min_toggle_interval_min",
    "virtual_temperature",
    "maintenance_target_c",
    "comfort_margin_c",
    "boost_slope_c",
    "control_min_c",
    "control_max_c",
    "saving_helper_write_delta_c",
    "comfort_helper_write_delta_c",
    "final_helper_write_delta_c",
    "control_write_delta_c",
    "daikin_min_temp_change",
    "daikin_outdoor_temp_sensor",
    "daikin_saving_temperature",
    "daikin_outdoor_temp_threshold",
)


def normalize_entry_data(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize entry/options data for runtime use and future saves."""
    normalized = {**DEFAULTS, **data}

    # Migrate old dual-offset keys to single heatpump_offset_c.
    # Check raw data (not normalized) so DEFAULTS don't mask the legacy value.
    if "comfort_to_heatpump_offset_c" in data:
        normalized[CONF_HEATPUMP_OFFSET_C] = data["comfort_to_heatpump_offset_c"]
    normalized.pop("comfort_to_heatpump_offset_c", None)
    normalized.pop("storage_to_heatpump_offset_c", None)

    # Strip legacy keys that are now hardcoded or removed.
    for key in _LEGACY_REMOVED_KEYS:
        normalized.pop(key, None)

    # Inject hardcoded values so runtime always sees them.
    normalized.update(HARDCODED)

    for key in LEGACY_INTERNAL_ENTITY_KEYS:
        normalized.pop(key, None)
    return normalized
