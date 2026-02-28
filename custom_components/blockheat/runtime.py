"""Home Assistant runtime adapter for Blockheat."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ServiceNotFound
from homeassistant.helpers import event as event_helper
from homeassistant.helpers import storage
from homeassistant.util import dt as dt_util

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
    DEFAULT_RECOMPUTE_MINUTES,
    DEFAULTS,
    EVENT_BLOCKHEAT_POLICY_CHANGED,
    EVENT_BLOCKHEAT_SNAPSHOT,
    EVENT_ENERGY_SAVING_STATE_CHANGED,
    OPTIONAL_ENTITY_KEYS,
    REQUIRED_ENTITY_KEYS,
    STATE_FALLBACK_ACTIVE,
    STATE_FALLBACK_LAST_TRIGGER,
    STATE_POLICY_LAST_CHANGED,
    STATE_POLICY_ON,
    STATE_STORAGE_KEY_PREFIX,
    STATE_STORAGE_VERSION,
    STATE_TARGET_COMFORT,
    STATE_TARGET_FINAL,
    STATE_TARGET_SAVING,
)
from .coordinator import BlockheatCoordinator
from .engine import (
    as_float,
    as_int,
    compute_comfort_target,
    compute_daikin,
    compute_fallback_conditions,
    compute_final_target,
    compute_floor,
    compute_policy,
    compute_saving_target,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class RuntimeState:
    """Internal runtime state persisted by the integration."""

    policy_on: bool = False
    policy_last_changed: datetime | None = None
    target_saving: float | None = None
    target_comfort: float | None = None
    target_final: float | None = None
    fallback_active: bool = False
    fallback_last_trigger: datetime | None = None


class BlockheatRuntime:
    """Translate HA state/events to pure Blockheat engine operations."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        config: dict[str, Any],
        coordinator: BlockheatCoordinator,
    ) -> None:
        self.hass = hass
        self._entry_id = entry_id
        self._config = {**DEFAULTS, **config}
        self._coordinator = coordinator
        self._unsubscribers: list[Callable[[], None]] = []
        self._fallback_arm_since: datetime | None = None
        self._fallback_arm_timer_unsub: Callable[[], None] | None = None
        self._lock = asyncio.Lock()
        self._state_store: storage.Store[dict[str, Any]] = storage.Store(
            hass,
            STATE_STORAGE_VERSION,
            f"{STATE_STORAGE_KEY_PREFIX}.{entry_id}",
        )
        self._state = RuntimeState()
        self._last_saved_state: dict[str, Any] | None = None

    async def async_setup(self) -> None:
        """Set up listeners and run initial compute."""
        await self._async_load_state()
        self._seed_state_from_legacy_entities()

        monitored_entities: list[str] = []
        for key in REQUIRED_ENTITY_KEYS + OPTIONAL_ENTITY_KEYS:
            entity_id = self._cfg_str(key)
            if entity_id:
                monitored_entities.append(entity_id)

        if monitored_entities:
            self._unsubscribers.append(
                event_helper.async_track_state_change_event(
                    self.hass,
                    monitored_entities,
                    self._async_handle_state_event,
                )
            )

        self._unsubscribers.append(
            event_helper.async_track_time_interval(
                self.hass,
                self._async_handle_periodic,
                timedelta(minutes=DEFAULT_RECOMPUTE_MINUTES),
            )
        )
        self._unsubscribers.append(
            self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_START,
                self._async_handle_start,
            )
        )

        await self.async_recompute("setup")

    async def async_unload(self) -> None:
        """Tear down listeners."""
        await self._async_save_state(force=True)
        self._clear_fallback_arm_timer()
        while self._unsubscribers:
            unsub = self._unsubscribers.pop()
            unsub()

    @callback
    def _async_handle_start(self, _: Event) -> None:
        self.hass.async_create_task(self.async_recompute("ha_start"))

    @callback
    def _async_handle_state_event(self, _: Event) -> None:
        self.hass.async_create_task(self.async_recompute("state_change"))

    @callback
    def _async_handle_periodic(self, _: datetime) -> None:
        self.hass.async_create_task(self.async_recompute("periodic"))

    @callback
    def _async_handle_fallback_arm_timer(self, _: datetime) -> None:
        self._fallback_arm_timer_unsub = None
        self.hass.async_create_task(self.async_recompute("fallback_arm_timer"))

    async def async_recompute(self, reason: str = "manual") -> dict[str, Any]:
        """Recompute full chain and write side-effects."""
        async with self._lock:
            now = dt_util.utcnow()

            policy_result = await self._async_apply_policy(now)
            policy_on_effective = policy_result["policy_on_effective"]

            saving_target = await self._async_apply_saving_target()
            comfort_target = await self._async_apply_comfort_target()

            (
                fallback_active_effective,
                fallback_debug,
            ) = await self._async_apply_fallback(
                now,
                policy_on_effective,
            )

            final_target = await self._async_apply_final_target(
                policy_on_effective=policy_on_effective,
                fallback_active_effective=fallback_active_effective,
                saving_target=saving_target,
                comfort_target=comfort_target,
            )

            daikin_result = await self._async_apply_daikin(policy_on_effective)
            floor_result = await self._async_apply_floor(policy_on_effective, now)

            internal_state = self._serialize_state()
            snapshot = {
                "reason": reason,
                "at": now.isoformat(),
                "policy": policy_result,
                "saving_target": saving_target,
                "comfort_target": comfort_target,
                "fallback": fallback_debug,
                "final_target": final_target,
                "daikin": daikin_result,
                "floor": floor_result,
                "internal_state": internal_state,
            }
            self._coordinator.async_set_updated_data(snapshot)
            self.hass.bus.async_fire(EVENT_BLOCKHEAT_SNAPSHOT, snapshot)
            await self._async_save_state()
            return snapshot

    async def _async_apply_policy(self, now: datetime) -> dict[str, Any]:
        nordpool_price = self._cfg_str(CONF_NORDPOOL_PRICE)

        price_state = self.hass.states.get(nordpool_price)
        price = as_float(price_state.state, 0.0) if price_state else 0.0
        prices_today: list[float] = []
        if price_state:
            attr = price_state.attributes.get("today")
            if isinstance(attr, (list, tuple)):
                prices_today = [
                    value for item in attr if (value := as_float(item)) is not None
                ]

        pv_sensor = self._cfg_str(CONF_PV_SENSOR)
        floor_temp_sensor = self._cfg_str(CONF_FLOOR_TEMP_SENSOR)
        pv_now = self._state_float(pv_sensor, default=0.0) if pv_sensor else 0.0
        floor_temp = (
            self._state_float(floor_temp_sensor, default=0.0)
            if floor_temp_sensor
            else 0.0
        )

        current_on = self._state.policy_on
        last_changed = self._state.policy_last_changed

        computation = compute_policy(
            price=price,
            prices_today=prices_today,
            minutes_to_block=self._cfg_int(CONF_MINUTES_TO_BLOCK, 240),
            price_ignore_below=self._cfg_float(CONF_PRICE_IGNORE_BELOW, 0.0),
            pv_now=pv_now,
            pv_ignore_above_w=self._cfg_float(CONF_PV_IGNORE_ABOVE_W, 0.0),
            floor_temp=floor_temp,
            min_floor_temp=self._cfg_float(CONF_MIN_FLOOR_TEMP, 0.0),
            current_on=current_on,
            last_changed=last_changed,
            now=now,
            min_toggle_interval_min=self._cfg_int(CONF_MIN_TOGGLE_INTERVAL_MIN, 15),
        )

        policy_on_effective = current_on
        transition = "none"
        if computation.should_turn_on:
            self._state.policy_on = True
            self._state.policy_last_changed = now
            policy_on_effective = True
            transition = "on"
            self._fire_policy_events("on", computation)
            await self._async_log(
                "Energy Saving",
                (
                    f"ON - price={computation.price:.3f} >= cutoff={computation.cutoff:.3f}, "
                    f"PV={computation.pv_now:.0f} W, floor={computation.floor_temp:.1f}C"
                ),
            )
        elif computation.should_turn_off:
            self._state.policy_on = False
            self._state.policy_last_changed = now
            policy_on_effective = False
            transition = "off"
            self._fire_policy_events("off", computation)
            if (
                computation.ignore_by_price
                or computation.ignore_by_pv
                or computation.below_min_floor
            ):
                reason = "ignored by price/PV/floor"
            else:
                reason = "price below cutoff"
            await self._async_log(
                "Energy Saving",
                (
                    f"OFF - {reason} "
                    f"(price={computation.price:.3f}, cutoff={computation.cutoff:.3f}, "
                    f"PV={computation.pv_now:.0f} W, floor={computation.floor_temp:.1f}C)"
                ),
            )

        return {
            "target_on": computation.target_on,
            "current_on": current_on,
            "transition": transition,
            "policy_on_effective": policy_on_effective,
            "blocked_now": computation.blocked_now,
            "cutoff": computation.cutoff,
            "price": computation.price,
            "pv_now": computation.pv_now,
            "floor_temp": computation.floor_temp,
            "ignore_by_price": computation.ignore_by_price,
            "ignore_by_pv": computation.ignore_by_pv,
            "below_min_floor": computation.below_min_floor,
            "enough_time_passed": computation.enough_time_passed,
        }

    def _fire_policy_events(self, state: str, computation: Any) -> None:
        reason = "top-N blocked (price >= cutoff)" if state == "on" else "not blocked"
        event_data = {
            "state": state,
            "price": computation.price,
            "cutoff": computation.cutoff,
            "pv_now": computation.pv_now,
            "floor_temp": computation.floor_temp,
            "reason": reason,
        }
        self.hass.bus.async_fire(EVENT_ENERGY_SAVING_STATE_CHANGED, event_data)
        self.hass.bus.async_fire(EVENT_BLOCKHEAT_POLICY_CHANGED, event_data)

    async def _async_apply_saving_target(self) -> float:
        target_current = self._state.target_saving
        target = compute_saving_target(
            outdoor_temp=self._state_float(
                self._cfg_str(CONF_OUTDOOR_TEMPERATURE_SENSOR)
            ),
            heatpump_setpoint=self._cfg_float(CONF_HEATPUMP_SETPOINT, 20.0),
            saving_cold_offset_c=self._cfg_float(CONF_SAVING_COLD_OFFSET_C, 1.0),
            virtual_temperature=self._cfg_float(CONF_VIRTUAL_TEMPERATURE, 20.0),
            warm_shutdown_outdoor=self._cfg_float(
                CONF_ENERGY_SAVING_WARM_SHUTDOWN_OUTDOOR,
                7.0,
            ),
            control_min_c=self._cfg_float(CONF_CONTROL_MIN_C, 10.0),
            control_max_c=self._cfg_float(CONF_CONTROL_MAX_C, 26.0),
        )

        if self._delta_ok(
            target,
            target_current,
            self._cfg_float(CONF_SAVING_HELPER_WRITE_DELTA_C, 0.05),
        ):
            self._state.target_saving = target

        return target

    async def _async_apply_comfort_target(self) -> float:
        target_current = self._state.target_comfort

        computation = compute_comfort_target(
            room1_temp=self._state_float(self._cfg_str(CONF_COMFORT_ROOM_1_SENSOR)),
            room2_temp=self._state_float(self._cfg_str(CONF_COMFORT_ROOM_2_SENSOR)),
            storage_temp=self._state_float(self._cfg_str(CONF_STORAGE_ROOM_SENSOR)),
            outdoor_temp=self._state_float(
                self._cfg_str(CONF_OUTDOOR_TEMPERATURE_SENSOR)
            ),
            comfort_target_c=self._cfg_float(CONF_COMFORT_TARGET_C, 22.0),
            comfort_to_heatpump_offset_c=self._cfg_float(
                CONF_COMFORT_TO_HEATPUMP_OFFSET_C,
                2.0,
            ),
            storage_target_c=self._cfg_float(CONF_STORAGE_TARGET_C, 25.0),
            storage_to_heatpump_offset_c=self._cfg_float(
                CONF_STORAGE_TO_HEATPUMP_OFFSET_C,
                2.0,
            ),
            maintenance_target_c=self._cfg_float(CONF_MAINTENANCE_TARGET_C, 20.0),
            comfort_margin_c=self._cfg_float(CONF_COMFORT_MARGIN_C, 0.2),
            cold_threshold=self._cfg_float(CONF_COLD_THRESHOLD, 0.0),
            max_boost=self._cfg_float(CONF_MAX_BOOST, 3.0),
            boost_slope_c=self._cfg_float(CONF_BOOST_SLOPE_C, 5.0),
            control_min_c=self._cfg_float(CONF_CONTROL_MIN_C, 10.0),
            control_max_c=self._cfg_float(CONF_CONTROL_MAX_C, 26.0),
        )

        if self._delta_ok(
            computation.target,
            target_current,
            self._cfg_float(CONF_COMFORT_HELPER_WRITE_DELTA_C, 0.05),
        ):
            self._state.target_comfort = computation.target

        return computation.target

    async def _async_apply_fallback(
        self,
        now: datetime,
        policy_on: bool,
    ) -> tuple[bool, dict[str, Any]]:
        fallback_active = self._state.fallback_active

        conditions = compute_fallback_conditions(
            policy_on=policy_on,
            fallback_active=fallback_active,
            room1_temp=self._state_float(self._cfg_str(CONF_COMFORT_ROOM_1_SENSOR)),
            room2_temp=self._state_float(self._cfg_str(CONF_COMFORT_ROOM_2_SENSOR)),
            comfort_target_c=self._cfg_float(CONF_COMFORT_TARGET_C, 22.0),
            trigger_delta_c=self._cfg_float(CONF_ELECTRIC_FALLBACK_DELTA_C, 0.5),
            release_delta_c=self._cfg_float(CONF_RELEASE_DELTA_C, 0.1),
            cooldown_minutes=self._cfg_int(CONF_ELECTRIC_FALLBACK_COOLDOWN_MINUTES, 60),
            last_trigger=self._state.fallback_last_trigger,
            now=now,
        )

        should_arm = False
        if conditions.arm_condition:
            if self._fallback_arm_since is None:
                self._fallback_arm_since = now
                self._set_fallback_arm_timer(
                    self._cfg_int(CONF_ELECTRIC_FALLBACK_MINUTES, 30) * 60
                )
            elapsed_sec = (now - self._fallback_arm_since).total_seconds()
            should_arm = elapsed_sec >= (
                self._cfg_int(CONF_ELECTRIC_FALLBACK_MINUTES, 30) * 60
            )
        else:
            self._fallback_arm_since = None
            self._clear_fallback_arm_timer()

        fallback_active_effective = fallback_active
        transition = "none"
        if should_arm:
            fallback_active_effective = True
            transition = "armed"
            self._state.fallback_active = True
            self._state.fallback_last_trigger = now
            self._fallback_arm_since = None
            self._clear_fallback_arm_timer()
        elif conditions.release_by_policy or conditions.release_by_recovery:
            self._state.fallback_active = False
            fallback_active_effective = False
            transition = "released"

        debug = {
            "active_before": fallback_active,
            "active_after": fallback_active_effective,
            "transition": transition,
            "comfort_min": conditions.comfort_min,
            "trigger_threshold": conditions.trigger_threshold,
            "release_threshold": conditions.release_threshold,
            "cooldown_ok": conditions.cooldown_ok,
            "arm_condition": conditions.arm_condition,
            "last_trigger": (
                self._state.fallback_last_trigger.isoformat()
                if self._state.fallback_last_trigger is not None
                else None
            ),
        }
        return fallback_active_effective, debug

    def _set_fallback_arm_timer(self, seconds: int) -> None:
        self._clear_fallback_arm_timer()
        self._fallback_arm_timer_unsub = event_helper.async_call_later(
            self.hass,
            seconds,
            self._async_handle_fallback_arm_timer,
        )

    def _clear_fallback_arm_timer(self) -> None:
        if self._fallback_arm_timer_unsub is not None:
            self._fallback_arm_timer_unsub()
            self._fallback_arm_timer_unsub = None

    async def _async_apply_final_target(
        self,
        *,
        policy_on_effective: bool,
        fallback_active_effective: bool,
        saving_target: float,
        comfort_target: float,
    ) -> float:
        control_number = self._cfg_str(CONF_CONTROL_NUMBER_ENTITY)

        final_current = self._state.target_final
        control_current = self._state_float(control_number)

        final = compute_final_target(
            policy_on=policy_on_effective,
            fallback_active=fallback_active_effective,
            saving_target=saving_target,
            comfort_target=comfort_target,
            control_current=control_current,
            control_min_c=self._cfg_float(CONF_CONTROL_MIN_C, 10.0),
            control_max_c=self._cfg_float(CONF_CONTROL_MAX_C, 26.0),
        )

        if self._delta_ok(
            final.target,
            final_current,
            self._cfg_float(CONF_FINAL_HELPER_WRITE_DELTA_C, 0.05),
        ):
            self._state.target_final = final.target

        if self._delta_ok(
            final.target,
            control_current,
            self._cfg_float(CONF_CONTROL_WRITE_DELTA_C, 0.2),
        ):
            await self._async_call_entity_service(
                "number",
                "set_value",
                control_number,
                value=final.target,
            )

        return final.target

    async def _async_apply_daikin(self, policy_on_effective: bool) -> dict[str, Any]:
        if not self._cfg_bool(CONF_ENABLE_DAIKIN_CONSUMER, False):
            return {"enabled": False}

        climate_entity = self._cfg_str(CONF_DAIKIN_CLIMATE_ENTITY)
        if not climate_entity:
            return {"enabled": True, "skipped": "missing_climate_entity"}

        climate_state = self.hass.states.get(climate_entity)
        current_temp = None
        if climate_state:
            current_temp = as_float(climate_state.attributes.get("temperature"))

        outdoor_sensor = self._cfg_str(CONF_DAIKIN_OUTDOOR_TEMP_SENSOR)
        computation = compute_daikin(
            policy_on=policy_on_effective,
            current_temp=current_temp,
            normal_temperature=self._cfg_float(CONF_DAIKIN_NORMAL_TEMPERATURE, 22.0),
            saving_temperature=self._cfg_float(CONF_DAIKIN_SAVING_TEMPERATURE, 19.0),
            min_temp_change=self._cfg_float(CONF_DAIKIN_MIN_TEMP_CHANGE, 0.5),
            outdoor_temp=self._state_float(outdoor_sensor) if outdoor_sensor else None,
            outdoor_temp_threshold=self._cfg_float(
                CONF_DAIKIN_OUTDOOR_TEMP_THRESHOLD, -10.0
            ),
            outdoor_sensor_defined=bool(outdoor_sensor),
        )

        if computation.should_write and computation.target_temp is not None:
            await self._async_call_entity_service(
                "climate",
                "set_temperature",
                climate_entity,
                temperature=computation.target_temp,
            )

        return {
            "enabled": True,
            "target": computation.target_temp,
            "written": computation.should_write,
            "outdoor_ok": computation.outdoor_ok,
        }

    async def _async_apply_floor(
        self, policy_on_effective: bool, now: datetime
    ) -> dict[str, Any]:
        if not self._cfg_bool(CONF_ENABLE_FLOOR_CONSUMER, False):
            return {"enabled": False}

        climate_entity = self._cfg_str(CONF_FLOOR_CLIMATE_ENTITY)
        if not climate_entity:
            return {"enabled": True, "skipped": "missing_climate_entity"}

        climate_state = self.hass.states.get(climate_entity)
        if climate_state is None:
            return {"enabled": True, "skipped": "climate_state_missing"}

        schedule_entity = self._cfg_str(CONF_FLOOR_COMFORT_SCHEDULE)
        schedule_defined = bool(schedule_entity)
        schedule_on = True
        if schedule_defined:
            schedule_on = self._is_on(schedule_entity)
        dev_min = as_float(climate_state.attributes.get("min_temp"))

        computation = compute_floor(
            policy_on=policy_on_effective,
            cur_temp=as_float(climate_state.attributes.get("temperature")),
            dev_min=dev_min if dev_min is not None else 5.0,
            comfort_temp_c=self._cfg_float(CONF_FLOOR_COMFORT_TEMP_C, 22.0),
            prefer_preset_manual=self._cfg_bool(CONF_FLOOR_PREFER_PRESET_MANUAL, True),
            hvac_mode_when_on=self._cfg_str(CONF_FLOOR_HVAC_MODE_WHEN_ON) or "heat",
            supported_hvac_modes=climate_state.attributes.get("hvac_modes"),
            preset_modes=climate_state.attributes.get("preset_modes"),
            soft_off_temp_override_c=self._cfg_raw(CONF_FLOOR_SOFT_OFF_TEMP_OVERRIDE_C),
            min_keep_temp_c=self._cfg_raw(CONF_FLOOR_MIN_KEEP_TEMP_C),
            schedule_defined=schedule_defined,
            schedule_on=schedule_on,
            last_changed=climate_state.last_changed,
            min_switch_interval_min=self._cfg_int(
                CONF_FLOOR_MIN_SWITCH_INTERVAL_MIN, 15
            ),
            now=now,
        )

        if computation.action == "set_on":
            if computation.use_manual_preset:
                await self._async_call_entity_service(
                    "climate",
                    "set_preset_mode",
                    climate_entity,
                    preset_mode="manual",
                )
            else:
                await self._async_call_entity_service(
                    "climate",
                    "set_hvac_mode",
                    climate_entity,
                    hvac_mode=computation.hvac_mode_final,
                )

            await asyncio.sleep(1)
            await self._async_call_entity_service(
                "climate",
                "set_temperature",
                climate_entity,
                temperature=computation.desired_temp,
            )

        elif computation.action == "set_soft_off":
            if computation.use_manual_preset:
                await self._async_call_entity_service(
                    "climate",
                    "set_preset_mode",
                    climate_entity,
                    preset_mode="manual",
                )

            await asyncio.sleep(1)
            await self._async_call_entity_service(
                "climate",
                "set_temperature",
                climate_entity,
                temperature=computation.soft_off_target,
            )

        return {
            "enabled": True,
            "action": computation.action,
            "desired_temp": computation.desired_temp,
            "soft_off_target": computation.soft_off_target,
        }

    def _delta_ok(self, target: float, current: float | None, delta: float) -> bool:
        if current is None:
            return True
        return abs(target - current) >= delta

    async def _async_call_entity_service(
        self,
        domain: str,
        service: str,
        entity_id: str,
        **data: Any,
    ) -> None:
        payload = {"entity_id": entity_id, **data}
        await self.hass.services.async_call(domain, service, payload, blocking=True)

    async def _async_log(self, name: str, message: str) -> None:
        if not self.hass.services.has_service("logbook", "log"):
            return
        try:
            await self.hass.services.async_call(
                "logbook",
                "log",
                {"name": name, "message": message},
                blocking=True,
            )
        except ServiceNotFound:
            _LOGGER.debug("logbook.log service not available")

    async def _async_load_state(self) -> None:
        raw = await self._state_store.async_load()
        if not isinstance(raw, dict):
            return

        self._state.policy_on = bool(raw.get(STATE_POLICY_ON, False))
        self._state.policy_last_changed = self._parse_datetime_value(
            raw.get(STATE_POLICY_LAST_CHANGED)
        )
        self._state.target_saving = as_float(raw.get(STATE_TARGET_SAVING))
        self._state.target_comfort = as_float(raw.get(STATE_TARGET_COMFORT))
        self._state.target_final = as_float(raw.get(STATE_TARGET_FINAL))
        self._state.fallback_active = bool(raw.get(STATE_FALLBACK_ACTIVE, False))
        self._state.fallback_last_trigger = self._parse_datetime_value(
            raw.get(STATE_FALLBACK_LAST_TRIGGER)
        )
        self._last_saved_state = self._serialize_state()

    async def _async_save_state(self, force: bool = False) -> None:
        serialized = self._serialize_state()
        if not force and serialized == self._last_saved_state:
            return
        await self._state_store.async_save(serialized)
        self._last_saved_state = serialized

    def _seed_state_from_legacy_entities(self) -> None:
        if self._last_saved_state is not None:
            return

        if self._state.policy_last_changed is None:
            policy_state = self.hass.states.get(self._cfg_str(CONF_TARGET_BOOLEAN))
            if policy_state is not None:
                self._state.policy_on = policy_state.state == "on"
                self._state.policy_last_changed = policy_state.last_changed

        if self._state.target_saving is None:
            self._state.target_saving = self._state_float(
                self._cfg_str(CONF_TARGET_SAVING_HELPER)
            )

        if self._state.target_comfort is None:
            self._state.target_comfort = self._state_float(
                self._cfg_str(CONF_TARGET_COMFORT_HELPER)
            )

        if self._state.target_final is None:
            self._state.target_final = self._state_float(
                self._cfg_str(CONF_TARGET_FINAL_HELPER)
            )

        if self._state.fallback_last_trigger is None:
            legacy_last_trigger = self.hass.states.get(
                self._cfg_str(CONF_ELECTRIC_FALLBACK_LAST_TRIGGER)
            )
            if legacy_last_trigger is not None:
                self._state.fallback_last_trigger = self._parse_datetime_value(
                    legacy_last_trigger.state
                )

        legacy_fallback = self.hass.states.get(
            self._cfg_str(CONF_FALLBACK_ACTIVE_BOOLEAN)
        )
        if legacy_fallback is not None:
            self._state.fallback_active = legacy_fallback.state == "on"

    def _serialize_state(self) -> dict[str, Any]:
        return {
            STATE_POLICY_ON: self._state.policy_on,
            STATE_POLICY_LAST_CHANGED: (
                self._state.policy_last_changed.isoformat()
                if self._state.policy_last_changed is not None
                else None
            ),
            STATE_TARGET_SAVING: self._state.target_saving,
            STATE_TARGET_COMFORT: self._state.target_comfort,
            STATE_TARGET_FINAL: self._state.target_final,
            STATE_FALLBACK_ACTIVE: self._state.fallback_active,
            STATE_FALLBACK_LAST_TRIGGER: (
                self._state.fallback_last_trigger.isoformat()
                if self._state.fallback_last_trigger is not None
                else None
            ),
        }

    def _parse_datetime_value(self, value: Any) -> datetime | None:
        parsed = dt_util.parse_datetime(str(value)) if value is not None else None
        if parsed is not None:
            return parsed

        ts = as_float(value)
        if ts is not None:
            return datetime.fromtimestamp(ts, tz=dt_util.UTC)

        return None

    def _state_float(
        self, entity_id: str, default: float | None = None
    ) -> float | None:
        if not entity_id:
            return default
        state = self.hass.states.get(entity_id)
        if state is None:
            return default
        return as_float(state.state, default)

    def _is_on(self, entity_id: str) -> bool:
        if not entity_id:
            return False
        state = self.hass.states.get(entity_id)
        return state is not None and state.state == "on"

    def _cfg_raw(self, key: str) -> Any:
        return self._config.get(key)

    def _cfg_bool(self, key: str, default: bool) -> bool:
        value = self._config.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in {"true", "1", "yes", "on"}
        return bool(value)

    def _cfg_str(self, key: str) -> str:
        value = self._config.get(key, "")
        return value if isinstance(value, str) else str(value)

    def _cfg_int(self, key: str, default: int) -> int:
        return as_int(self._config.get(key), default)

    def _cfg_float(self, key: str, default: float) -> float:
        value = as_float(self._config.get(key))
        if value is None:
            return default
        return value
