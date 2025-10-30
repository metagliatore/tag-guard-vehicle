"""Services and webhook handler for the integration."""
from __future__ import annotations

import logging
from typing import Any

try:
    from homeassistant.core import HomeAssistant, ServiceCall
    from homeassistant.helpers import aiohttp_client
except Exception:  # pragma: no cover - fallback for test environment without HA
    HomeAssistant = object
    ServiceCall = object
    aiohttp_client = None

from aiohttp import web

_LOGGER = logging.getLogger(__name__)


def validate_and_extract_coords(coordinator: Any, hass: Any, device_tracker_entity: str, data: dict, allow_payload_coords: bool = True):
    """Extract coordinates from payload or device_tracker.

    By default this will accept coordinates present in `data` (latitude/longitude).
    When `allow_payload_coords` is False the function will ignore coordinates in
    the payload and only attempt to read them from the configured device_tracker
    (this is used for webhook-triggered saves to avoid accepting remote coords).

    Returns tuple (ok: bool, status: str, lat, lon, http_status:int).
    """
    lat = None
    lon = None
    if allow_payload_coords:
        lat = data.get("latitude")
        lon = data.get("longitude")

    # fallback to current tracker if payload missing coords or payload coords disallowed
    if lat is None or lon is None:
        state = hass.states.get(device_tracker_entity)
        if state:
            lat = state.attributes.get("latitude")
            lon = state.attributes.get("longitude")

    if lat is None or lon is None:
        return False, "no_coords", None, None, 400

    return True, "ok", lat, lon, 200


