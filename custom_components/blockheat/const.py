"""Constants for Blockheat integration."""

from __future__ import annotations

from typing import Any

DOMAIN = "blockheat"
PLATFORMS: list[str] = ["binary_sensor", "sensor"]

CONF_TARGET_BOOLEAN = "target_boolean"
CONF_NORDPOOL_PRICE = "nordpool_price"
CONF_PV_SENSOR = "pv_sensor"
CONF_PV_IGNORE_ABOVE_W = "pv_ignore_above_w"
CONF_FLOOR_TEMP_SENSOR = "floor_temp_sensor"
CONF_MIN_FLOOR_TEMP = "min_floor_temp"
CONF_MINUTES_TO_BLOCK = "minutes_to_block"
CONF_PRICE_IGNORE_BELOW = "price_ignore_below"
CONF_MIN_TOGGLE_INTERVAL_MIN = "min_toggle_interval_min"

CONF_COMFORT_ROOM_1_SENSOR = "comfort_room_1_sensor"
CONF_COMFORT_ROOM_2_SENSOR = "comfort_room_2_sensor"
CONF_STORAGE_ROOM_SENSOR = "storage_room_sensor"
CONF_OUTDOOR_TEMPERATURE_SENSOR = "outdoor_temperature_sensor"

CONF_TARGET_SAVING_HELPER = "target_saving_helper"
CONF_TARGET_COMFORT_HELPER = "target_comfort_helper"
CONF_TARGET_FINAL_HELPER = "target_final_helper"
CONF_FALLBACK_ACTIVE_BOOLEAN = "fallback_active_boolean"
CONF_ELECTRIC_FALLBACK_LAST_TRIGGER = "electric_fallback_last_trigger"
CONF_CONTROL_NUMBER_ENTITY = "control_number_entity"

CONF_HEATPUMP_SETPOINT = "heatpump_setpoint"
CONF_SAVING_COLD_OFFSET_C = "saving_cold_offset_c"
CONF_VIRTUAL_TEMPERATURE = "virtual_temperature"
CONF_ENERGY_SAVING_WARM_SHUTDOWN_OUTDOOR = "energy_saving_warm_shutdown_outdoor"

CONF_COMFORT_TARGET_C = "comfort_target_c"
CONF_COMFORT_TO_HEATPUMP_OFFSET_C = "comfort_to_heatpump_offset_c"
CONF_STORAGE_TARGET_C = "storage_target_c"
CONF_STORAGE_TO_HEATPUMP_OFFSET_C = "storage_to_heatpump_offset_c"
CONF_MAINTENANCE_TARGET_C = "maintenance_target_c"
CONF_COMFORT_MARGIN_C = "comfort_margin_c"
CONF_COLD_THRESHOLD = "cold_threshold"
CONF_MAX_BOOST = "max_boost"
CONF_BOOST_SLOPE_C = "boost_slope_c"

CONF_CONTROL_MIN_C = "control_min_c"
CONF_CONTROL_MAX_C = "control_max_c"
CONF_SAVING_HELPER_WRITE_DELTA_C = "saving_helper_write_delta_c"
CONF_COMFORT_HELPER_WRITE_DELTA_C = "comfort_helper_write_delta_c"
CONF_FINAL_HELPER_WRITE_DELTA_C = "final_helper_write_delta_c"
CONF_CONTROL_WRITE_DELTA_C = "control_write_delta_c"

CONF_ELECTRIC_FALLBACK_DELTA_C = "electric_fallback_delta_c"
CONF_RELEASE_DELTA_C = "release_delta_c"
CONF_ELECTRIC_FALLBACK_MINUTES = "electric_fallback_minutes"
CONF_ELECTRIC_FALLBACK_COOLDOWN_MINUTES = "electric_fallback_cooldown_minutes"

