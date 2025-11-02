"""Sensor platform for Tag Guard Vehicle."""
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    _LOGGER.info("Setting up Tag Guard Vehicle sensor platform")
    async_add_entities([TagGuardVehicleSensor(hass, entry)])


class TagGuardVehicleSensor(SensorEntity):
    """Representation of a Tag Guard Vehicle sensor."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        """Initialize the sensor."""
        self._hass = hass
        self._entry = entry
        # try to use translation for the sensor name when hass is available
        try:
            name = hass.data.get('translations') and hass.config and getattr(hass.config, 'language', None)
        except Exception:
            name = None
        # prefer including the configured device_tracker in the entity name so
        # multiple instances are distinguishable in the UI. Look first in
        # entry.data then in entry.options under 'device_tracker'.
        try:
            dt = (entry.data or {}).get("device_tracker") or (entry.options or {}).get("device_tracker")
        except Exception:
            dt = None
        if dt:
            # human-friendly name includes the tracker entity id
            self._attr_name = f"Tag Guard Vehicle ({dt})"
            # include tracker in unique id for stronger uniqueness across entries
            safe_dt = dt.replace(".", "_")
            self._attr_unique_id = f"{entry.entry_id}_{safe_dt}_vehicle_status"
        else:
            self._attr_name = "Tag Guard Vehicle"
            self._attr_unique_id = f"{entry.entry_id}_vehicle_status"

        # register an update listener so that if the config entry's options
        # change (for example the `device_tracker` is edited) we update the
        # entity's displayed name automatically. We don't attempt to change
        # the unique_id at runtime since Home Assistant enforces uniqueness
        # and it cannot be reliably mutated after creation.
        try:
            # add_update_listener will call our bound coroutine when entry updates
            entry.add_update_listener(self._async_entry_updated)
        except Exception:
            # older test harnesses or environments may not provide this; ignore
            pass

        # maintain backward-compatible internal state
        self._state = "unknown"
        self._attrs: dict = {}

        # set HA attribute fields so SensorEntity exposes them via standard API
        self._attr_native_value = self._state
        self._attr_extra_state_attributes = self._attrs

    async def async_added_to_hass(self) -> None:
        """Register callbacks when entity is added to hass."""
        await super().async_added_to_hass()
        
        # Listen for update signals from coordinator
        self.async_on_remove(
            async_dispatcher_connect(
                self._hass,
                f"{DOMAIN}_{self._entry.entry_id}_update",
                self._handle_coordinator_update,
            )
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_schedule_update_ha_state(force_refresh=True)

    async def _async_entry_updated(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Called when the config entry is updated (options changed).

        Update the entity's display name to include the current configured
        device_tracker, if any, and write state so the UI refreshes.
        """
        try:
            dt = (entry.data or {}).get("device_tracker") or (entry.options or {}).get("device_tracker")
        except Exception:
            dt = None
        if dt:
            self._attr_name = f"Tag Guard Vehicle ({dt})"
        else:
            self._attr_name = "Tag Guard Vehicle"
        try:
            # request HA to persist the new name in the state machine
            self.async_write_ha_state()
        except Exception:
            # tests may not have full HA runtime; ignore failures
            pass

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._attr_name

    @property
    def unique_id(self) -> str:
        """Return a unique ID to use for this entity."""
        return self._attr_unique_id

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return additional state attributes."""
        return self._attrs

    async def async_update(self) -> None:
        """Fetch new state data for the sensor."""
        coordinator = self._hass.data.get(DOMAIN, {}).get(self._entry.entry_id + "_coordinator")
        if not coordinator:
            _LOGGER.warning("Coordinator not found for entry_id: %s", self._entry.entry_id)
            return
        
        # Log update with safe attribute access (for tests with FakeCoordinator)
        device_tracker = None
        if hasattr(coordinator, "config") and hasattr(coordinator.config, "get"):
            device_tracker = coordinator.config.get("device_tracker")
        _LOGGER.info("Updating sensor for entry_id=%s, device_tracker=%s, alarm_active=%s, coordinator_id=%s", 
                     self._entry.entry_id, 
                     device_tracker,
                     getattr(coordinator, "alarm_active", None),
                     id(coordinator))

        # build attributes
        # expose core persisted state + runtime hints for automations and UI
        self._attrs = {
            "saved_latitude": coordinator.saved_latitude,
            "saved_longitude": coordinator.saved_longitude,
            "saved_gpsUtcDt": getattr(coordinator, "saved_gpsUtcDt", None),
            "saved_last_seen": getattr(coordinator, "saved_last_seen", None),
            "saved_location_type": getattr(coordinator, "saved_location_type", None),
            "tolerance_radius_m": coordinator.tolerance_radius,
            "stationary_minutes": coordinator.stationary_minutes,
            "stationary_counter": getattr(coordinator, "_stationary_counter", None),
            "stationary_candidate": getattr(coordinator, "_stationary_candidate", None),
            "alarm_active": coordinator.alarm_active,
            "position_notified": coordinator.position_notified,
            "last_tag_state": coordinator.last_tag_state,
            "activation_mode": getattr(coordinator, "activation_mode", None),
            "debug_mode": getattr(coordinator, "debug_mode", False),
            "awaiting_activation_save": getattr(coordinator, "_awaiting_activation_save", False),
            # include the configured device_tracker and other config refs so
            # multiple instances can be distinguished by the UI
            "device_tracker": (getattr(coordinator, "config", {}) or {}).get("device_tracker"),
            "person_entity": getattr(coordinator, "person_entity", None),
            "notifier": getattr(coordinator, "notifier", None),
        }

        # Compute state based on coordinator flags:
        # 
        # State Logic (in priority order):
        # 1. 'awaiting_position' -> Alarm active but no position OR waiting for fresh GPS
        # 2. 'alarm_triggered' -> Movement detected, alarm active, notification sent
        # 3. 'parked' -> Position saved, alarm active, monitoring for movement
        # 4. 'position_saved' -> Position saved but alarm not active (stopped/disarmed)
        # 5. 'unknown' -> Initial state, no saved position, alarm not active
        
        awaiting_fresh_gps = getattr(coordinator, "_awaiting_activation_save", False)
        has_position = (coordinator.saved_latitude is not None and coordinator.saved_longitude is not None)
        
        # AWAITING POSITION: Alarm active but no position OR waiting for fresh GPS (HIGHEST PRIORITY)
        # This covers both: initial activation without position, and re-activation waiting for new GPS
        if coordinator.alarm_active and (not has_position or awaiting_fresh_gps):
            self._state = "awaiting_position"
        
        # ALARM TRIGGERED: Movement detected and notification sent
        # Only show this state if we have a position, alarm is active, and position_notified=True
        elif coordinator.alarm_active and coordinator.position_notified and has_position:
            self._state = "alarm_triggered"
        
        # PARKED: Alarm active, position saved, monitoring
        elif coordinator.alarm_active and has_position:
            self._state = "parked"
        
        # POSITION SAVED: Position exists but alarm not active (disarmed)
        elif has_position and not coordinator.alarm_active:
            self._state = "position_saved"
        
        # UNKNOWN: No position, no alarm
        else:
            self._state = "unknown"

        # mirror into HA standard attrs
        try:
            self._attr_native_value = self._state
            self._attr_extra_state_attributes = self._attrs
        except Exception:
            # fallback: keep internal fields; tests will still read .state and .extra_state_attributes
            pass
