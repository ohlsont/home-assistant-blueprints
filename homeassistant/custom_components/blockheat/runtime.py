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
    CONF_ENABLE_DAIKIN_CONSUMER,
    CONF_ENERGY_SAVING_WARM_SHUTDOWN_OUTDOOR,
    CONF_FINAL_HELPER_WRITE_DELTA_C,
    CONF_HEATPUMP_SETPOINT,
    CONF_MAINTENANCE_TARGET_C,
    CONF_MAX_BOOST,
    CONF_MIN_TOGGLE_INTERVAL_MIN,
    CONF_MINUTES_TO_BLOCK,
    CONF_NORDPOOL_PRICE,
    CONF_OUTDOOR_TEMPERATURE_SENSOR,
    CONF_PRICE_IGNORE_BELOW,
    CONF_PV_IGNORE_ABOVE_W,
    CONF_PV_SENSOR,
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
    compute_final_target,
    compute_policy,
    compute_saving_target,
)

_LOGGER = logging.getLogger(__name__)

_SELF_WRITTEN_ENTITY_KEYS: tuple[str, ...] = (
    CONF_CONTROL_NUMBER_ENTITY,
    CONF_DAIKIN_CLIMATE_ENTITY,
)

_DAIKIN_CONFIG_DEBUG_KEYS: tuple[str, ...] = (
    CONF_ENABLE_DAIKIN_CONSUMER,
    CONF_DAIKIN_CLIMATE_ENTITY,
    CONF_DAIKIN_OUTDOOR_TEMP_SENSOR,
    CONF_DAIKIN_NORMAL_TEMPERATURE,
    CONF_DAIKIN_SAVING_TEMPERATURE,
    CONF_DAIKIN_OUTDOOR_TEMP_THRESHOLD,
    CONF_DAIKIN_MIN_TEMP_CHANGE,
)


@dataclass
class RuntimeState:
    """Internal runtime state persisted by the integration."""

    policy_on: bool = False
    policy_last_changed: datetime | None = None
    target_saving: float | None = None
    target_comfort: float | None = None
    target_final: float | None = None


