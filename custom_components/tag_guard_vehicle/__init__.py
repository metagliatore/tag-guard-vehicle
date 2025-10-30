"""The Tag Guard Vehicle integration."""
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Tag Guard Vehicle component."""
    _LOGGER.info("Setting up Tag Guard Vehicle")
    hass.data.setdefault(DOMAIN, {})
    # Initialize global coordinator registry for multi-instance support
    hass.data[DOMAIN].setdefault("coordinators", {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tag Guard Vehicle from a config entry."""
    _LOGGER.info("Setting up Tag Guard Vehicle from a config entry")
    hass.data[DOMAIN][entry.entry_id] = entry.data

    # Register static files from www directory (only once per HA session)
    if "_static_path_registered" not in hass.data[DOMAIN]:
        try:
            from homeassistant.components.http import StaticPathConfig
            import os
            
            www_path = os.path.join(os.path.dirname(__file__), "www")
            if os.path.exists(www_path):
                await hass.http.async_register_static_paths([
                    StaticPathConfig(
                        url_path=f"/{DOMAIN}",
                        path=www_path,
                        cache_headers=True
                    )
                ])
                _LOGGER.info("Registered static path: /%s -> %s", DOMAIN, www_path)
                hass.data[DOMAIN]["_static_path_registered"] = True
            else:
                _LOGGER.warning("www directory not found at: %s", www_path)
        except Exception as e:
            _LOGGER.warning("Failed to register static path: %s", e)

    # Register Lovelace resource for custom card (only once)
    if "_lovelace_resource_registered" not in hass.data[DOMAIN]:
        try:
            await _async_register_lovelace_resource(hass)
            hass.data[DOMAIN]["_lovelace_resource_registered"] = True
        except Exception as e:
            _LOGGER.warning("Failed to auto-register Lovelace resource: %s", e)

    # Initialize coordinator
    from .coordinator import VehicleCoordinator
    from .services import async_register_services

    # include options in the config passed to coordinator so it can apply them
    config = dict(entry.data)
    if entry.options:
        config["options"] = dict(entry.options)
    
    # Debug logging to see what config is being passed
    _LOGGER.info("Creating coordinator with config keys: %s", list(config.keys()))
    if "options" in config:
        _LOGGER.info("Options in config: %s", list(config["options"].keys()))
        if "webhook_token" in config["options"]:
            _LOGGER.info("webhook_token found in options: %s", config["options"]["webhook_token"])
    if "webhook_token" in config:
        _LOGGER.info("webhook_token found in config (data): %s", config["webhook_token"])
    
    coordinator = VehicleCoordinator(hass, entry.entry_id, config)
    await coordinator.async_load()
    
    # Initialize position from device_tracker if no saved position exists
    # This ensures we always have a reference position, but does NOT activate alarm
    device_tracker = entry.data.get("device_tracker")
    if device_tracker:
        await coordinator.async_initialize_position_if_needed(device_tracker)
    
    # Store coordinator in both legacy key and global registry
    hass.data[DOMAIN][entry.entry_id + "_coordinator"] = coordinator
    hass.data[DOMAIN]["coordinators"][entry.entry_id] = coordinator
    _LOGGER.info("Registered coordinator for entry_id: %s, coordinator_id=%s (total coordinators: %d)", 
                 entry.entry_id, id(coordinator), len(hass.data[DOMAIN]["coordinators"]))

    # start listening to the device tracker configured
    notifier = entry.data.get("notifier")
    await coordinator.async_start(device_tracker)

    # register services
    await async_register_services(hass, coordinator, device_tracker, notifier)
    
    # register webhook and mobile app action listeners
    from .services import async_register_webhook_and_listeners
    from homeassistant.exceptions import ConfigEntryNotReady
    
    try:
        await async_register_webhook_and_listeners(hass, coordinator, device_tracker)
    except ValueError as e:
        # Webhook already registered - clear error message
        _LOGGER.error("Failed to setup integration: %s", str(e))
        # Cleanup coordinator before failing
        await coordinator.async_stop()
        hass.data[DOMAIN].pop(entry.entry_id + "_coordinator", None)
        hass.data[DOMAIN]["coordinators"].pop(entry.entry_id, None)
        raise ConfigEntryNotReady(
            f"Webhook registration failed: {str(e)}. "
            "Please ensure the webhook token is unique across all instances."
        ) from e
    except Exception as e:
        # Unexpected error
        _LOGGER.error("Unexpected error during webhook registration: %s", str(e))
        # Cleanup coordinator before failing
        await coordinator.async_stop()
        hass.data[DOMAIN].pop(entry.entry_id + "_coordinator", None)
        hass.data[DOMAIN]["coordinators"].pop(entry.entry_id, None)
        raise ConfigEntryNotReady(
            f"Failed to register webhook: {str(e)}"
        ) from e

    # ensure webhook token is persisted in options and expose webhook info service
    options = dict(entry.options or {})
    token = options.get("webhook_token") or config.get("webhook_token")
    if not token:
        # nothing to persist (token should be created at config flow), but guard anyway
        token = None
    else:
        # ensure stored in options
        if options.get("webhook_token") != token:
            options["webhook_token"] = token
            # persist updated options
            hass.async_create_task(entry.async_update(options=options))

    # register small helper services
    from .services import async_register_helper_services
    await async_register_helper_services(hass, coordinator, entry.entry_id, token)

    # listen for options updates on the entry and apply them at runtime
    async def _entry_update_listener(updated_entry: ConfigEntry):
        new_options = updated_entry.options
        await coordinator.async_update_options(new_options)

    entry.add_update_listener(_entry_update_listener)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Tag Guard Vehicle config entry: %s", entry.entry_id)
    
    # Get coordinator before removing from hass.data
    coordinator_key = entry.entry_id + "_coordinator"
    coordinator = hass.data.get(DOMAIN, {}).get(coordinator_key)
    
    # Remove from global coordinator registry
    if entry.entry_id in hass.data.get(DOMAIN, {}).get("coordinators", {}):
        del hass.data[DOMAIN]["coordinators"][entry.entry_id]
        _LOGGER.info("Removed coordinator from registry for entry_id: %s", entry.entry_id)
    
    # Stop coordinator (unsubscribe from device_tracker events)
    if coordinator:
        _LOGGER.debug("Stopping coordinator for entry: %s", entry.entry_id)
        await coordinator.async_stop()
    
    # Unregister webhook
    from homeassistant.components import webhook
    from .const import CONF_WEBHOOK_TOKEN, DEFAULT_WEBHOOK_ID
    
    # Get webhook token from config
    options = entry.options or {}
    webhook_id = options.get(CONF_WEBHOOK_TOKEN) or entry.data.get(CONF_WEBHOOK_TOKEN) or DEFAULT_WEBHOOK_ID
    
    try:
        webhook.async_unregister(hass, webhook_id)
        _LOGGER.info("Unregistered webhook: %s", webhook_id)
        
        # Remove webhook->entry_id mapping
        if "_webhook_to_entry" in hass.data.get(DOMAIN, {}):
            hass.data[DOMAIN]["_webhook_to_entry"].pop(webhook_id, None)
            _LOGGER.debug("Removed webhook->entry mapping for: %s", webhook_id)
    except Exception as e:
        _LOGGER.debug("Could not unregister webhook %s: %s (may not exist)", webhook_id, e)
    
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    # Remove from hass.data
    if unload_ok:
        # Remove all data for this entry
        if DOMAIN in hass.data:
            hass.data[DOMAIN].pop(entry.entry_id, None)
            hass.data[DOMAIN].pop(coordinator_key, None)
            _LOGGER.debug("Removed entry data from hass.data: %s", entry.entry_id)
            
            # If no more coordinators, cleanup global mobile action listener
            if not hass.data[DOMAIN].get("coordinators"):
                if "_mobile_action_listener" in hass.data[DOMAIN]:
                    try:
                        hass.data[DOMAIN]["_mobile_action_listener"]()
                        del hass.data[DOMAIN]["_mobile_action_listener"]
                        _LOGGER.info("Unregistered global mobile_app_notification_action listener (no more instances)")
                    except Exception as e:
                        _LOGGER.debug("Could not unregister mobile action listener: %s", e)
            
            # If no more entries, clean up domain data
            if not hass.data[DOMAIN] or (len(hass.data[DOMAIN]) == 1 and "coordinators" in hass.data[DOMAIN] and not hass.data[DOMAIN]["coordinators"]):
                hass.data.pop(DOMAIN)
                _LOGGER.debug("Removed empty DOMAIN from hass.data")

    _LOGGER.info("Unload complete for entry: %s, success: %s", entry.entry_id, unload_ok)
    return unload_ok