async def handle_webhook_impl(hass: Any, coordinator: Any, device_tracker_entity: str, request: web.Request) -> web.Response:
    """Implementation of webhook handler extracted for easier testing.

    Behavior:
    - POST: expects JSON payload; action may be present in JSON.
    - GET: returns a small HTML control page with buttons to POST actions.
    - Actions supported: start, stop, mute, unmute, save.
    - Token may be provided via header 'X-Integration-Token' or query param 'token'.
    
    Action 'start' accepts optional parameter:
    - notify_waiting (bool): Send notification if waiting for fresh GPS position
      Example: {"action": "start", "notify_waiting": true}
    
    NOTE: coordinator parameter may be stale if integration was reloaded.
    We try to fetch the latest coordinator from hass.data if available.
    """
    _LOGGER.info("Webhook handler called - method=%s, path=%s, coordinator_id=%s", 
                 getattr(request, "method", "UNKNOWN"), getattr(request, "path", "UNKNOWN"), id(coordinator))
    
    # NOTE: coordinator is already fetched dynamically by the wrapper handle_webhook()
    # based on webhook_id -> entry_id mapping. Do NOT override it here!
    
    # read JSON payload for POST, otherwise use empty dict (GET shows control page)
    data = {}
    method = getattr(request, "method", "POST")
    if method != "POST":
        # show control HTML page for browser GET
        try:
            from .utils import translate

            title = await translate(hass, "messages.control_title", "Tag Guard Vehicle — Control")
            description = await translate(
                hass,
                "messages.control_description",
                "Use the buttons below to control the guard. The token is already in the webhook URL.",
            )
            start_label = await translate(hass, "messages.start_button", "Start (enable)")
            stop_label = await translate(hass, "messages.stop_button", "Stop (disable)")
            save_label = await translate(hass, "messages.save_button", "Trigger save now")
        except Exception:
            title = "Tag Guard Vehicle"
            description = "Use the buttons below to control the guard. The token is already in the webhook URL."
            start_label = "Start (enable)"
            stop_label = "Stop (disable)"
            save_label = "Trigger save now"

        tpl = """
        <!doctype html>
        <html>
        <head><meta charset="utf-8"><title>{title}</title></head>
        <body>
            <h3>{title}</h3>
            <p>{description}</p>
            <button id="start">{start_label}</button>
            <button id="stop">{stop_label}</button>
            <button id="save">{save_label}</button>
            <pre id="out"></pre>
            <script>
                const out = document.getElementById('out');
                async function postAction(action){{
                    const headers = {{'Content-Type':'application/json'}};
                    try{{
                        const resp = await fetch(window.location.href, {{method:'POST', headers, body: JSON.stringify({{action}})}});
                        const j = await resp.json();
                        out.textContent = JSON.stringify(j, null, 2);
                    }}catch(e){{ out.textContent = e; }}
                }}
                document.getElementById('start').onclick = ()=>postAction('start');
                document.getElementById('stop').onclick = ()=>postAction('disarm');
                document.getElementById('save').onclick = ()=>postAction('save');
            </script>
        </body>
        </html>
        """
        html = tpl.format(title=title, description=description, start_label=start_label, stop_label=stop_label, save_label=save_label)
        return web.Response(text=html, content_type="text/html")

    # POST: attempt to parse JSON payload
    try:
        data = await request.json()
    except Exception:
        data = {}

    # Get action from JSON body only (not from query string)
    action = data.get("action") if isinstance(data, dict) else None
    if action:
        a = str(action).strip().lower()
        _LOGGER.info("Webhook received action: %s (coordinator id: %s)", a, id(coordinator))

        if a == "start":
            # Enable alarm monitoring
            # Extract optional notify_waiting parameter from JSON payload
            try:
                notify_waiting = data.get("notify_waiting", False) if isinstance(data, dict) else False
                # Convert string "true"/"false" to boolean if needed
                if isinstance(notify_waiting, str):
                    notify_waiting = notify_waiting.lower() in ("true", "1", "yes")
                
                _LOGGER.info("Processing START action - setting alarm_active=True, notify_waiting=%s, coordinator_id=%s", 
                            notify_waiting, id(coordinator))
                await coordinator.set_alarm_active(True, notify_waiting=notify_waiting)
                _LOGGER.info("START action completed - alarm_active=%s, coordinator_id=%s", 
                            coordinator.alarm_active, id(coordinator))
                return web.json_response({"status": "started", "alarm_active": True, "notify_waiting": notify_waiting}, status=200)
            except Exception:
                _LOGGER.exception("Failed to enable alarm via webhook action")
                return web.json_response({"status": "error"}, status=500)

        if a == "mute":
            # Silence notifications but keep alarm active and monitoring
            try:
                _LOGGER.info("Processing MUTE action - setting position_notified=True")
                coordinator.position_notified = True
                await coordinator.async_save()
                _LOGGER.info("MUTE action completed - position_notified=%s", coordinator.position_notified)
                return web.json_response({
                    "status": "muted", 
                    "alarm_active": coordinator.alarm_active,
                    "position_notified": True,
                    "message": "Notifications muted. Alarm still monitoring."
                }, status=200)
            except Exception:
                _LOGGER.exception("Failed to mute notifications via webhook action")
                return web.json_response({"status": "error"}, status=500)

        if a == "stop":
            # Completely disable alarm monitoring
            try:
                _LOGGER.info("Processing STOP action - setting alarm_active=False")
                await coordinator.set_alarm_active(False)
                _LOGGER.info("STOP action completed - alarm_active=%s", coordinator.alarm_active)
                return web.json_response({
                    "status": "stopped", 
                    "alarm_active": False,
                    "message": "Alarm disabled. Monitoring stopped."
                }, status=200)
            except Exception:
                _LOGGER.exception("Failed to disable alarm via webhook action")
                return web.json_response({"status": "error"}, status=500)

        if a == "unmute":
            # Re-enable notifications (reset position_notified flag)
            try:
                _LOGGER.info("Processing UNMUTE action - setting position_notified=False")
                coordinator.position_notified = False
                await coordinator.async_save()
                _LOGGER.info("UNMUTE action completed - position_notified=%s", coordinator.position_notified)
                return web.json_response({
                    "status": "unmuted", 
                    "alarm_active": coordinator.alarm_active,
                    "position_notified": False,
                    "message": "Notifications re-enabled."
                }, status=200)
            except Exception:
                _LOGGER.exception("Failed to unmute notifications via webhook action")
                return web.json_response({"status": "error"}, status=500)

        if a == "save":
            # Save current position from device_tracker
            try:
                _LOGGER.info("Processing SAVE action - extracting coordinates from device_tracker")
                ok, status, lat, lon, http_status = validate_and_extract_coords(
                    coordinator, hass, device_tracker_entity, {}, allow_payload_coords=False
                )
                if not ok:
                    _LOGGER.warning("SAVE action failed - could not extract coordinates: %s", status)
                    return web.json_response({"status": status}, status=http_status)
                lat_f = float(lat)
                lon_f = float(lon)
                await coordinator._async_save_position(lat_f, lon_f, reason="save")
                _LOGGER.info("SAVE action completed - saved position: lat=%s, lon=%s", lat_f, lon_f)
                return web.json_response({"status": "saved", "latitude": lat_f, "longitude": lon_f}, status=200)
            except Exception:
                _LOGGER.exception("Failed to save position via webhook action")
                return web.json_response({"status": "error"}, status=500)
    # If we reach here there was no explicit action provided
    return web.json_response(
        {"status": "no_action", "message": "Provide action: start|stop|mute|unmute|save"},
        status=400,
    )