CONF_ENABLE_DAIKIN_CONSUMER = "enable_daikin_consumer"
CONF_DAIKIN_CLIMATE_ENTITY = "daikin_climate_entity"
CONF_DAIKIN_NORMAL_TEMPERATURE = "daikin_normal_temperature"
CONF_DAIKIN_SAVING_TEMPERATURE = "daikin_saving_temperature"
CONF_DAIKIN_OUTDOOR_TEMP_SENSOR = "daikin_outdoor_temp_sensor"
CONF_DAIKIN_OUTDOOR_TEMP_THRESHOLD = "daikin_outdoor_temp_threshold"
CONF_DAIKIN_MIN_TEMP_CHANGE = "daikin_min_temp_change"

CONF_ENABLE_FLOOR_CONSUMER = "enable_floor_consumer"
CONF_FLOOR_CLIMATE_ENTITY = "floor_climate_entity"
CONF_FLOOR_COMFORT_TEMP_C = "floor_comfort_temp_c"
CONF_FLOOR_PREFER_PRESET_MANUAL = "floor_prefer_preset_manual"
CONF_FLOOR_HVAC_MODE_WHEN_ON = "floor_hvac_mode_when_on"
CONF_FLOOR_SOFT_OFF_TEMP_OVERRIDE_C = "floor_soft_off_temp_override_c"
CONF_FLOOR_MIN_KEEP_TEMP_C = "floor_min_keep_temp_c"
CONF_FLOOR_COMFORT_SCHEDULE = "floor_comfort_schedule"
CONF_FLOOR_MIN_SWITCH_INTERVAL_MIN = "floor_min_switch_interval_min"

EVENT_ENERGY_SAVING_STATE_CHANGED = "energy_saving_state_changed"
EVENT_BLOCKHEAT_POLICY_CHANGED = "blockheat_policy_changed"
EVENT_BLOCKHEAT_SNAPSHOT = "blockheat_snapshot"

SERVICE_RECOMPUTE = "recompute"
SERVICE_DUMP_DIAGNOSTICS = "dump_diagnostics"

DEFAULT_RECOMPUTE_MINUTES = 5
DEFAULT_HELPER_WRITE_DELTA_C = 0.05
DEFAULT_CONTROL_WRITE_DELTA_C = 0.2

LEGACY_INTERNAL_ENTITY_KEYS: tuple[str, ...] = (
    CONF_TARGET_BOOLEAN,
    CONF_TARGET_SAVING_HELPER,
    CONF_TARGET_COMFORT_HELPER,
    CONF_TARGET_FINAL_HELPER,
    CONF_FALLBACK_ACTIVE_BOOLEAN,
    CONF_ELECTRIC_FALLBACK_LAST_TRIGGER,
)

STATE_POLICY_ON = "policy_on"
STATE_POLICY_LAST_CHANGED = "policy_last_changed"
STATE_TARGET_SAVING = "target_saving"
STATE_TARGET_COMFORT = "target_comfort"
STATE_TARGET_FINAL = "target_final"
STATE_FALLBACK_ACTIVE = "fallback_active"
STATE_FALLBACK_LAST_TRIGGER = "fallback_last_trigger"

STATE_STORAGE_VERSION = 1
STATE_STORAGE_KEY_PREFIX = "blockheat.internal_state"

ENTITY_ID_POLICY_ACTIVE = "binary_sensor.blockheat_energy_saving_active"
ENTITY_ID_FALLBACK_ACTIVE = "binary_sensor.blockheat_fallback_active"
ENTITY_ID_TARGET_SAVING = "sensor.blockheat_target_saving"
ENTITY_ID_TARGET_COMFORT = "sensor.blockheat_target_comfort"
ENTITY_ID_TARGET_FINAL = "sensor.blockheat_target_final"
ENTITY_ID_FALLBACK_LAST_TRIGGER = "sensor.blockheat_fallback_last_trigger"

