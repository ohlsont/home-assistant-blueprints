"""Home Assistant runtime adapter for Blockheat."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.const import EVENT_HOMEASSISTANT_START
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceNotFound
from homeassistant.helpers import event as event_helper
from homeassistant.helpers import storage
from homeassistant.util import dt as dt_util

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
    DEFAULT_RECOMPUTE_MINUTES,
    DEFAULTS,
    EVENT_BLOCKHEAT_POLICY_CHANGED,
    EVENT_BLOCKHEAT_SNAPSHOT,
    HARDCODED,
    OPTIONAL_ENTITY_KEYS,
    REQUIRED_ENTITY_KEYS,
    STATE_POLICY_LAST_CHANGED,
    STATE_POLICY_ON,
    STATE_STORAGE_KEY_PREFIX,
    STATE_STORAGE_VERSION,
    STATE_TARGET_COMFORT,
    STATE_TARGET_FINAL,
    STATE_TARGET_SAVING,
    STATE_WARM_SHUTDOWN,
)
from .engine import (
    as_float,
    as_int,
    compute_comfort_target,
    compute_daikin,
    compute_final_target,
    compute_policy,
    compute_price_quartile,
    compute_saving_target,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from . import BlockheatCoordinator

_LOGGER = logging.getLogger(__name__)

_SELF_WRITTEN_ENTITY_KEYS: tuple[str, ...] = (
    CONF_CONTROL_NUMBER_ENTITY,
    CONF_DAIKIN_CLIMATE_ENTITY,
)

_DAIKIN_CONFIG_DEBUG_KEYS: tuple[str, ...] = (
    CONF_ENABLE_DAIKIN_CONSUMER,
    CONF_DAIKIN_CLIMATE_ENTITY,
    CONF_DAIKIN_NORMAL_TEMPERATURE,
    CONF_DAIKIN_PREHEAT_OFFSET,
    CONF_DAIKIN_MILD_THRESHOLD,
)


@dataclass
class RuntimeState:
    """Internal runtime state persisted by the integration."""

    policy_on: bool = False
    policy_last_changed: datetime | None = None
    target_saving: float | None = None
    target_comfort: float | None = None
    target_final: float | None = None
    warm_shutdown: bool = False


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
        self._config = {
            **DEFAULTS,
            **HARDCODED,
            **self._entry_data,
            **self._entry_options,
        }
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

            prices_today = self._read_prices_today()

            policy_result = await self._async_apply_policy(
                now, trigger_context, prices_today=prices_today
            )
            policy_on_effective = policy_result["policy_on_effective"]

            saving_target, saving_debug = await self._async_apply_saving_target()
            comfort_target, comfort_debug = await self._async_apply_comfort_target()

            final_target, final_debug = await self._async_apply_final_target(
                policy_on_effective=policy_on_effective,
                saving_target=saving_target,
                comfort_target=comfort_target,
                trigger_context=trigger_context,
            )

            daikin_result = await self._async_apply_daikin(
                policy_on_effective, prices_today=prices_today
            )

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

    def _read_prices_today(self) -> list[float]:
        nordpool_price = self._cfg_str(CONF_NORDPOOL_PRICE)
        price_state = self.hass.states.get(nordpool_price)
        if not price_state:
            return []
        attr = price_state.attributes.get("today")
        if not isinstance(attr, (list, tuple)):
            return []
        return [value for item in attr if (value := as_float(item)) is not None]

    async def _async_get_hourly_forecast(
        self, weather_entity: str
    ) -> list[dict[str, Any]]:
        """Fetch hourly forecast from a weather entity, or [] on failure."""
        try:
            response = await self.hass.services.async_call(
                "weather",
                "get_forecasts",
                {"entity_id": weather_entity, "type": "hourly"},
                blocking=True,
                return_response=True,
            )
        except (ServiceNotFound, HomeAssistantError) as exc:
            _LOGGER.debug("Forecast fetch failed for %s: %s", weather_entity, exc)
            return []

        if not isinstance(response, dict):
            return []
        forecasts = response.get(weather_entity)
        if isinstance(forecasts, dict):
            forecasts = forecasts.get("forecast", [])
        if isinstance(forecasts, (list, tuple)):
            return list(forecasts)
        return []

    def _build_outdoor_temps_by_slot(
        self, forecast: list[dict[str, Any]], now: datetime, num_slots: int
    ) -> list[float | None]:
        """Map forecast temps to slot indices (0..num_slots-1).

        Slot 0 = today midnight local hour, slot 23 = today 23:00 local,
        slot 24 = tomorrow midnight local, slot 47 = tomorrow 23:00 local.
        Nordpool prices are indexed in local time, so we convert all
        datetimes to local before extracting date/hour.
        """
        temps: list[float | None] = [None] * num_slots
        local_now = dt_util.as_local(now)
        today_date = local_now.date()
        for entry in forecast:
            dt_raw = entry.get("datetime")
            if dt_raw is None:
                continue
            if isinstance(dt_raw, str):
                dt_parsed = dt_util.parse_datetime(dt_raw)
                if dt_parsed is None:
                    continue
            elif isinstance(dt_raw, datetime):
                dt_parsed = dt_raw
            else:
                continue
            local_dt = dt_util.as_local(dt_parsed)
            day_offset = (local_dt.date() - today_date).days
            if day_offset < 0 or day_offset > 1:
                continue
            slot_idx = day_offset * 24 + local_dt.hour
            if 0 <= slot_idx < num_slots:
                temp = entry.get("temperature")
                if temp is not None:
                    with contextlib.suppress(TypeError, ValueError):
                        temps[slot_idx] = float(temp)
        return temps

    async def _async_apply_policy(
        self,
        now: datetime,
        trigger_context: dict[str, Any],
        *,
        prices_today: list[float],
    ) -> dict[str, Any]:
        nordpool_price = self._cfg_str(CONF_NORDPOOL_PRICE)

        price_state = self.hass.states.get(nordpool_price)
        price = as_float(price_state.state, 0.0) if price_state else 0.0

        # Forecast optimization: extend price window and apply COP weighting.
        forecast_enabled = self._cfg_bool(CONF_ENABLE_FORECAST_OPTIMIZATION, False)
        weather_entity = self._cfg_str(CONF_WEATHER_ENTITY)
        use_cop_weighting = False
        outdoor_temps_by_slot: list[float | None] | None = None
        current_hour_index: int | None = None
        prices_window = list(prices_today)

        if forecast_enabled and weather_entity:
            forecast = await self._async_get_hourly_forecast(weather_entity)
            if forecast:
                # Only extend the price window with tomorrow when the forecast
                # is available — otherwise the non-COP fallback path would rank
                # nslots against a 48-slot window, diluting the daily budget.
                prices_tomorrow: list[float] = []
                if price_state:
                    attr_tmrw = price_state.attributes.get("tomorrow")
                    if isinstance(attr_tmrw, (list, tuple)):
                        prices_tomorrow = [
                            value
                            for item in attr_tmrw
                            if (value := as_float(item)) is not None
                        ]

                if prices_tomorrow:
                    prices_window = prices_today + prices_tomorrow

                outdoor_temps_by_slot = self._build_outdoor_temps_by_slot(
                    forecast, now, len(prices_window)
                )
                use_cop_weighting = True
                current_hour_index = dt_util.as_local(now).hour

        pv_sensor = self._cfg_str(CONF_PV_SENSOR)
        pv_now = self._state_float(pv_sensor, default=0.0) if pv_sensor else 0.0

        current_on = self._state.policy_on
        last_changed = self._state.policy_last_changed

        min_toggle = int(HARDCODED["min_toggle_interval_min"])  # type: ignore[call-overload]

        computation = compute_policy(
            price=price,
            prices_today=prices_window,
            minutes_to_block=self._cfg_int(CONF_MINUTES_TO_BLOCK, 240),
            price_ignore_below=self._cfg_float(CONF_PRICE_IGNORE_BELOW, 0.0),
            pv_now=pv_now,
            pv_ignore_above_w=self._cfg_float(CONF_PV_IGNORE_ABOVE_W, 0.0),
            current_on=current_on,
            last_changed=last_changed,
            now=now,
            min_toggle_interval_min=min_toggle,
            use_cop_weighting=use_cop_weighting,
            outdoor_temps_by_slot=outdoor_temps_by_slot,
            current_hour_index=current_hour_index,
            price_hysteresis_fraction=float(HARDCODED["price_hysteresis_fraction"]),  # type: ignore[arg-type]
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
            "cop_weighting_active": computation.cop_weighting_active,
            "current_true_cost": computation.current_true_cost,
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
        self.hass.bus.async_fire(EVENT_BLOCKHEAT_POLICY_CHANGED, event_data)

    async def _async_apply_saving_target(self) -> tuple[float, dict[str, Any]]:
        target_current = self._state.target_saving
        outdoor_temp = self._state_float(self._cfg_str(CONF_OUTDOOR_TEMPERATURE_SENSOR))
        heatpump_setpoint = self._cfg_float(CONF_HEATPUMP_SETPOINT, 21.0)
        saving_cold_offset_c = self._cfg_float(CONF_SAVING_COLD_OFFSET_C, 1.0)
        warm_shutdown_outdoor = self._cfg_float(
            CONF_ENERGY_SAVING_WARM_SHUTDOWN_OUTDOOR,
            8.0,
        )
        control_min_c = float(HARDCODED["control_min_c"])  # type: ignore[arg-type]
        control_max_c = float(HARDCODED["control_max_c"])  # type: ignore[arg-type]
        warm_shutdown_hysteresis_c = float(HARDCODED["warm_shutdown_hysteresis_c"])  # type: ignore[arg-type]
        computation = compute_saving_target(
            outdoor_temp=outdoor_temp,
            heatpump_setpoint=heatpump_setpoint,
            saving_cold_offset_c=saving_cold_offset_c,
            warm_shutdown_outdoor=warm_shutdown_outdoor,
            control_min_c=control_min_c,
            control_max_c=control_max_c,
            warm_shutdown_hysteresis_c=warm_shutdown_hysteresis_c,
            currently_warm_shutdown=self._state.warm_shutdown,
        )
        self._state.warm_shutdown = computation.warm_shutdown

        write_delta_c = float(HARDCODED["saving_helper_write_delta_c"])  # type: ignore[arg-type]
        write_performed = self._delta_ok(
            computation.target,
            target_current,
            write_delta_c,
        )
        if write_performed:
            self._state.target_saving = computation.target

        debug = {
            "source": (
                "heatpump_setpoint"
                if computation.warm_shutdown
                else "setpoint_minus_offset"
            ),
            "outdoor_temp": outdoor_temp,
            "warm_shutdown_outdoor": warm_shutdown_outdoor,
            "warm_shutdown": computation.warm_shutdown,
            "target": computation.target,
            "target_current": target_current,
            "delta": self._delta_abs(computation.target, target_current),
            "write_delta_c": write_delta_c,
            "write_performed": write_performed,
            "heatpump_setpoint": heatpump_setpoint,
            "saving_cold_offset_c": saving_cold_offset_c,
        }
        return computation.target, debug

    async def _async_apply_comfort_target(self) -> tuple[float, dict[str, Any]]:
        target_current = self._state.target_comfort

        heatpump_setpoint = self._cfg_float(CONF_HEATPUMP_SETPOINT, 21.0)

        comfort_margin_c = float(HARDCODED["comfort_margin_c"])  # type: ignore[arg-type]
        boost_slope_c = float(HARDCODED["boost_slope_c"])  # type: ignore[arg-type]
        control_min_c = float(HARDCODED["control_min_c"])  # type: ignore[arg-type]
        control_max_c = float(HARDCODED["control_max_c"])  # type: ignore[arg-type]

        computation = compute_comfort_target(
            room1_temp=self._state_float(self._cfg_str(CONF_COMFORT_ROOM_1_SENSOR)),
            room2_temp=self._state_float(self._cfg_str(CONF_COMFORT_ROOM_2_SENSOR)),
            storage_temp=self._state_float(self._cfg_str(CONF_STORAGE_ROOM_SENSOR)),
            outdoor_temp=self._state_float(
                self._cfg_str(CONF_OUTDOOR_TEMPERATURE_SENSOR)
            ),
            comfort_target_c=self._cfg_float(CONF_COMFORT_TARGET_C, 22.0),
            storage_target_c=self._cfg_float(CONF_STORAGE_TARGET_C, 25.0),
            heatpump_setpoint=heatpump_setpoint,
            comfort_margin_c=comfort_margin_c,
            cold_threshold=self._cfg_float(CONF_COLD_THRESHOLD, 2.0),
            max_boost=self._cfg_float(CONF_MAX_BOOST, 3.0),
            boost_slope_c=boost_slope_c,
            control_min_c=control_min_c,
            control_max_c=control_max_c,
        )

        write_delta_c = float(HARDCODED["comfort_helper_write_delta_c"])  # type: ignore[arg-type]
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

        control_min_c = float(HARDCODED["control_min_c"])  # type: ignore[arg-type]
        control_max_c = float(HARDCODED["control_max_c"])  # type: ignore[arg-type]

        final = compute_final_target(
            policy_on=policy_on_effective,
            saving_target=saving_target,
            comfort_target=comfort_target,
            control_current=control_current,
            control_min_c=control_min_c,
            control_max_c=control_max_c,
        )

        final_helper_write_delta_c = float(HARDCODED["final_helper_write_delta_c"])  # type: ignore[arg-type]
        control_write_delta_c = float(HARDCODED["control_write_delta_c"])  # type: ignore[arg-type]

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

    async def _async_apply_daikin(
        self, policy_on_effective: bool, *, prices_today: list[float]
    ) -> dict[str, Any]:
        if not self._cfg_bool(CONF_ENABLE_DAIKIN_CONSUMER, False):
            return {"enabled": False}

        climate_entity = self._cfg_str(CONF_DAIKIN_CLIMATE_ENTITY)
        if not climate_entity:
            return {"enabled": True, "skipped": "missing_climate_entity"}

        climate_state = self.hass.states.get(climate_entity)
        current_temp = None
        current_hvac_mode: str | None = None
        if climate_state:
            current_temp = as_float(climate_state.attributes.get("temperature"))
            current_hvac_mode = climate_state.state

        nordpool_price = self._cfg_str(CONF_NORDPOOL_PRICE)
        price_state = self.hass.states.get(nordpool_price)
        current_price = as_float(price_state.state, 0.0) if price_state else 0.0
        current_price = current_price or 0.0
        price_quartile = compute_price_quartile(current_price, prices_today)

        outdoor_sensor = self._cfg_str(CONF_OUTDOOR_TEMPERATURE_SENSOR)
        min_temp_change = float(HARDCODED["daikin_min_temp_change"])  # type: ignore[arg-type]
        computation = compute_daikin(
            current_temp=current_temp,
            current_hvac_mode=current_hvac_mode,
            normal_temperature=self._cfg_float(CONF_DAIKIN_NORMAL_TEMPERATURE, 22.0),
            preheat_offset=self._cfg_float(CONF_DAIKIN_PREHEAT_OFFSET, 2.0),
            min_temp_change=min_temp_change,
            outdoor_temp=self._state_float(outdoor_sensor) if outdoor_sensor else None,
            mild_threshold=self._cfg_float(CONF_DAIKIN_MILD_THRESHOLD, 5.0),
            outdoor_sensor_defined=True,
            price_quartile=price_quartile,
        )

        if computation.should_write_mode and computation.target_hvac_mode is not None:
            if computation.target_hvac_mode == "off":
                await self._async_call_entity_service(
                    "climate", "turn_off", climate_entity
                )
            else:
                await self._async_call_entity_service(
                    "climate", "turn_on", climate_entity
                )

        if computation.should_write_temp and computation.target_temp is not None:
            await self._async_call_entity_service(
                "climate",
                "set_temperature",
                climate_entity,
                temperature=computation.target_temp,
            )

        return {
            "enabled": True,
            "mode": computation.mode,
            "price_quartile": computation.price_quartile,
            "target_temp": computation.target_temp,
            "target_hvac_mode": computation.target_hvac_mode,
            "temp_written": computation.should_write_temp,
            "mode_written": computation.should_write_mode,
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
        if not self.hass.services.has_service(domain, service):
            _LOGGER.warning(
                "Service %s.%s not available, skipping write to %s",
                domain,
                service,
                entity_id,
            )
            return
        payload = {"entity_id": entity_id, **data}
        try:
            await self.hass.services.async_call(domain, service, payload, blocking=True)
        except (ServiceNotFound, HomeAssistantError) as exc:
            _LOGGER.warning(
                "Failed to call %s.%s on %s: %s", domain, service, entity_id, exc
            )

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
        self._state.warm_shutdown = bool(raw.get(STATE_WARM_SHUTDOWN, False))
        self._last_saved_state = self._serialize_state()

    async def _async_save_state(self, force: bool = False) -> None:
        serialized = self._serialize_state()
        if not force and serialized == self._last_saved_state:
            return
        await self._state_store.async_save(serialized)
        self._last_saved_state = serialized

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
            STATE_WARM_SHUTDOWN: self._state.warm_shutdown,
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
            return dt_util.as_utc(parsed)  # type: ignore[no-any-return]

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