async def process_mobile_action(hass: Any, data: dict):
    """Process a mobile_app_notification_action payload for all coordinators.
    
    Each coordinator will check if the action is meant for it (via entry_id suffix).
    """
    from .const import DOMAIN
    
    coordinators_dict = hass.data.get(DOMAIN, {}).get("coordinators", {})
    action = data.get("action")
    
    # Forward action to all coordinators - each will filter based on entry_id
    for entry_id, coordinator in coordinators_dict.items():
        if hasattr(coordinator, "async_handle_action"):
            await coordinator.async_handle_action(action, data)


def _get_entry_id(coordinator):
    """Safely get entry_id from coordinator for logging."""
    return getattr(coordinator, 'entry_id', 'unknown')


def _get_coordinators_for_call(hass, call, fallback_coordinator=None, fallback_device_tracker=None, fallback_notifier=None):
    """Get coordinators based on call data.
    
    Returns a list of tuples: [(coordinator, device_tracker, notifier), ...]
    If config_entry is specified, returns only that coordinator.
    Otherwise returns all coordinators.
    
    For backward compatibility with tests, if no coordinators are found in registry
    and fallback_coordinator is provided, returns that coordinator.
    """
    from .const import DOMAIN
    
    # Get coordinators dict, handling missing data gracefully for tests
    try:
        coordinators_dict = hass.data.get(DOMAIN, {}).get("coordinators", {})
    except (AttributeError, TypeError):
        # Fallback for test environments without proper hass.data structure
        coordinators_dict = {}
    
    # Check if a specific config_entry was requested
    config_entry_id = None
    if call and hasattr(call, 'data'):
        config_entry_id = call.data.get('config_entry')
    
    if config_entry_id:
        # Return specific coordinator
        coordinator = coordinators_dict.get(config_entry_id)
        if coordinator:
            # Get device_tracker and notifier from coordinator config
            device_tracker = coordinator.config.get("device_tracker")
            notifier = coordinator.config.get("notifier")
            return [(coordinator, device_tracker, notifier)]
        else:
            _LOGGER.warning("No coordinator found for config_entry: %s", config_entry_id)
            return []
    else:
        # Return all coordinators
        result = []
        for entry_id, coordinator in coordinators_dict.items():
            device_tracker = coordinator.config.get("device_tracker")
            notifier = coordinator.config.get("notifier")
            result.append((coordinator, device_tracker, notifier))
        
        # Fallback for test environments: if no coordinators found but fallback provided
        if not result and fallback_coordinator is not None:
            result = [(fallback_coordinator, fallback_device_tracker, fallback_notifier)]
        
        return result