DEFAULTS: dict[str, object] = {
    CONF_MINUTES_TO_BLOCK: 240,
    CONF_PRICE_IGNORE_BELOW: 0.0,
    CONF_PV_SENSOR: "",
    CONF_PV_IGNORE_ABOVE_W: 0.0,
    CONF_FLOOR_TEMP_SENSOR: "",
    CONF_MIN_FLOOR_TEMP: 0.0,
    CONF_MIN_TOGGLE_INTERVAL_MIN: 15,
    CONF_HEATPUMP_SETPOINT: 20.0,
    CONF_SAVING_COLD_OFFSET_C: 1.0,
    CONF_VIRTUAL_TEMPERATURE: 20.0,
    CONF_ENERGY_SAVING_WARM_SHUTDOWN_OUTDOOR: 7.0,
    CONF_COMFORT_TARGET_C: 22.0,
    CONF_COMFORT_TO_HEATPUMP_OFFSET_C: 2.0,
    CONF_STORAGE_TARGET_C: 25.0,
    CONF_STORAGE_TO_HEATPUMP_OFFSET_C: 2.0,
    CONF_MAINTENANCE_TARGET_C: 20.0,
    CONF_COMFORT_MARGIN_C: 0.2,
    CONF_COLD_THRESHOLD: 0.0,
    CONF_MAX_BOOST: 3.0,
    CONF_BOOST_SLOPE_C: 5.0,
    CONF_CONTROL_MIN_C: 10.0,
    CONF_CONTROL_MAX_C: 26.0,
    CONF_SAVING_HELPER_WRITE_DELTA_C: DEFAULT_HELPER_WRITE_DELTA_C,
    CONF_COMFORT_HELPER_WRITE_DELTA_C: DEFAULT_HELPER_WRITE_DELTA_C,
    CONF_FINAL_HELPER_WRITE_DELTA_C: DEFAULT_HELPER_WRITE_DELTA_C,
    CONF_CONTROL_WRITE_DELTA_C: DEFAULT_CONTROL_WRITE_DELTA_C,
    CONF_ELECTRIC_FALLBACK_DELTA_C: 0.5,
    CONF_RELEASE_DELTA_C: 0.1,
    CONF_ELECTRIC_FALLBACK_MINUTES: 30,
    CONF_ELECTRIC_FALLBACK_COOLDOWN_MINUTES: 60,
    CONF_ENABLE_DAIKIN_CONSUMER: False,
    CONF_DAIKIN_CLIMATE_ENTITY: "",
    CONF_DAIKIN_NORMAL_TEMPERATURE: 22.0,
    CONF_DAIKIN_SAVING_TEMPERATURE: 19.0,
    CONF_DAIKIN_OUTDOOR_TEMP_SENSOR: "",
    CONF_DAIKIN_OUTDOOR_TEMP_THRESHOLD: -10.0,
    CONF_DAIKIN_MIN_TEMP_CHANGE: 0.5,
    CONF_ENABLE_FLOOR_CONSUMER: False,
    CONF_FLOOR_CLIMATE_ENTITY: "",
    CONF_FLOOR_COMFORT_TEMP_C: 22.0,
    CONF_FLOOR_PREFER_PRESET_MANUAL: True,
    CONF_FLOOR_HVAC_MODE_WHEN_ON: "heat",
    CONF_FLOOR_SOFT_OFF_TEMP_OVERRIDE_C: "",
    CONF_FLOOR_MIN_KEEP_TEMP_C: "",
    CONF_FLOOR_COMFORT_SCHEDULE: "",
    CONF_FLOOR_MIN_SWITCH_INTERVAL_MIN: 15,
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
    CONF_FLOOR_TEMP_SENSOR,
    CONF_DAIKIN_CLIMATE_ENTITY,
    CONF_DAIKIN_OUTDOOR_TEMP_SENSOR,
    CONF_FLOOR_CLIMATE_ENTITY,
    CONF_FLOOR_COMFORT_SCHEDULE,
)


def normalize_entry_data(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize entry/options data for runtime use and future saves."""
    normalized = {**DEFAULTS, **data}
    for key in LEGACY_INTERNAL_ENTITY_KEYS:
        normalized.pop(key, None)
    return normalized