async def async_get_options_flow(config_entry):
    from .options_flow import TagGuardVehicleOptionsFlowHandler

    return TagGuardVehicleOptionsFlowHandler(config_entry)


async def _async_register_lovelace_resource(hass: HomeAssistant) -> None:
    """Register the custom Lovelace card resource automatically.
    
    This registers the card JavaScript file so users don't need to manually
    add it via the Resources UI. The card will be available as:
    custom:tag-guard-vehicle-card
    """
    try:
        # Use the lovelace resources API to register the card
        from homeassistant.components.lovelace import resources
        
        # The path format for custom_components is:
        # /hacsfiles/<domain>/<file> or for local custom_components:
        # /<domain>/<file> when served from custom_components/<domain>/www/
        # Register frontend resource (Lovelace card)
        resource_url = f"/{DOMAIN}/tag-guard-vehicle-card.js"
        
        # Check if resource already registered
        # ResourceStorageCollection might not have .values() method in all HA versions
        # Try to iterate directly if possible
        if hasattr(hass.data.get("lovelace"), "resources"):
            try:
                existing = hass.data["lovelace"].resources
                # Try different ways to access resources depending on HA version
                if hasattr(existing, "async_items"):
                    # Newer HA versions
                    items = await existing.async_items()
                    if any(r.get("url") == resource_url for r in items):
                        _LOGGER.debug("Lovelace resource already registered: %s", resource_url)
                        return
                elif hasattr(existing, "data"):
                    # Some versions store in .data dict
                    if any(r.get("url") == resource_url for r in existing.data.values()):
                        _LOGGER.debug("Lovelace resource already registered: %s", resource_url)
                        return
            except Exception:
                # If checking fails, proceed to registration attempt
                pass
        
        # Register the resource using the ResourceStorageCollection API
        # Different HA versions have different APIs and different schema requirements
        # Use direct attribute access (not .get()) to avoid deprecation warning
        lovelace_data = hass.data.get("lovelace")
        if lovelace_data is not None and hasattr(lovelace_data, "resources"):
            lovelace_resources = lovelace_data.resources
            
            # Try to create resource - try different schemas as HA versions vary
            registered = False
            
            # Method 1: Try async_create_item (newer HA)
            if hasattr(lovelace_resources, "async_create_item"):
                # Try with "res_type" first (some HA versions use this even with async_create_item)
                try:
                    await lovelace_resources.async_create_item({
                        "url": resource_url,
                        "res_type": "module",
                    })
                    _LOGGER.info("Auto-registered Lovelace resource (async_create_item with res_type): %s", resource_url)
                    registered = True
                except Exception as e1:
                    # If that fails, try with "type" (other HA versions)
                    try:
                        await lovelace_resources.async_create_item({
                            "url": resource_url,
                            "type": "module",
                        })
                        _LOGGER.info("Auto-registered Lovelace resource (async_create_item with type): %s", resource_url)
                        registered = True
                    except Exception as e2:
                        _LOGGER.debug("Both async_create_item attempts failed: res_type=%s, type=%s", e1, e2)
            
            # Method 2: Try async_create (older HA)
            if not registered and hasattr(lovelace_resources, "async_create"):
                try:
                    await lovelace_resources.async_create({
                        "url": resource_url,
                        "res_type": "module",
                    })
                    _LOGGER.info("Auto-registered Lovelace resource (async_create): %s", resource_url)
                    registered = True
                except Exception as e:
                    _LOGGER.debug("async_create failed: %s", e)
            
            # If nothing worked, log manual instructions
            if not registered:
                _LOGGER.warning(
                    "Could not auto-register Lovelace resource. "
                    "Manually add it at Settings → Dashboards → Resources: "
                    "URL=/%s/tag-guard-vehicle-card.js, Type=module", DOMAIN
                )
        else:
            _LOGGER.debug("Lovelace resources not available, skipping auto-registration")
    except Exception as e:
        # Fallback: log instructions for manual registration
        _LOGGER.warning(
            "Could not auto-register Lovelace card resource (%s). "
            "To use the custom card, manually register it at Settings → Dashboards → Resources: "
            "URL=/%s/tag-guard-vehicle-card.js, Type=module",
            e, DOMAIN
        )