async def async_register_services(hass, coordinator, device_tracker_entity: str, notifier: str):
    """Register services. Services are registered only once and support multiple instances."""
    
    # Check if services are already registered (for second+ instance)
    try:
        if hasattr(hass.services, 'has_service') and hass.services.has_service(DOMAIN, "save_position"):
            _LOGGER.debug("Services already registered, skipping re-registration")
            return
    except Exception:
        pass  # Fallback for test environments
    
    _LOGGER.info("Registering Tag Guard Vehicle services (multi-instance support)")
    
    async def async_save_position(call=None):
        # save current device_tracker coords for specified or all coordinators
        coordinators = _get_coordinators_for_call(hass, call, coordinator, device_tracker_entity, notifier)
        if not coordinators:
            _LOGGER.warning("No coordinators found to execute save_position")
            return
            
        for coord, dev_tracker, _ in coordinators:
            state = hass.states.get(dev_tracker)
            if state is None:
                _LOGGER.warning("Device tracker entity not found: %s", dev_tracker)
                continue
            lat = state.attributes.get("latitude")
            lon = state.attributes.get("longitude")
            if lat is None or lon is None:
                _LOGGER.warning("No coordinates available to save for %s", dev_tracker)
                continue
            await coord._async_save_position(lat, lon, reason="save")
            _LOGGER.info("Saved position for coordinator %s", _get_entry_id(coord))

    async def async_reset_flags(call=None):
        coordinators = _get_coordinators_for_call(hass, call, coordinator, device_tracker_entity, notifier)
        for coord, _, _ in coordinators:
            coord.position_notified = False
            await coord.async_save()
            _LOGGER.info("Reset flags for coordinator %s", _get_entry_id(coord))

    async def async_clear_persisted(call=None):
        """Clear persisted saved coordinates and alarm flag for coordinators."""
        coordinators = _get_coordinators_for_call(hass, call, coordinator, device_tracker_entity, notifier)
        for coord, _, _ in coordinators:
            try:
                coord.saved_latitude = None
                coord.saved_longitude = None
                coord.saved_gpsUtcDt = None
                coord.saved_location_type = None
                coord.saved_last_seen = None
                coord.position_notified = False
                coord.last_tag_state = None
                try:
                    coord.alarm_active = False
                except Exception:
                    pass
                await coord.async_save()
                _LOGGER.info("Cleared persisted data for coordinator %s", _get_entry_id(coord))
            except Exception:
                _LOGGER.exception("Failed to clear persisted data for coordinator %s", _get_entry_id(coord))

    async def async_mute_notifications(call=None):
        """Mute notifications but keep monitoring active."""
        coordinators = _get_coordinators_for_call(hass, call, coordinator, device_tracker_entity, notifier)
        for coord, _, _ in coordinators:
            coord.position_notified = True
            await coord.async_save()
            _LOGGER.info("Muted notifications for coordinator %s (alarm_active=%s)", 
                        _get_entry_id(coord), coord.alarm_active)

    async def async_unmute_notifications(call=None):
        """Re-enable notifications."""
        coordinators = _get_coordinators_for_call(hass, call, coordinator, device_tracker_entity, notifier)
        for coord, _, _ in coordinators:
            coord.position_notified = False
            await coord.async_save()
            _LOGGER.info("Unmuted notifications for coordinator %s (alarm_active=%s)", 
                        _get_entry_id(coord), coord.alarm_active)

    hass.services.async_register(DOMAIN, "save_position", async_save_position)
    hass.services.async_register(DOMAIN, "reset_flags", async_reset_flags)
    hass.services.async_register(DOMAIN, "clear_persisted", async_clear_persisted)
    hass.services.async_register(DOMAIN, "mute_notifications", async_mute_notifications)
    hass.services.async_register(DOMAIN, "unmute_notifications", async_unmute_notifications)


from .const import DEFAULT_WEBHOOK_ID, CONF_WEBHOOK_TOKEN, DOMAIN