class BlockheatRuntime:
    """Translate HA state/events to pure Blockheat engine operations."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        config: dict[str, Any],
        coordinator: BlockheatCoordinator,
        *,
        entry_data: dict[str, Any] | None = None,
        entry_options: dict[str, Any] | None = None,
    ) -> None:
        self.hass = hass
        self._entry_id = entry_id
        self._entry_data = dict(config if entry_data is None else entry_data)
        self._entry_options = {} if entry_options is None else dict(entry_options)
        self._config = {**DEFAULTS, **self._entry_data, **self._entry_options}
        self._coordinator = coordinator
        self._unsubscribers: list[Callable[[], None]] = []
        self._lock = asyncio.Lock()
        self._state_store: storage.Store[dict[str, Any]] = storage.Store(
            hass,
            STATE_STORAGE_VERSION,
            f"{STATE_STORAGE_KEY_PREFIX}.{entry_id}",
        )
        self._state = RuntimeState()
        self._last_saved_state: dict[str, Any] | None = None

    @property
    def entry_id(self) -> str:
        """Expose the owning config entry id."""
        return self._entry_id

    async def async_setup(self) -> None:
        """Set up listeners and run initial compute."""
        await self._async_load_state()
        self._seed_state_from_legacy_entities()

        monitored_entities: list[str] = []
        for key in REQUIRED_ENTITY_KEYS + OPTIONAL_ENTITY_KEYS:
            if key in _SELF_WRITTEN_ENTITY_KEYS:
                continue
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
        while self._unsubscribers:
            unsub = self._unsubscribers.pop()
            unsub()

    @callback
    def _async_handle_start(self, _: Event) -> None:
        self.hass.async_create_task(
            self.async_recompute(
                "ha_start",
                trigger={"source": "homeassistant_start"},
            )
        )

    @callback
    def _async_handle_state_event(self, event: Event) -> None:
        event_data = getattr(event, "data", {}) or {}
        trigger: dict[str, Any] = {"source": "state_change"}
        entity_id = event_data.get("entity_id")
        if isinstance(entity_id, str) and entity_id:
            trigger["entity_id"] = entity_id
        self.hass.async_create_task(
            self.async_recompute("state_change", trigger=trigger)
        )

    @callback
    def _async_handle_periodic(self, _: datetime) -> None:
        self.hass.async_create_task(
            self.async_recompute("periodic", trigger={"source": "periodic"})
        )

    async def async_recompute(
        self,
        reason: str = "manual",
        *,
        trigger: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Recompute full chain and write side-effects."""
        async with self._lock:
            now = dt_util.utcnow()
            trigger_context = {"reason": reason}
            if trigger:
                trigger_context.update(trigger)

            policy_result = await self._async_apply_policy(now, trigger_context)
            policy_on_effective = policy_result["policy_on_effective"]

            saving_target, saving_debug = await self._async_apply_saving_target()
            comfort_target, comfort_debug = await self._async_apply_comfort_target()

            final_target, final_debug = await self._async_apply_final_target(
                policy_on_effective=policy_on_effective,
                saving_target=saving_target,
                comfort_target=comfort_target,
                trigger_context=trigger_context,
            )

            daikin_result = await self._async_apply_daikin(policy_on_effective)

            internal_state = self._serialize_state()
            snapshot = {
                "reason": reason,
                "at": now.isoformat(),
                "trigger": trigger_context,
                "policy": policy_result,
                "saving_target": saving_target,
                "saving_debug": saving_debug,
                "comfort_target": comfort_target,
                "comfort_debug": comfort_debug,
                "final_target": final_target,
                "final_debug": final_debug,
                "daikin": daikin_result,
                "config_debug": self._build_config_debug(),
                "internal_state": internal_state,
            }
            self._coordinator.async_set_updated_data(snapshot)
            self.hass.bus.async_fire(EVENT_BLOCKHEAT_SNAPSHOT, snapshot)
            await self._async_save_state()
            return snapshot

    async def _async_apply_policy(
        self, now: datetime, trigger_context: dict[str, Any]
    ) -> dict[str, Any]:
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
        pv_now = self._state_float(pv_sensor, default=0.0) if pv_sensor else 0.0

        current_on = self._state.policy_on
        last_changed = self._state.policy_last_changed

        computation = compute_policy(
            price=price,
            prices_today=prices_today,
            minutes_to_block=self._cfg_int(CONF_MINUTES_TO_BLOCK, 240),
            price_ignore_below=self._cfg_float(CONF_PRICE_IGNORE_BELOW, 0.0),
            pv_now=pv_now,
            pv_ignore_above_w=self._cfg_float(CONF_PV_IGNORE_ABOVE_W, 0.0),
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
                    f"PV={computation.pv_now:.0f} W; "
                    f"{self._trigger_summary(trigger_context)}"
                ),
            )
        elif computation.should_turn_off:
            self._state.policy_on = False
            self._state.policy_last_changed = now
            policy_on_effective = False
            transition = "off"
            self._fire_policy_events("off", computation)
            if computation.ignore_by_price or computation.ignore_by_pv:
                reason = "ignored by price/PV"
            else:
                reason = "price below cutoff"
            await self._async_log(
                "Energy Saving",
                (
                    f"OFF - {reason} "
                    f"(price={computation.price:.3f}, cutoff={computation.cutoff:.3f}, "
                    f"PV={computation.pv_now:.0f} W); "
                    f"{self._trigger_summary(trigger_context)}"
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
            "ignore_by_price": computation.ignore_by_price,
            "ignore_by_pv": computation.ignore_by_pv,
            "enough_time_passed": computation.enough_time_passed,
        }

    def _fire_policy_events(self, state: str, computation: Any) -> None:
        reason = "top-N blocked (price >= cutoff)" if state == "on" else "not blocked"
        event_data = {
            "state": state,
            "price": computation.price,
            "cutoff": computation.cutoff,
            "pv_now": computation.pv_now,
            "reason": reason,
        }
        self.hass.bus.async_fire(EVENT_ENERGY_SAVING_STATE_CHANGED, event_data)
        self.hass.bus.async_fire(EVENT_BLOCKHEAT_POLICY_CHANGED, event_data)

    async def _async_apply_saving_target(self) -> tuple[float, dict[str, Any]]:
        target_current = self._state.target_saving
        outdoor_temp = self._state_float(self._cfg_str(CONF_OUTDOOR_TEMPERATURE_SENSOR))
        heatpump_setpoint = self._cfg_float(CONF_HEATPUMP_SETPOINT, 20.0)
        saving_cold_offset_c = self._cfg_float(CONF_SAVING_COLD_OFFSET_C, 1.0)
        virtual_temperature = self._cfg_float(CONF_VIRTUAL_TEMPERATURE, 20.0)
        warm_shutdown_outdoor = self._cfg_float(
            CONF_ENERGY_SAVING_WARM_SHUTDOWN_OUTDOOR,
            7.0,
        )
        target = compute_saving_target(
            outdoor_temp=outdoor_temp,
            heatpump_setpoint=heatpump_setpoint,
            saving_cold_offset_c=saving_cold_offset_c,
            virtual_temperature=virtual_temperature,
            warm_shutdown_outdoor=warm_shutdown_outdoor,
            control_min_c=self._cfg_float(CONF_CONTROL_MIN_C, 10.0),
            control_max_c=self._cfg_float(CONF_CONTROL_MAX_C, 26.0),
        )

        write_delta_c = self._cfg_float(CONF_SAVING_HELPER_WRITE_DELTA_C, 0.05)
        write_performed = self._delta_ok(
            target,
            target_current,
            write_delta_c,
        )
        if write_performed:
            self._state.target_saving = target

        debug = {
            "source": (
                "virtual_temperature"
                if outdoor_temp is not None and outdoor_temp >= warm_shutdown_outdoor
                else "setpoint_minus_offset"
            ),
            "outdoor_temp": outdoor_temp,
            "warm_shutdown_outdoor": warm_shutdown_outdoor,
            "target": target,
            "target_current": target_current,
            "delta": self._delta_abs(target, target_current),
            "write_delta_c": write_delta_c,
            "write_performed": write_performed,
            "heatpump_setpoint": heatpump_setpoint,
            "saving_cold_offset_c": saving_cold_offset_c,
            "virtual_temperature": virtual_temperature,
        }
        return target, debug

    async def _async_apply_comfort_target(self) -> tuple[float, dict[str, Any]]:
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

        write_delta_c = self._cfg_float(CONF_COMFORT_HELPER_WRITE_DELTA_C, 0.05)
        write_performed = self._delta_ok(
            computation.target,
            target_current,
            write_delta_c,
        )
        if write_performed:
            self._state.target_comfort = computation.target

        if computation.comfort_satisfied and computation.storage_needs_heat:
            route = "storage_max"
        elif computation.comfort_satisfied:
            route = "maintenance"
        else:
            route = "comfort"

        debug = {
            "route": route,
            "target": computation.target,
            "target_current": target_current,
            "delta": self._delta_abs(computation.target, target_current),
            "write_delta_c": write_delta_c,
            "write_performed": write_performed,
            "comfort_satisfied": computation.comfort_satisfied,
            "storage_needs_heat": computation.storage_needs_heat,
            "boost_clamped": computation.boost_clamped,
            "comfort_target_unclamped": computation.comfort_target_unclamped,
            "storage_target_unclamped": computation.storage_target_unclamped,
        }
        return computation.target, debug

    async def _async_apply_final_target(
        self,
        *,
        policy_on_effective: bool,
        saving_target: float,
        comfort_target: float,
        trigger_context: dict[str, Any],
    ) -> tuple[float, dict[str, Any]]:
        control_number = self._cfg_str(CONF_CONTROL_NUMBER_ENTITY)

        final_current = self._state.target_final
        control_current = self._state_float(control_number)

        final = compute_final_target(
            policy_on=policy_on_effective,
            saving_target=saving_target,
            comfort_target=comfort_target,
            control_current=control_current,
            control_min_c=self._cfg_float(CONF_CONTROL_MIN_C, 10.0),
            control_max_c=self._cfg_float(CONF_CONTROL_MAX_C, 26.0),
        )

        final_helper_write_delta_c = self._cfg_float(
            CONF_FINAL_HELPER_WRITE_DELTA_C, 0.05
        )
        control_write_delta_c = self._cfg_float(CONF_CONTROL_WRITE_DELTA_C, 0.2)

        final_helper_write_performed = self._delta_ok(
            final.target,
            final_current,
            final_helper_write_delta_c,
        )
        if final_helper_write_performed:
            self._state.target_final = final.target

        control_write_performed = self._delta_ok(
            final.target,
            control_current,
            control_write_delta_c,
        )
        if control_write_performed:
            await self._async_call_entity_service(
                "number",
                "set_value",
                control_number,
                value=final.target,
            )

        if final_helper_write_performed or control_write_performed:
            await self._async_log(
                "Blockheat Final Target",
                (
                    f"source={final.source}, target={final.target:.3f}, "
                    f"helper_write={final_helper_write_performed}, "
                    f"helper_delta={self._delta_abs(final.target, final_current)}, "
                    f"helper_threshold={final_helper_write_delta_c:.3f}, "
                    f"control_write={control_write_performed}, "
                    f"control_delta={self._delta_abs(final.target, control_current)}, "
                    f"control_threshold={control_write_delta_c:.3f}; "
                    f"{self._trigger_summary(trigger_context)}"
                ),
            )

        debug = {
            "source": final.source,
            "target": final.target,
            "final_helper_current": final_current,
            "final_helper_delta": self._delta_abs(final.target, final_current),
            "final_helper_write_delta_c": final_helper_write_delta_c,
            "final_helper_write_performed": final_helper_write_performed,
            "control_current": control_current,
            "control_delta": self._delta_abs(final.target, control_current),
            "control_write_delta_c": control_write_delta_c,
            "control_write_performed": control_write_performed,
        }
        return final.target, debug

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

    def _delta_ok(self, target: float, current: float | None, delta: float) -> bool:
        if current is None:
            return True
        return abs(target - current) >= delta

    def _delta_abs(self, target: float, current: float | None) -> float | None:
        if current is None:
            return None
        return abs(target - current)

    def _trigger_summary(self, trigger_context: dict[str, Any] | None) -> str:
        if not trigger_context:
            return "trigger=unknown"
        reason = str(trigger_context.get("reason", "unknown"))
        entity_id = trigger_context.get("entity_id")
        source = trigger_context.get("source")
        if isinstance(entity_id, str) and entity_id:
            return f"trigger={reason}, entity_id={entity_id}"
        if isinstance(source, str) and source:
            return f"trigger={reason}, source={source}"
        return f"trigger={reason}"

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
        }

    def _build_config_debug(self) -> dict[str, dict[str, Any]]:
        return {
            "entry_data": self._config_debug_subset(self._entry_data),
            "entry_options": self._config_debug_subset(self._entry_options),
            "effective": {
                key: self._config.get(key) for key in _DAIKIN_CONFIG_DEBUG_KEYS
            },
        }

    def _config_debug_subset(self, source: dict[str, Any]) -> dict[str, Any]:
        return {
            key: source.get(key) if key in source else None
            for key in _DAIKIN_CONFIG_DEBUG_KEYS
        }

    def _parse_datetime_value(self, value: Any) -> datetime | None:
        parsed = dt_util.parse_datetime(str(value)) if value is not None else None
        if parsed is not None:
            return dt_util.as_utc(parsed)

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
