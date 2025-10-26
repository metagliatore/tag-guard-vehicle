"""Coordinator for Vehicle BT Parking Sentinel.

Handles listening to device_tracker changes, saving/loading parking
position, stationary detection and sending notifications.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.helpers.event import async_track_state_change_event, async_call_later

from .const import (
    DOMAIN,
    CONF_TOLERANCE_RADIUS,
    CONF_STATIONARY_MINUTES,
    CONF_STATIONARY_COUNT,
    CONF_PERSON_ENTITY,
    CONF_NOTIFIER,
    CONF_ACTIVATION_MODE,
)
from .utils import (
    safe_get,
    haversine_distance,
    update_stationary_counter,
    parse_connection_state,
    extract_coords_from_ops_attrs,
    build_notify_message,
    should_finalize_combined,
    format_map_url,
    normalize_notification_action,
)

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY = f"{DOMAIN}_storage"
STORAGE_VERSION = 1


class VehicleCoordinator:
    def __init__(self, hass: HomeAssistant, entry_id: str, config: dict[str, Any]):
        """Initialize the coordinator for a config entry instance."""
        self.hass = hass
        self.entry_id = entry_id
        self.config = config

        # use per-entry storage key so multiple instances don't collide
        self.store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{entry_id}")

        # persisted state
        self.saved_latitude: float | None = None
        self.saved_longitude: float | None = None
        # metadata saved alongside the parking coordinates
        self.saved_gpsUtcDt: str | None = None
        self.saved_location_type: str | None = None
        self.saved_last_seen: str | None = None
        self.position_notified: bool = False
        self.last_tag_state: str | None = None

        # runtime / config (apply defaults if missing)
        self.notifier = config.get(CONF_NOTIFIER)
        self.person_entity = config.get(CONF_PERSON_ENTITY)
        self.activation_mode = config.get(CONF_ACTIVATION_MODE)
        self.tolerance_radius = float(config.get(CONF_TOLERANCE_RADIUS, 200))
        self.stationary_minutes = int(config.get(CONF_STATIONARY_MINUTES, 10))
        self.stationary_count = int(config.get(CONF_STATIONARY_COUNT, 3))
        # In 'manual' activation mode the alarm should be off by default.
        # For other modes keep the legacy behavior of enabled by default.
        try:
            self.alarm_active = False if str(self.activation_mode) == "manual" else True
        except Exception:
            self.alarm_active = True
        self.debug_mode = bool(config.get("debug_mode", False))

        # runtime helpers
        self._unsub_track = None
        self._stationary_handle = None
        # flag indicating we enabled alarm but have not yet found a fresh GPS to save
        self._awaiting_activation_save = False
        # stored activation time string used to compare gpsUtcDt
        self._activation_time_str = None
        # track consecutive reports within tolerance for the current candidate position
        self._stationary_counter = 0
        self._stationary_candidate = None  # tuple(lat, lon)
        self._stationary_start_utc = None
        self._stationary_candidate_gpsUtcDt = None

    def _debug_notify(self, message: str) -> None:
        """Send debug message to logger."""
        _LOGGER.debug(message)

    async def async_load(self) -> None:
        # Apply options FIRST if present in config (before loading storage)
        # This ensures activation_mode is set correctly before we check it
        options = self.config.get("options") or {}
        if options:
            # Apply options early so activation_mode is available
            if CONF_PERSON_ENTITY in options:
                self.person_entity = options[CONF_PERSON_ENTITY]
            if CONF_NOTIFIER in options:
                self.notifier = options[CONF_NOTIFIER]
            if CONF_TOLERANCE_RADIUS in options:
                self.tolerance_radius = float(options[CONF_TOLERANCE_RADIUS])
            if CONF_ACTIVATION_MODE in options:
                self.activation_mode = options[CONF_ACTIVATION_MODE]
            if CONF_STATIONARY_MINUTES in options:
                self.stationary_minutes = int(options[CONF_STATIONARY_MINUTES])
            if CONF_STATIONARY_COUNT in options:
                self.stationary_count = int(options[CONF_STATIONARY_COUNT])
            if "tag_model" in options:
                self.config["tag_model"] = options["tag_model"]
            if "debug_mode" in options:
                self.debug_mode = bool(options["debug_mode"])
            _LOGGER.debug("Applied options early (before storage load): %s", options)
        
        data = await self.store.async_load()
        if data:
            self.saved_latitude = data.get("saved_latitude")
            self.saved_longitude = data.get("saved_longitude")
            self.saved_gpsUtcDt = data.get("saved_gpsUtcDt")
            self.saved_location_type = data.get("saved_location_type")
            self.saved_last_seen = data.get("saved_last_seen")
            self.position_notified = data.get("position_notified", False)
            self.last_tag_state = data.get("last_tag_state")
            # Load alarm_active ONLY if NOT in manual mode
            # In manual mode, always start with alarm_active = False
            if "alarm_active" in data and str(self.activation_mode) != "manual":
                self.alarm_active = data.get("alarm_active", False)
                _LOGGER.debug("Restored alarm_active from storage: %s (mode=%s)", self.alarm_active, self.activation_mode)
            elif str(self.activation_mode) == "manual":
                # Manual mode always starts with alarm disabled
                self.alarm_active = False
                _LOGGER.debug("Manual mode detected - forcing alarm_active=False (mode=%s)", self.activation_mode)
            else:
                # No alarm_active in storage and not manual mode - use default
                _LOGGER.debug("No alarm_active in storage, using default: %s (mode=%s)", self.alarm_active, self.activation_mode)

        # Validate state consistency after loading from store
        self._validate_and_fix_state()

    async def async_save(self) -> None:
        await self.store.async_save(
            {
                "saved_latitude": self.saved_latitude,
                "saved_longitude": self.saved_longitude,
                "saved_gpsUtcDt": self.saved_gpsUtcDt,
                "saved_location_type": self.saved_location_type,
                "saved_last_seen": self.saved_last_seen,
                "position_notified": self.position_notified,
                "last_tag_state": self.last_tag_state,
                "alarm_active": self.alarm_active,
            }
        )
        # Trigger sensor update after saving state (if hass has dispatcher support)
        try:
            from homeassistant.helpers.dispatcher import async_dispatcher_send
            async_dispatcher_send(self.hass, f"{DOMAIN}_{self.entry_id}_update")
        except (AttributeError, KeyError):
            # hass.data not available (e.g., in unit tests with FakeHass)
            pass

    async def async_initialize_position_if_needed(self, device_tracker_entity: str) -> None:
        """Initialize saved position from device_tracker if missing.
        
        Called during setup after async_load(). If no saved position exists,
        retrieves current coordinates from the device_tracker and saves them
        as the initial parking position. This ensures the integration always
        has a reference position to work with.
        
        Note: This does NOT activate the alarm - it only initializes coordinates.
        In manual mode, alarm_active remains False until explicitly enabled.
        """
        # Only initialize if we have no saved coordinates
        if self.saved_latitude is not None and self.saved_longitude is not None:
            if self.debug_mode:
                _LOGGER.debug("Saved position already exists, skipping initialization")
                self._debug_notify("Saved position already exists, skipping initialization")
            return
        
        # Get current position from device_tracker
        state = self.hass.states.get(device_tracker_entity)
        if state is None:
            _LOGGER.warning(
                "Cannot initialize position: device_tracker %s not found",
                device_tracker_entity
            )
            return
        
        lat = state.attributes.get("latitude")
        lon = state.attributes.get("longitude")
        
        if lat is None or lon is None:
            _LOGGER.warning(
                "Cannot initialize position: no coordinates in device_tracker %s",
                device_tracker_entity
            )
            return
        
        # Extract additional GPS metadata if available
        gps_utc_dt = None
        location_type = None
        last_seen = state.attributes.get("last_seen")
        
        # Try to get gpsUtcDt from ops or extra attributes
        ops = state.attributes.get("ops", [])
        if ops and isinstance(ops, list) and len(ops) > 0:
            extra = ops[0].get("extra", {})
            gps_utc_dt = extra.get("gpsUtcDt")
            location_type = ops[0].get("locationType")
        
        # Save the initial position
        self.saved_latitude = lat
        self.saved_longitude = lon
        self.saved_gpsUtcDt = gps_utc_dt
        self.saved_location_type = location_type
        self.saved_last_seen = last_seen
        
        await self.async_save()
        
        _LOGGER.info(
            "Initialized parking position from device_tracker: lat=%s, lon=%s (alarm_active=%s)",
            lat, lon, self.alarm_active
        )

    def _validate_and_fix_state(self) -> None:
        """Validate state consistency and fix common issues.
        
        This method detects and fixes inconsistent states that can occur due to:
        - Upgrades from older versions
        - Interrupted save operations
        - Manual edits to the storage file
        
        Common issues fixed:
        1. alarm_active=True in manual mode (should be False by default)
        2. awaiting_activation_save=False but no saved position and alarm active
           (indicates interrupted save, should re-enable awaiting flag)
        """
        # Issue #1: In manual mode, alarm should default to False unless explicitly activated
        # If we loaded from store and activation_mode is manual, ensure alarm starts as False
        # (this handles the case where a previous version left alarm_active=True in storage)
        if str(self.activation_mode) == "manual" and self.alarm_active:
            # Check if we have a valid saved position - if so, keep alarm active
            # Otherwise, reset to False (user must manually activate)
            if self.saved_latitude is None or self.saved_longitude is None:
                if self.debug_mode:
                    _LOGGER.debug(
                        "State validation: resetting alarm_active to False in manual mode (no saved position)"
                    )
                self.alarm_active = False
        
        # Issue #2: Detect interrupted save scenario
        # If alarm is active but we have no saved position and awaiting flag is False,
        # this indicates the save was interrupted or never completed. Re-enable awaiting.
        if self.alarm_active and not self._awaiting_activation_save:
            if self.saved_latitude is None or self.saved_longitude is None:
                if self.debug_mode:
                    _LOGGER.debug(
                        "State validation: alarm active but no saved position - enabling awaiting_activation_save"
                    )
                self._awaiting_activation_save = True
                # Set a current activation time so we can detect fresh GPS
                from datetime import datetime
                self._activation_time_str = datetime.utcnow().strftime('%Y%m%d%H%M%S')
                # Notify sensor immediately to show awaiting_position state
                try:
                    from homeassistant.helpers.dispatcher import async_dispatcher_send
                    async_dispatcher_send(self.hass, f"{DOMAIN}_{self.entry_id}_update")
                except (AttributeError, KeyError, ImportError):
                    pass

    async def async_update_options(self, options: dict | None) -> None:
        """Apply runtime options from config entry options dict."""
        if not options:
            return
        # update runtime configuration
        self.notifier = options.get(CONF_NOTIFIER, self.notifier)
        self.person_entity = options.get(CONF_PERSON_ENTITY, self.person_entity)
        self.activation_mode = options.get(CONF_ACTIVATION_MODE, self.activation_mode)
        try:
            self.tolerance_radius = float(options.get(CONF_TOLERANCE_RADIUS, self.tolerance_radius))
        except Exception:
            pass
        try:
            self.stationary_minutes = int(options.get(CONF_STATIONARY_MINUTES, self.stationary_minutes))
        except Exception:
            pass
        try:
            self.stationary_count = int(options.get(CONF_STATIONARY_COUNT, self.stationary_count))
        except Exception:
            pass
        # apply debug_mode and tag_model if present
        try:
            self.debug_mode = bool(options.get("debug_mode", self.debug_mode))
        except Exception:
            pass
        try:
            # tag_model indicates which parser to use
            self.config["tag_model"] = options.get("tag_model", self.config.get("tag_model"))
        except Exception:
            pass
        # store options in config for persistence if desired
        self.config.setdefault("options", {})
        self.config["options"].update(options)
        if self.debug_mode:
            _LOGGER.debug("Applied new options to coordinator: %s", options)
            self._debug_notify(f"Options updated: {options}")

    async def async_start(self, device_tracker_entity: str):
        # subscribe to device_tracker state changes
        self._unsub_track = async_track_state_change_event(
            self.hass, [device_tracker_entity], self._async_device_tracker_changed
        )

    async def async_stop(self):
        if self._unsub_track:
            self._unsub_track()
            self._unsub_track = None

    @callback
    def _async_device_tracker_changed(self, event):
        # schedule processing
        self.hass.async_create_task(self._handle_device_event(event))

    async def _handle_device_event(self, event):
        # event.data contains entity_id, old_state, new_state
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")
        entity_id = event.data.get("entity_id")

        if new_state is None:
            return

        attrs = new_state.attributes

        # extract smarttag ops if present
        ops = attrs.get("ops") or []
        # ops might be a JSON string in some trackers; attempt to parse
        if isinstance(ops, str):
            try:
                import json

                ops = json.loads(ops)
            except Exception:
                ops = []
        if not isinstance(ops, list):
            ops = list(ops) if ops else []

        last_op = ops[0] if len(ops) > 0 else {}

        # parse connection state and last op using helper (model-aware)
        tag_model = self.config.get("tag_model")
        from .utils import parse_connection_state_by_model

        connected, _parsed_last_op = parse_connection_state_by_model(tag_model, ops, attrs)
        # prefer parsed last_op when available
        if _parsed_last_op:
            last_op = _parsed_last_op

        new_tag_state = "connected" if connected else "disconnected"

        # detect change
        if new_tag_state != self.last_tag_state:
            if self.debug_mode:
                _LOGGER.debug("Tag state changed %s -> %s", self.last_tag_state, new_tag_state)
            self.last_tag_state = new_tag_state
            await self.async_save()

            # if disconnected -> interpret as parked and save position if available
            # decide if disconnect should finalize save (handles combined mode)
            if should_finalize_combined(self.activation_mode, new_tag_state, self._stationary_counter, self.stationary_count):
                from .utils import extract_coords_from_ops_attrs_by_model

                lat, lon = extract_coords_from_ops_attrs_by_model(tag_model, last_op, attrs)
                # try to pass gps timestamp and meta if available
                gpsUtcDt = safe_get(last_op, "extra", "gpsUtcDt") or safe_get(last_op, "gpsUtcDt") or attrs.get("gpsUtcDt")
                locationType = safe_get(last_op, "extra", "locationType") or safe_get(last_op, "locationType") or attrs.get("locationType")
                last_seen = attrs.get("last_seen")
                if lat is not None and lon is not None:
                    await self._async_save_position(lat, lon, gpsUtcDt=gpsUtcDt, locationType=locationType, last_seen=last_seen, reason="disconnect")
                else:
                    # nothing to save now; if we recently enabled and are awaiting
                    # a fresh GPS reading, keep awaiting flag set so that later
                    # device events can trigger the save
                    if getattr(self, "_awaiting_activation_save", False):
                        # remain awaiting; nothing to do here
                        pass

        # If activation mode is 'position' we'll handle movement via saved pos comparisons
        # Save latest coordinates for stationary detection
        from .utils import extract_coords_from_ops_attrs_by_model

        latitude, longitude = extract_coords_from_ops_attrs_by_model(self.config.get("tag_model"), last_op, attrs)

        if latitude is not None and longitude is not None:
            try:
                lat_f = float(latitude)
                lon_f = float(longitude)
            except Exception:
                lat_f = None
                lon_f = None

            if lat_f is not None and lon_f is not None:
                # if we have saved position and alarm is active, check movement
                if self.saved_latitude is not None and self.alarm_active:
                    if self.has_moved(lat_f, lon_f, self.tolerance_radius):
                        # avoid duplicate notifications
                        if not self.position_notified:
                            # build message and call notifier
                            # use translated notify title/message
                            try:
                                from .utils import async_build_notify_message

                                title, message = await async_build_notify_message(self.hass, lat_f, lon_f)
                            except Exception:
                                title, _ = build_notify_message(lat_f, lon_f)
                                message = format_map_url(lat_f, lon_f)
                            await self.hass.services.async_call("notify", self.notifier, {"title": title, "message": message})
                            self.position_notified = True
                            await self.async_save()

                # stationary detection and count handling: only for position/combined modes
                if self.activation_mode in ("position", "combined"):
                    # update stationary candidate and counter using helper
                    candidate, counter = update_stationary_counter(
                        self._stationary_candidate, self._stationary_counter, (lat_f, lon_f), self.tolerance_radius
                    )
                    self._stationary_candidate = candidate
                    self._stationary_counter = counter

                    # if this is the start of a new candidate, record the start UTC
                    if counter == 1:
                        try:
                            from datetime import datetime

                            self._stationary_start_utc = datetime.utcnow().strftime('%Y%m%d%H%M%S')
                        except Exception:
                            self._stationary_start_utc = None
                        # capture candidate gpsUtcDt if present for later verification
                        try:
                            self._stationary_candidate_gpsUtcDt = safe_get(last_op, "extra", "gpsUtcDt") or None
                        except Exception:
                            self._stationary_candidate_gpsUtcDt = None

                    # schedule/refresh timer for stationary_minutes
                    if self._stationary_handle:
                        self._stationary_handle()
                    self._stationary_handle = async_call_later(
                        self.hass,
                        self.stationary_minutes * 60,
                        lambda _now: self.hass.async_create_task(self._stationary_check(lat_f, lon_f)),
                    )

                    # If activation is 'combined' and the tag is disconnected we only
                    # finalize when both connection and stationary criteria are met.
                    # The actual save-on-disconnect logic is handled in the connection
                    # branch above which calls _async_save_position when disconnected.
                    # Here we only track stationary_count and timer; the combined
                    # activation will require both events to have occurred.

        # If we were awaiting a save triggered by enable->wegun, check gps freshness
        try:
            if getattr(self, "_awaiting_activation_save", False):
                # try to extract gpsUtcDt from last_op or attrs
                try:
                    gpsUtcDt = safe_get(last_op, "extra", "gpsUtcDt") or safe_get(last_op, "gpsUtcDt") or attrs.get("gpsUtcDt")
                except Exception:
                    gpsUtcDt = None
                # if gpsUtcDt is available and numeric, and we have stored activation_time
                act_time = getattr(self, "_activation_time_str", None)
                try:
                    if act_time and gpsUtcDt and str(gpsUtcDt).isdigit() and int(str(gpsUtcDt)) > int(str(act_time)):
                        # coordinates should already be present in latitude/longitude (above block)
                        if latitude is not None and longitude is not None:
                            await self._async_save_position(latitude, longitude, gpsUtcDt=gpsUtcDt, locationType=None, last_seen=attrs.get("last_seen"), reason="start")
                            self._awaiting_activation_save = False
                            if self.debug_mode:
                                _LOGGER.debug(
                                    "Awaiting save completed: fresh GPS found (gpsUtcDt=%s > activation_time=%s)",
                                    gpsUtcDt, act_time
                                )
                        else:
                            # GPS timestamp is fresh but coordinates are missing - log this anomaly
                            if self.debug_mode:
                                _LOGGER.warning(
                                    "Awaiting save: GPS timestamp is fresh (gpsUtcDt=%s > activation_time=%s) but coordinates are None. "
                                    "This may indicate a parser issue. last_op=%s, attrs_keys=%s",
                                    gpsUtcDt, act_time, last_op, list(attrs.keys()) if isinstance(attrs, dict) else None
                                )
                except Exception as e:
                    # on any parse/compare error, do nothing and keep awaiting
                    if self.debug_mode:
                        _LOGGER.debug("Awaiting save: error during GPS freshness check: %s", e)
                    pass
        except Exception:
            pass

    async def set_alarm_active(self, active: bool, activation_time: str | None = None) -> None:
        """Set alarm active state.

        If enabling the alarm (active=True), attempt to immediately save the current
        device tracker coordinates if the device reports a gpsUtcDt newer than the
        activation time. If already enabled and called again, reset awaiting state
        to search for fresh position again.
        
        The optional `activation_time` (format YYYYMMDDHHMMSS) can be provided for
        testing; otherwise current UTC time is used.
        """
        previous = bool(getattr(self, "alarm_active", False))
        self.alarm_active = bool(active)
        _LOGGER.info("Alarm active changed: %s -> %s", previous, self.alarm_active)
        await self.async_save()

        # If we're enabling (either fresh enable OR re-enable while already active)
        # In case of re-enable, reset the awaiting flag to search for fresh GPS again
        if self.alarm_active:
            # Reset awaiting flag - this allows re-starting the position search
            self._awaiting_activation_save = False
            
            # Reset position_notified - this un-mutes notifications for the new monitoring session
            self.position_notified = False
            
            # determine activation time string (YYYYMMDDHHMMSS)
            try:
                from datetime import datetime

                if activation_time:
                    act_ts = str(activation_time)
                else:
                    act_ts = datetime.utcnow().strftime('%Y%m%d%H%M%S')
            except Exception:
                act_ts = None

            # attempt to read coords from configured device tracker
            device_entity = self.config.get("device_tracker")
            if device_entity:
                state = self.hass.states.get(device_entity)
                if state:
                    try:
                        from .utils import extract_coords_from_ops_attrs_by_model, safe_get

                        ops = state.attributes.get("ops") or []
                        last_op = ops[0] if isinstance(ops, (list, tuple)) and len(ops) > 0 else {}
                        lat, lon = extract_coords_from_ops_attrs_by_model(self.config.get("tag_model"), last_op, state.attributes)
                        gpsUtcDt = safe_get(last_op, "extra", "gpsUtcDt") or safe_get(last_op, "gpsUtcDt") or state.attributes.get("gpsUtcDt")
                        
                        # Track whether we successfully saved
                        saved = False
                        
                        # only accept numeric YYYYMMDDHHMMSS style timestamps for now
                        if act_ts and gpsUtcDt and str(gpsUtcDt).isdigit():
                            try:
                                if int(str(gpsUtcDt)) > int(str(act_ts)):
                                    if lat is not None and lon is not None:
                                        await self._async_save_position(lat, lon, gpsUtcDt=gpsUtcDt, locationType=None, last_seen=state.attributes.get("last_seen"), reason="start")
                                        saved = True
                            except Exception:
                                # parsing/comparison issues -> ignore
                                pass
                        
                        # If we didn't save (GPS missing, not numeric, or not newer), set awaiting flag
                        if not saved:
                            self._awaiting_activation_save = True
                            self._activation_time_str = act_ts
                            _LOGGER.debug("Awaiting fresh GPS after activation: activation_time=%s device=%s gpsUtcDt=%s", act_ts, device_entity, gpsUtcDt)
                            # Notify sensor immediately to show awaiting_position state
                            try:
                                from homeassistant.helpers.dispatcher import async_dispatcher_send
                                async_dispatcher_send(self.hass, f"{DOMAIN}_{self.entry_id}_update")
                            except (AttributeError, KeyError, ImportError):
                                pass
                    except Exception:
                        # suppress any exceptions from this best-effort save
                        _LOGGER.exception("Error while attempting save-on-activation")

    async def async_handle_action(self, action: str, data: dict[str, Any] | None = None) -> None:
        """Handle a notification action from mobile app."""
        action = normalize_notification_action(action)
        if action == "DISABLE_ALARM":
            await self.set_alarm_active(False)
            _LOGGER.info("Alarm disabled via notification action")
            # optional: notify user ack
            if self.notifier:
                try:
                    from .utils import translate

                    title = await translate(self.hass, "messages.alarm_disabled", "Alarm disabled via notification")
                    notif_title = await translate(self.hass, "messages.vehicle_tracker_title", "Vehicle Tracker")
                except Exception:
                    title = "Alarm disabled via notification"
                    notif_title = "Vehicle Tracker"
                await self.hass.services.async_call(
                    "notify",
                    self.notifier,
                    {"message": title, "title": notif_title},
                )
        elif action == "OPEN_MAP":
            # send map link as notification
            if self.saved_latitude is not None and self.saved_longitude is not None and self.notifier:
                url = format_map_url(self.saved_latitude, self.saved_longitude)
                try:
                    from .utils import translate

                    notif_title = await translate(self.hass, "messages.open_map_title", "Open map")
                except Exception:
                    notif_title = "Open map"
                await self.hass.services.async_call(
                    "notify",
                    self.notifier,
                    {"message": url, "title": notif_title},
                )
        else:
            if self.debug_mode:
                _LOGGER.debug("Unknown notification action received: %s", action)

    async def _async_save_position(
        self, 
        lat: float, 
        lon: float, 
        gpsUtcDt: str | None = None, 
        locationType: str | None = None, 
        last_seen: str | None = None,
        reason: str = "save"  # "save", "start", "disconnect", "stationary"
    ):
        """Save the parking position and optional metadata.
        
        Args:
            lat: Latitude (will be converted to float)
            lon: Longitude (will be converted to float)
            gpsUtcDt: GPS UTC timestamp
            locationType: Type of location (gps, network, etc.)
            last_seen: Last seen timestamp
            reason: Why the position is being saved (affects notification message)
        """
        # Ensure coordinates are floats (they might come as strings from parsers)
        try:
            self.saved_latitude = float(lat)
            self.saved_longitude = float(lon)
        except (ValueError, TypeError) as e:
            _LOGGER.error("Invalid coordinates: lat=%s, lon=%s - %s", lat, lon, e)
            return
            
        if gpsUtcDt:
            try:
                self.saved_gpsUtcDt = str(gpsUtcDt)
            except Exception:
                self.saved_gpsUtcDt = None
        if locationType:
            try:
                self.saved_location_type = str(locationType)
            except Exception:
                self.saved_location_type = None
        if last_seen:
            try:
                self.saved_last_seen = str(last_seen)
            except Exception:
                self.saved_last_seen = None

        self.position_notified = False
        await self.async_save()
        _LOGGER.info("Saved parking position: %s,%s (reason=%s, gpsUtcDt=%s)", 
                     self.saved_latitude, self.saved_longitude, reason, self.saved_gpsUtcDt)
        
        # If this is a start-related save, clear the awaiting flag
        if reason == "start":
            self._awaiting_activation_save = False
        
        # Notify UI immediately to update state
        try:
            from homeassistant.helpers.dispatcher import async_dispatcher_send
            async_dispatcher_send(self.hass, f"{DOMAIN}_{self.entry_id}_update")
        except (AttributeError, KeyError, ImportError):
            # hass.data not available (e.g., in unit tests with FakeHass)
            pass
        
        # Send notification based on reason
        # Only send for "save" and "start" - NOT for disconnect/stationary (those are automatic)
        if self.notifier and reason in ("save", "start"):
            try:
                service_name = self.notifier.replace("notify.", "") if self.notifier.startswith("notify.") else self.notifier
                
                # Build message based on reason
                if reason == "start":
                    title = "🟢 Monitoraggio attivato"
                    message = f"Allarme attivo. Monitoraggio posizione corrente.\n📍 https://maps.google.com/?q={lat},{lon}"
                else:  # reason == "save"
                    title = "📍 Posizione salvata"
                    message = f"Posizione parcheggio memorizzata.\n📍 https://maps.google.com/?q={lat},{lon}"
                
                _LOGGER.debug("Sending notification: reason=%s, service=%s", reason, service_name)
                
                await self.hass.services.async_call(
                    "notify",
                    service_name,
                    {"title": title, "message": message},
                )
                _LOGGER.info("Sent '%s' notification via notify.%s", reason, service_name)
                    
            except Exception as e:
                _LOGGER.warning("Failed to send notification: %s", e, exc_info=True)

    def has_moved(self, lat: float, lon: float, tolerance_m: float) -> bool:
        """Check if current position has moved beyond tolerance from saved position.
        
        Returns:
            False if no saved position (cannot determine movement, don't send false alarms)
            False if within tolerance
            True if beyond tolerance
        """
        if self.saved_latitude is None or self.saved_longitude is None:
            # Cannot determine movement without saved position
            # Better to avoid false alarms - return False
            return False
        dist = haversine_distance(self.saved_latitude, self.saved_longitude, lat, lon)
        return dist > float(tolerance_m)

    async def _stationary_check(self, lat: float, lon: float) -> None:
        """Called after stationary_minutes to verify position remained the same and save it."""
        # get current tracker coords
        # this method will only save if coordinates didn't change significantly
        # fetch latest from device tracker entity if available in config
        device_entity = self.config.get("device_tracker")
        if not device_entity:
            return
        state = self.hass.states.get(device_entity)
        if not state:
            return
        current_lat = state.attributes.get("latitude")
        current_lon = state.attributes.get("longitude")
        if current_lat is None or current_lon is None:
            return
        try:
            current_lat = float(current_lat)
            current_lon = float(current_lon)
        except Exception:
            return

        # if the coords didn't change beyond tolerance_radius (meters), consider save
        try:
            dist = haversine_distance(lat, lon, current_lat, current_lon)
        except Exception:
            return
        if dist <= float(self.tolerance_radius):
            # In 'position' mode optionally require stationary_count threshold
            if self.activation_mode == "position" and int(getattr(self, "stationary_count", 0)) > 0:
                if int(getattr(self, "_stationary_counter", 0)) < int(self.stationary_count):
                    # not enough repeated reports yet
                    if self.debug_mode:
                        _LOGGER.debug("Stationary counter %s below required %s, skipping save", self._stationary_counter, self.stationary_count)
                    return

            # if candidate provided a gpsUtcDt and we recorded a start UTC, ensure gps is newer
            try:
                candidate_gps = getattr(self, "_stationary_candidate_gpsUtcDt", None)
                start_utc = getattr(self, "_stationary_start_utc", None)
                if candidate_gps and start_utc:
                    # compare as integers if possible (format YYYYMMDDHHMMSS)
                    try:
                        if int(str(candidate_gps)) <= int(str(start_utc)):
                            if self.debug_mode:
                                _LOGGER.debug("Candidate gpsUtcDt %s is not newer than start %s; skipping save", candidate_gps, start_utc)
                            return
                    except Exception:
                        # non-numeric gpsUtcDt: fall back to saving
                        pass
            except Exception:
                pass

            # collect metadata from the last known device attrs if available
            try:
                device_entity = self.config.get("device_tracker")
                state = self.hass.states.get(device_entity) if device_entity else None
                last_seen = None
                locationType = None
                gpsUtcDt = None
                if state:
                    last_seen = state.attributes.get("last_seen")
                    # try to pull locationType/gpsUtcDt from the state's ops if present
                    ops = state.attributes.get("ops") or []
                    if isinstance(ops, str):
                        import json

                        try:
                            ops = json.loads(ops)
                        except Exception:
                            ops = []
                    if isinstance(ops, (list, tuple)) and len(ops) > 0:
                        last_op = ops[0] or {}
                        gpsUtcDt = last_op.get("extra", {}).get("gpsUtcDt") or last_op.get("gpsUtcDt")
                        locationType = last_op.get("extra", {}).get("locationType") or last_op.get("locationType")
                await self._async_save_position(current_lat, current_lon, gpsUtcDt=gpsUtcDt, locationType=locationType, last_seen=last_seen, reason="stationary")
            except Exception:
                # ensure we don't crash the timer callback
                _LOGGER.exception("Error while finalizing stationary save")

    async def _notify_movement(self, lat: float, lon: float) -> None:
        """Notify configured notifier that the vehicle moved from saved position."""
        if not self.notifier:
            _LOGGER.info("Movement detected but no notifier configured: %s,%s", lat, lon)
            return

        # Calculate distance from saved position
        distance = 0
        if self.saved_latitude and self.saved_longitude:
            distance = haversine_distance(self.saved_latitude, self.saved_longitude, lat, lon)
        
        service_name = self.notifier.replace("notify.", "") if self.notifier.startswith("notify.") else self.notifier
        
        title = "🚨 Veicolo in movimento!"
        message = (
            f"⚠️ Rilevato spostamento di {distance:.0f}m dalla posizione salvata!\n\n"
            f"📍 Posizione salvata:\n"
            f"https://maps.google.com/?q={self.saved_latitude},{self.saved_longitude}\n\n"
            f"📍 Posizione attuale:\n"
            f"https://maps.google.com/?q={lat},{lon}"
        )
        
        _LOGGER.info("Sending movement alert: distance=%.0fm", distance)
        
        try:
            await self.hass.services.async_call(
                "notify", 
                service_name, 
                {"title": title, "message": message}
            )
            _LOGGER.info("Sent movement notification via notify.%s", service_name)
        except Exception as e:
            _LOGGER.warning("Failed to send movement notification: %s", e, exc_info=True)