async def async_register_webhook_and_listeners(hass, coordinator, device_tracker_entity: str, webhook_id: str = None):
    """Register a webhook to manually save position and listen for mobile app notification actions.

    The webhook_id parameter is the token that will be used in the URL path.
    Example: POST http://HA_IP:8123/api/webhook/{webhook_id}
    Body: {"action": "start"}
    """

    from homeassistant.components import webhook

    # If no webhook_id provided, try to get it from coordinator's config
    if not webhook_id:
        # Get token from coordinator config (it should be in options)
        options = coordinator.config.get("options") or {}
        webhook_id = options.get(CONF_WEBHOOK_TOKEN) or coordinator.config.get(CONF_WEBHOOK_TOKEN) or DEFAULT_WEBHOOK_ID
        
        # Debug logging to understand where token comes from
        _LOGGER.info("Webhook token lookup: options=%s, config_keys=%s", 
                     {CONF_WEBHOOK_TOKEN: options.get(CONF_WEBHOOK_TOKEN)},
                     list(coordinator.config.keys()))
        if CONF_WEBHOOK_TOKEN in coordinator.config:
            _LOGGER.info("Found webhook_token in coordinator.config: %s", coordinator.config.get(CONF_WEBHOOK_TOKEN))
        if "options" in coordinator.config and CONF_WEBHOOK_TOKEN in coordinator.config["options"]:
            _LOGGER.info("Found webhook_token in coordinator.config['options']: %s", 
                        coordinator.config["options"].get(CONF_WEBHOOK_TOKEN))

    _LOGGER.info("Registering webhook with ID: %s for coordinator %s", webhook_id, _get_entry_id(coordinator))
    
    # Store webhook_id -> entry_id mapping in hass.data for dynamic lookup
    if "_webhook_to_entry" not in hass.data[DOMAIN]:
        hass.data[DOMAIN]["_webhook_to_entry"] = {}
    
    # Check if webhook_id is already mapped to a different entry_id
    existing_entry_id = hass.data[DOMAIN]["_webhook_to_entry"].get(webhook_id)
    if existing_entry_id and existing_entry_id != coordinator.entry_id:
        _LOGGER.warning(
            "Webhook ID '%s' is already mapped to entry_id '%s', now mapping to '%s'. "
            "This indicates duplicate webhook tokens!",
            webhook_id, existing_entry_id, coordinator.entry_id
        )
    
    hass.data[DOMAIN]["_webhook_to_entry"][webhook_id] = coordinator.entry_id
    _LOGGER.debug("Webhook mapping updated: %s -> %s", webhook_id, coordinator.entry_id)

    # Handler signature must match: async def handler(hass, webhook_id, request)
    # HA will call it with these 3 parameters
    # IMPORTANT: Do NOT capture coordinator in closure - fetch dynamically by webhook_id
    async def handle_webhook(hass_instance: Any, webhook_id_param: str, request: web.Request) -> web.Response:
        # Look up the coordinator for this webhook_id
        webhook_to_entry = hass.data.get(DOMAIN, {}).get("_webhook_to_entry", {})
        entry_id = webhook_to_entry.get(webhook_id_param)
        
        _LOGGER.info("Webhook called: webhook_id=%s, mapped_entry_id=%s", webhook_id_param, entry_id)
        _LOGGER.debug("All webhook mappings: %s", webhook_to_entry)
        
        if not entry_id:
            _LOGGER.error("No entry_id found for webhook_id: %s", webhook_id_param)
            return web.json_response({"error": "Unknown webhook"}, status=404)
        
        coordinators_dict = hass.data.get(DOMAIN, {}).get("coordinators", {})
        coord = coordinators_dict.get(entry_id)
        
        if not coord:
            _LOGGER.error("No coordinator found for entry_id: %s (webhook_id: %s)", entry_id, webhook_id_param)
            return web.json_response({"error": "Coordinator not found"}, status=404)
        
        # Get device_tracker from coordinator config
        dev_tracker = coord.config.get("device_tracker")
        
        _LOGGER.info("Webhook routing to coordinator: entry_id=%s, device_tracker=%s", entry_id, dev_tracker)
        
        return await handle_webhook_impl(hass, coord, dev_tracker, request)

    # HA webhook.async_register signature: (hass, domain, name, webhook_id, handler)
    try:
        webhook.async_register(
            hass,
            DOMAIN,
            "Tag Guard Vehicle",
            webhook_id,
            handle_webhook,
        )
        _LOGGER.info("Webhook successfully registered at: /api/webhook/%s for coordinator %s", 
                    webhook_id, _get_entry_id(coordinator))
        
        # Register global mobile app notification action listener (only once for all instances)
        # Check if already registered
        if "_mobile_action_listener" not in hass.data[DOMAIN]:
            def _handle_action(event):
                data = event.data or {}
                # Forward to all coordinators via global processor
                hass.async_create_task(process_mobile_action(hass, data))

            # Store the unsubscribe function globally
            unsub_mobile_action = hass.bus.async_listen("mobile_app_notification_action", _handle_action)
            hass.data[DOMAIN]["_mobile_action_listener"] = unsub_mobile_action
            _LOGGER.info("Registered global mobile_app_notification_action listener for all instances")
        else:
            _LOGGER.debug("Global mobile_app_notification_action listener already registered")
        
    except ValueError as e:
        # Webhook ID already registered - this should not happen if validation worked
        error_msg = f"Webhook token '{webhook_id}' is already in use. This webhook ID is already registered in Home Assistant."
        _LOGGER.error(error_msg)
        raise ValueError(error_msg) from e
    except Exception as e:
        # Unexpected error during webhook registration
        error_msg = f"Failed to register webhook '{webhook_id}': {str(e)}"
        _LOGGER.error(error_msg)
        raise RuntimeError(error_msg) from e


