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
    - Actions supported: start, disarm, mute, unmute, save.
    - Token may be provided via header 'X-Integration-Token' or query param 'token'.
    
    NOTE: coordinator parameter may be stale if integration was reloaded.
    We try to fetch the latest coordinator from hass.data if available.
    """
    _LOGGER.info("Webhook handler called - method=%s, path=%s", getattr(request, "method", "UNKNOWN"), getattr(request, "path", "UNKNOWN"))
    
    # Try to get the latest coordinator from hass.data (in case integration was reloaded)
    from .const import DOMAIN
    if hasattr(hass, 'data') and DOMAIN in hass.data:
        # Find the first coordinator in hass.data[DOMAIN]
        for key, value in hass.data[DOMAIN].items():
            if key.endswith("_coordinator"):
                coordinator = value
                _LOGGER.debug("Using coordinator from hass.data: %s", key)
                break
    
    # read JSON payload for POST, otherwise use empty dict (GET shows control page)
    data = {}
    method = getattr(request, "method", "POST")
    if method != "POST":
        # show control HTML page for browser GET
        try:
            from .utils import translate

            title = await translate(hass, "messages.control_title", "Vehicle BT Parking Sentinel — Control")
            description = await translate(
                hass,
                "messages.control_description",
                "Use the buttons below to control the sentinel. The token is already in the webhook URL.",
            )
            start_label = await translate(hass, "messages.start_button", "Start (enable)")
            stop_label = await translate(hass, "messages.stop_button", "Stop (disable)")
            save_label = await translate(hass, "messages.save_button", "Trigger save now")
        except Exception:
            title = "Vehicle BT Parking Sentinel"
            description = "Use the buttons below to control the sentinel. The token is already in the webhook URL."
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
            try:
                _LOGGER.info("Processing START action - setting alarm_active=True")
                await coordinator.set_alarm_active(True)
                _LOGGER.info("START action completed - alarm_active=%s", coordinator.alarm_active)
                return web.json_response({"status": "started", "alarm_active": True}, status=200)
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

        if a == "disarm":
            # Completely disable alarm monitoring
            try:
                _LOGGER.info("Processing DISARM action - setting alarm_active=False")
                await coordinator.set_alarm_active(False)
                _LOGGER.info("DISARM action completed - alarm_active=%s", coordinator.alarm_active)
                return web.json_response({
                    "status": "disarmed", 
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
        {"status": "no_action", "message": "Provide action: start|disarm|mute|unmute|save"},
        status=400,
    )


async def process_mobile_action(coordinator: Any, data: dict):
    """Process a mobile_app_notification_action payload; delegated to coordinator."""
    action = data.get("action")
    # forward to coordinator's async handler if present
    if hasattr(coordinator, "async_handle_action"):
        await coordinator.async_handle_action(action, data)


async def async_register_services(hass, coordinator, device_tracker_entity: str, notifier: str):
    async def async_save_position(call=None):
        # save current device_tracker coords
        state = hass.states.get(device_tracker_entity)
        if state is None:
            _LOGGER.warning("Device tracker entity not found: %s", device_tracker_entity)
            return
        lat = state.attributes.get("latitude")
        lon = state.attributes.get("longitude")
        if lat is None or lon is None:
            _LOGGER.warning("No coordinates available to save")
            return
        await coordinator._async_save_position(lat, lon, reason="save")
        # Note: notification is now handled inside _async_save_position based on reason

    async def async_reset_flags(call=None):
        coordinator.position_notified = False
        await coordinator.async_save()

    async def async_clear_persisted(call=None):
        """Clear persisted saved coordinates and alarm flag for this coordinator."""
        try:
            coordinator.saved_latitude = None
            coordinator.saved_longitude = None
            coordinator.saved_gpsUtcDt = None
            coordinator.saved_location_type = None
            coordinator.saved_last_seen = None
            coordinator.position_notified = False
            coordinator.last_tag_state = None
            # reset alarm to False (user-level default for manual)
            try:
                coordinator.alarm_active = False
            except Exception:
                pass
            await coordinator.async_save()
        except Exception:
            _LOGGER.exception("Failed to clear persisted data for coordinator")

    async def async_manual_trigger(call):
        """Manual trigger: quick activation of monitoring (save current position + enable alarm).
        
        This service works in ALL activation modes, not just 'manual' mode. It provides
        a way to manually force a save and enable the alarm, regardless of the configured
        activation mode logic.
        
        The save respects the timestamp freshness check: if the current gpsUtcDt is
        newer than the activation time, the position is saved immediately. Otherwise,
        the coordinator sets _awaiting_activation_save and will save when a fresh
        GPS reading arrives.
        
        Does NOT accept custom coordinates in the payload.
        """
        from datetime import datetime
        activation_time = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        
        # Force a save attempt regardless of current alarm state
        # First, try to save if GPS is fresh
        device_entity = coordinator.config.get("device_tracker")
        saved = False
        
        if device_entity:
            state = hass.states.get(device_entity)
            if state:
                try:
                    from .utils import extract_coords_from_ops_attrs_by_model, safe_get
                    
                    ops = state.attributes.get("ops") or []
                    last_op = ops[0] if isinstance(ops, (list, tuple)) and len(ops) > 0 else {}
                    lat, lon = extract_coords_from_ops_attrs_by_model(coordinator.config.get("tag_model"), last_op, state.attributes)
                    gpsUtcDt = safe_get(last_op, "extra", "gpsUtcDt") or safe_get(last_op, "gpsUtcDt") or state.attributes.get("gpsUtcDt")
                    
                    # Check if GPS is fresh
                    if gpsUtcDt and str(gpsUtcDt).isdigit() and int(str(gpsUtcDt)) > int(str(activation_time)):
                        if lat is not None and lon is not None:
                            await coordinator._async_save_position(lat, lon, gpsUtcDt=gpsUtcDt, locationType=None, last_seen=state.attributes.get("last_seen"), reason="start")
                            saved = True
                except Exception:
                    _LOGGER.exception("Error while attempting save in manual_trigger")
        
        # Set awaiting flag if we didn't save
        if not saved:
            coordinator._awaiting_activation_save = True
            coordinator._activation_time_str = activation_time
            _LOGGER.debug("manual_trigger: awaiting fresh GPS (activation_time=%s)", activation_time)
        
        # Enable alarm (even if already enabled, this ensures it's on)
        coordinator.alarm_active = True
        await coordinator.async_save()
        
        # Notification is handled by _async_save_position (with reason="start") if GPS was saved
        # If we're still awaiting GPS, notify user to wait
        if getattr(coordinator, '_awaiting_activation_save', False) and notifier:
            try:
                from .utils import translate
                title = await translate(hass, "messages.manual_trigger_awaiting_title", "⏳ Parking sentinel activating...")
                message = await translate(hass, "messages.manual_trigger_awaiting_message", "Waiting for fresh GPS position to save parking location.")
                await _notify(hass, notifier, title, message)
            except Exception:
                await _notify(hass, notifier, "⏳ Parking sentinel", "Waiting for GPS position...")

    async def async_mute_notifications(call=None):
        """Mute notifications but keep monitoring active."""
        coordinator.position_notified = True
        await coordinator.async_save()
        _LOGGER.info("Notifications muted (position_notified=True, alarm_active=%s)", coordinator.alarm_active)

    async def async_unmute_notifications(call=None):
        """Re-enable notifications."""
        coordinator.position_notified = False
        await coordinator.async_save()
        _LOGGER.info("Notifications unmuted (position_notified=False, alarm_active=%s)", coordinator.alarm_active)

    hass.services.async_register("vehicle_bt_parking_sentinel", "save_position", async_save_position)
    hass.services.async_register("vehicle_bt_parking_sentinel", "reset_flags", async_reset_flags)
    hass.services.async_register("vehicle_bt_parking_sentinel", "manual_trigger", async_manual_trigger)
    hass.services.async_register("vehicle_bt_parking_sentinel", "clear_persisted", async_clear_persisted)
    hass.services.async_register("vehicle_bt_parking_sentinel", "mute_notifications", async_mute_notifications)
    hass.services.async_register("vehicle_bt_parking_sentinel", "unmute_notifications", async_unmute_notifications)


from .const import DEFAULT_WEBHOOK_ID, CONF_WEBHOOK_TOKEN


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

    _LOGGER.info("Registering webhook with ID: %s (token from config)", webhook_id)

    # Handler signature must match: async def handler(hass, webhook_id, request)
    # HA will call it with these 3 parameters
    async def handle_webhook(hass_instance: Any, webhook_id_param: str, request: web.Request) -> web.Response:
        return await handle_webhook_impl(hass, coordinator, device_tracker_entity, request)

    # HA webhook.async_register signature: (hass, domain, name, webhook_id, handler)
    try:
        webhook.async_register(
            hass,
            "vehicle_bt_parking_sentinel",
            "Vehicle BT Parking Sentinel",
            webhook_id,
            handle_webhook,
        )
        _LOGGER.info("Webhook successfully registered at: /api/webhook/%s", webhook_id)
        
        # listen for mobile app notification actions (only if webhook registration succeeded)
        def _handle_action(event):
            data = event.data or {}
            # schedule module-level processor
            hass.async_create_task(process_mobile_action(coordinator, data))

        hass.bus.async_listen("mobile_app_notification_action", _handle_action)
        _LOGGER.info("Registered mobile_app_notification_action listener")
        
    except ValueError:
        # Handler already defined (e.g., after reload); log and continue
        _LOGGER.info("Webhook handler for %s already registered, skipping registration", webhook_id)
        # NOTE: Mobile app listener is NOT re-registered to avoid duplicates


async def async_register_helper_services(hass, coordinator, entry_id: str, token):
    """Register helper services: get_webhook_info and toggle_alarm."""

    async def get_webhook_info(call=None):
        # return or log webhook url and token
        # The webhook URL now uses the token as the webhook ID
        webhook_id = token or DEFAULT_WEBHOOK_ID
        webhook_url = f"/api/webhook/{webhook_id}"
        info = {"webhook_url": webhook_url, "webhook_id": webhook_id, "token": token}
        _LOGGER.info("Webhook info: %s", info)
        return info

    async def start_alarm(call=None):
        """Start/enable the parking sentinel alarm monitoring."""
        await coordinator.set_alarm_active(True)
        _LOGGER.info("Started alarm for %s (alarm_active=True)", entry_id)
        return {"status": "ok", "alarm_active": True}
    
    async def stop_alarm(call=None):
        """Stop/disable the parking sentinel alarm monitoring."""
        await coordinator.set_alarm_active(False)
        _LOGGER.info("Stopped alarm for %s (alarm_active=False)", entry_id)
        return {"status": "ok", "alarm_active": False}
    
    async def toggle_alarm(call=None):
        """Toggle the alarm state (kept for backward compatibility)."""
        new_state = not bool(coordinator.alarm_active)
        await coordinator.set_alarm_active(new_state)
        _LOGGER.info("Toggled alarm for %s to %s", entry_id, new_state)
        return {"status": "ok", "alarm_active": new_state}

    hass.services.async_register("vehicle_bt_parking_sentinel", "get_webhook_info", get_webhook_info)
    hass.services.async_register("vehicle_bt_parking_sentinel", "start", start_alarm)
    hass.services.async_register("vehicle_bt_parking_sentinel", "stop", stop_alarm)
    hass.services.async_register("vehicle_bt_parking_sentinel", "toggle_alarm", toggle_alarm)  # backward compatibility
    
    # Register cleanup service
    async def cleanup_webhooks(call=None):
        await async_cleanup_old_webhooks(hass, coordinator)
    
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
                    _LOGGER.info("Vehicle BT Parking Sentinel webhooks: %s", our_webhooks)
                else:
                    _LOGGER.warning("No webhooks found for Vehicle BT Parking Sentinel in registered list!")
                
                return {"all_webhooks": webhook_ids, "our_webhooks": our_webhooks}
            else:
                _LOGGER.warning("Could not retrieve webhook list")
                return {"error": "Could not retrieve webhook list"}
                
        except Exception as e:
            _LOGGER.error("Error listing webhooks: %s", e, exc_info=True)
            return {"error": str(e)}
    
    hass.services.async_register("vehicle_bt_parking_sentinel", "cleanup_webhooks", cleanup_webhooks)
    hass.services.async_register("vehicle_bt_parking_sentinel", "list_webhooks", list_webhooks)
    _LOGGER.info("Registered cleanup service: vehicle_bt_parking_sentinel.cleanup_webhooks")
    _LOGGER.info("Registered list service: vehicle_bt_parking_sentinel.list_webhooks")


async def async_cleanup_old_webhooks(hass, coordinator):
    """Unregister old webhooks before registering new one.
    
    This is useful when switching from the old webhook ID system to the new token-based system.
    Call this service: vehicle_bt_parking_sentinel.cleanup_webhooks
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