async def async_register_helper_services(hass, coordinator, entry_id: str, token):
    """Register helper services: get_webhook_info and toggle_alarm.
    
    These services are registered only once and support multiple instances via config_entry parameter.
    """
    
    # Check if services are already registered (for second+ instance)
    try:
        if hasattr(hass.services, 'has_service') and hass.services.has_service(DOMAIN, "start"):
            _LOGGER.debug("Helper services already registered, skipping re-registration")
            return
    except Exception:
        pass  # Fallback for test environments
    
    _LOGGER.info("Registering Tag Guard Vehicle helper services (multi-instance support)")

    async def get_webhook_info(call=None):
        # Get specific coordinator based on config_entry parameter
        config_entry_id = None
        if call and hasattr(call, 'data'):
            config_entry_id = call.data.get('config_entry')
        
        if config_entry_id:
            # Specific coordinator requested
            coordinators_dict = hass.data.get(DOMAIN, {}).get("coordinators", {})
            coord = coordinators_dict.get(config_entry_id)
            
            if not coord:
                _LOGGER.warning("No coordinator found for config_entry: %s", config_entry_id)
                return {"error": f"No coordinator found for {config_entry_id}"}
            
            # Get token from coordinator config
            options = coord.config.get("options") or {}
            coord_token = options.get(CONF_WEBHOOK_TOKEN) or coord.config.get(CONF_WEBHOOK_TOKEN) or DEFAULT_WEBHOOK_ID
            
            webhook_id = coord_token
            webhook_url = f"/api/webhook/{webhook_id}"
            info = {"webhook_url": webhook_url, "webhook_id": webhook_id, "token": coord_token, "config_entry": config_entry_id}
            _LOGGER.info("Webhook info for %s: %s", config_entry_id, info)
            return info
        else:
            # Fallback: use coordinator and token passed to function (for backward compatibility with tests)
            webhook_id = token or DEFAULT_WEBHOOK_ID
            webhook_url = f"/api/webhook/{webhook_id}"
            info = {"webhook_url": webhook_url, "webhook_id": webhook_id, "token": token, "config_entry": entry_id}
            _LOGGER.info("Webhook info (fallback): %s", info)
            return info

    async def start_alarm(call=None):
        """Start/enable the parking guard alarm monitoring.
        
        Accepts optional 'notify_waiting' parameter (bool) to send user notification
        if we're waiting for fresh GPS position.
        
        Example:
            service: tag_guard_vehicle.start
            data:
              config_entry: "01234567890abcdef"
              notify_waiting: true
        """
        # For helper services, use the coordinator passed as parameter as fallback
        coordinators = _get_coordinators_for_call(hass, call, coordinator, None, None)
        if not coordinators:
            _LOGGER.warning("No coordinators found to execute start")
            return
        
        # Extract notify_waiting from call data
        notify_waiting = False
        if call and hasattr(call, 'data'):
            notify_waiting = call.data.get('notify_waiting', False)
        
        for coord, _, _ in coordinators:
            await coord.set_alarm_active(True, notify_waiting=notify_waiting)
            _LOGGER.info("Started alarm for %s (alarm_active=True, notify_waiting=%s)", 
                        _get_entry_id(coord), notify_waiting)
        
        return {"status": "ok", "alarm_active": True}
    
    async def stop_alarm(call=None):
        """Stop/disable the parking guard alarm monitoring."""
        coordinators = _get_coordinators_for_call(hass, call, coordinator, None, None)
        if not coordinators:
            _LOGGER.warning("No coordinators found to execute stop")
            return
        
        for coord, _, _ in coordinators:
            await coord.set_alarm_active(False)
            _LOGGER.info("Stopped alarm for %s (alarm_active=False)", _get_entry_id(coord))
        
        return {"status": "ok", "alarm_active": False}
    
    async def toggle_alarm(call=None):
        """Toggle the alarm state (kept for backward compatibility)."""
        coordinators = _get_coordinators_for_call(hass, call, coordinator, None, None)
        if not coordinators:
            _LOGGER.warning("No coordinators found to execute toggle_alarm")
            return
        
        for coord, _, _ in coordinators:
            new_state = not bool(coord.alarm_active)
            await coord.set_alarm_active(new_state)
            _LOGGER.info("Toggled alarm for %s to %s", _get_entry_id(coord), new_state)

    hass.services.async_register(DOMAIN, "get_webhook_info", get_webhook_info)
    hass.services.async_register(DOMAIN, "start", start_alarm)
    hass.services.async_register(DOMAIN, "stop", stop_alarm)
    hass.services.async_register(DOMAIN, "toggle_alarm", toggle_alarm)  # backward compatibility
    
    # Register debug service
    async def debug_multi_instance(call=None):
        """Debug service to inspect multi-instance state."""
        coordinators_dict = hass.data.get(DOMAIN, {}).get("coordinators", {})
        webhook_to_entry = hass.data.get(DOMAIN, {}).get("_webhook_to_entry", {})
        
        _LOGGER.info("=== MULTI-INSTANCE DEBUG ===")
        _LOGGER.info("Total coordinators: %d", len(coordinators_dict))
        _LOGGER.info("Coordinators: %s", list(coordinators_dict.keys()))
        _LOGGER.info("Webhook mappings: %s", webhook_to_entry)
        
        for entry_id, coord in coordinators_dict.items():
            device_tracker = coord.config.get("device_tracker")
            options = coord.config.get("options") or {}
            webhook_token = options.get(CONF_WEBHOOK_TOKEN) or coord.config.get(CONF_WEBHOOK_TOKEN)
            _LOGGER.info(
                "  Entry %s: device_tracker=%s, webhook_token=%s, alarm_active=%s",
                entry_id, device_tracker, webhook_token, coord.alarm_active
            )
        
        # Check reverse mapping
        _LOGGER.info("Reverse check (webhook -> entry):")
        for webhook_id, entry_id in webhook_to_entry.items():
            if entry_id in coordinators_dict:
                _LOGGER.info("  Webhook '%s' -> Entry '%s' [OK]", webhook_id, entry_id)
            else:
                _LOGGER.warning("  Webhook '%s' -> Entry '%s' [MISSING COORDINATOR!]", webhook_id, entry_id)
        
        return {
            "coordinators": list(coordinators_dict.keys()),
            "webhook_mappings": webhook_to_entry,
            "status": "ok"
        }
    
    # Register cleanup service
    async def cleanup_webhooks(call=None):
        coordinators = _get_coordinators_for_call(hass, call, coordinator, None, None)
        if not coordinators:
            # If no specific coordinator, cleanup all
            try:
                coordinators_dict = hass.data.get(DOMAIN, {}).get("coordinators", {})
                coordinators = [(coord, None, None) for coord in coordinators_dict.values()]
            except (AttributeError, TypeError):
                coordinators = [(coordinator, None, None)] if coordinator else []
        
        for coord, _, _ in coordinators:
            await async_cleanup_old_webhooks(hass, coord)
            _LOGGER.info("Cleaned up webhooks for coordinator %s", _get_entry_id(coord))
    
    async def list_webhooks(call=None):
        """List all registered webhooks in Home Assistant."""
        from homeassistant.components import webhook
        
        try:
            # Try different ways to access the webhook registry depending on HA version
            webhook_ids = []
            
            # Method 1: Try hass.data["webhook"]._handlers (older versions)
            if "webhook" in hass.data and hasattr(hass.data["webhook"], "_handlers"):
                handlers = hass.data["webhook"]._handlers
                webhook_ids = list(handlers.keys())
                _LOGGER.info("Registered webhooks (%d total): %s", len(webhook_ids), webhook_ids)
            
            # Method 2: Try webhook component's async_active_webhooks (newer versions)
            elif hasattr(webhook, "async_active_webhooks"):
                webhook_ids = list(webhook.async_active_webhooks(hass))
                _LOGGER.info("Registered webhooks (%d total): %s", len(webhook_ids), webhook_ids)
            
            # Method 3: Just check if our webhook is callable
            else:
                _LOGGER.info("Cannot enumerate all webhooks, testing our webhook...")
                # Try to check if webhook exists by attempting to get info about it
                our_webhook_id = token or DEFAULT_WEBHOOK_ID
                _LOGGER.info("Our webhook should be registered at: /api/webhook/%s", our_webhook_id)
                return {"webhook_id": our_webhook_id, "webhook_url": f"/api/webhook/{our_webhook_id}"}
            
            if webhook_ids:
                # Filter our integration's webhooks
                our_webhooks = [wid for wid in webhook_ids if "vehicle" in wid.lower() or wid == token or wid == DEFAULT_WEBHOOK_ID]
                if our_webhooks:
                    _LOGGER.info("Tag Guard Vehicle webhooks: %s", our_webhooks)
                else:
                    _LOGGER.warning("No webhooks found for Tag Guard Vehicle in registered list!")
                
                return {"all_webhooks": webhook_ids, "our_webhooks": our_webhooks}
            else:
                _LOGGER.warning("Could not retrieve webhook list")
                return {"error": "Could not retrieve webhook list"}
                
        except Exception as e:
            _LOGGER.error("Error listing webhooks: %s", e, exc_info=True)
            return {"error": str(e)}
    
    hass.services.async_register(DOMAIN, "debug_multi_instance", debug_multi_instance)
    hass.services.async_register(DOMAIN, "cleanup_webhooks", cleanup_webhooks)
    hass.services.async_register(DOMAIN, "list_webhooks", list_webhooks)
    _LOGGER.info("Registered debug service: %s.debug_multi_instance", DOMAIN)
    _LOGGER.info("Registered cleanup service: %s.cleanup_webhooks", DOMAIN)
    _LOGGER.info("Registered list service: %s.list_webhooks", DOMAIN)


async def async_cleanup_old_webhooks(hass, coordinator):
    """Unregister old webhooks before registering new one.
    
    This is useful when switching from the old webhook ID system to the new token-based system.
    Call this service: tag_guard_vehicle.cleanup_webhooks
    """
    from homeassistant.components import webhook
    
    # List of potential old webhook IDs to clean up
    old_webhook_ids = [
        DEFAULT_WEBHOOK_ID,  # "vehicle-save-location" (old default)
    ]
    
    # Also try to get the current token from config to clean it up
    options = coordinator.config.get("options") or {}
    current_token = options.get(CONF_WEBHOOK_TOKEN) or coordinator.config.get(CONF_WEBHOOK_TOKEN)
    if current_token and current_token not in old_webhook_ids:
        old_webhook_ids.append(current_token)
    
    _LOGGER.info("Starting webhook cleanup for IDs: %s", old_webhook_ids)
    
    for webhook_id in old_webhook_ids:
        try:
            webhook.async_unregister(hass, webhook_id)
            _LOGGER.info("✓ Successfully unregistered webhook: %s", webhook_id)
        except Exception as e:
            _LOGGER.debug("Could not unregister webhook %s: %s (may not exist)", webhook_id, e)
    
    _LOGGER.info("Webhook cleanup completed. You can now reload the integration.")


async def _notify(hass, notifier, title: str, message: str):
    service = hass.services
    await hass.services.async_call("notify", notifier, {
        "title": title,
        "message": message
    })
