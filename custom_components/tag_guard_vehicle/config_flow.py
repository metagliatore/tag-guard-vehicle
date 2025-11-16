"""Config flow for Tag Guard Vehicle."""
import voluptuous as vol
import logging

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    BooleanSelector,
    BooleanSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    DOMAIN,
    CONF_DEVICE_TRACKER,
    CONF_PERSON_ENTITY,
    CONF_NOTIFIER,
    CONF_TOLERANCE_RADIUS,
    CONF_STATIONARY_MINUTES,
    CONF_STATIONARY_COUNT,
    CONF_ACTIVATION_MODE,
    CONF_WEBHOOK_TOKEN,
    TAG_MODELS,
)
from .utils import needs_stationary_step, build_create_payload, translate

_LOGGER = logging.getLogger(__name__)


def is_webhook_token_in_use(hass, token: str, exclude_entry_id: str = None) -> bool:
    """Check if a webhook token is already in use by another config entry.
    
    Args:
        hass: Home Assistant instance
        token: The webhook token to check
        exclude_entry_id: Optional entry_id to exclude (for options flow)
    
    Returns:
        True if token is in use, False otherwise
    """
    if not token:
        return False
    
    # Check all existing config entries for this domain
    entries = hass.config_entries.async_entries(DOMAIN)
    for entry in entries:
        if exclude_entry_id and entry.entry_id == exclude_entry_id:
            continue
        
        # Check both data and options for webhook_token
        existing_token = entry.options.get(CONF_WEBHOOK_TOKEN) or entry.data.get(CONF_WEBHOOK_TOKEN)
        if existing_token == token:
            return True
    
    return False

class TagGuardVehicleConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tag Guard Vehicle."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Initial step: collect device_tracker and basic options.

        We intentionally *don't* always ask for stationary parameters. If the
        user chooses an activation mode that requires position-based checks
        ("position" or "combined") we'll present an additional step to
        collect stationary parameters (minutes + count).
        """
        errors = {}
        if user_input is not None:
            # Check if custom webhook_token is provided and if it's already in use
            custom_token = user_input.get("webhook_token", "").strip()
            if custom_token and is_webhook_token_in_use(self.hass, custom_token):
                errors["webhook_token"] = "webhook_token_in_use"
                _LOGGER.warning("Webhook token already in use: %s", custom_token)
            
            if not errors:
                # store the partial results and branch depending on activation mode
                self._user_data = user_input
                activation = user_input.get(CONF_ACTIVATION_MODE)
                if needs_stationary_step(activation):
                    return await self.async_step_stationary()

                # activation doesn't require stationary params: build payload via helper
                data, options = build_create_payload(user_input)
                # if webhook token was auto-generated, log to make flow clearer in logs
                if not user_input.get("webhook_token") and options.get("webhook_token"):
                    import logging

                    logging.getLogger(__name__).info("Generated webhook token for new config entry (shown to user in next step)")
                # stash the built payload and show token page
                self._create_payload = (data, options)
                return await self.async_step_show_token()

        # present initial form
        if user_input is None:
            # Get available notify services
            notify_services = []
            try:
                services = self.hass.services.async_services().get("notify", {})
                notify_services = [f"notify.{service}" for service in services.keys() if service not in ["persistent_notification"]]
            except Exception:
                pass
            
            notify_services_text = ", ".join(notify_services) if notify_services else "No notify services found"
            
            # build translated placeholders (awaited)
            activation_help = await translate(
                self.hass,
                "messages.activation_help",
                "Activation modes: 'connection' — save when the tag disconnects (e.g. Bluetooth lost); 'position' — save when location is stable (e.g. parked); 'combined' — both; 'manual' — no automatic saves (manual control).",
            )
            placeholders = {
                "activation_help": activation_help,
                "tag_model_help": await translate(
                    self.hass,
                    "messages.tag_model_help",
                    "🏷️ SELECT YOUR TAG MODEL FIRST — This determines which device_tracker entities will be shown in the next field. Different tags report GPS coordinates differently.",
                ),
                "device_tracker_help": await translate(
                    self.hass,
                    "messages.device_tracker_help",
                    "📍 Select the device_tracker for your Bluetooth tag (filtered based on your tag model). Example: device_tracker.smarttag_scooter",
                ),
                "person_help": await translate(
                    self.hass,
                    "messages.person_help",
                    "👤 Person associated with the vehicle (used for notifications and presence detection), e.g. person.john.",
                ),
                "notifier_help": await translate(
                    self.hass,
                    "messages.notifier_help",
                    f"🔔 Notification service to receive alerts. Available services: {notify_services_text}",
                ),
                "tolerance_help": await translate(
                    self.hass,
                    "messages.tolerance_help",
                    "📏 GPS tolerance radius: small GPS fluctuations within this radius are ignored (prevents false movement alerts).",
                ),
                "activation_mode_help": await translate(
                    self.hass,
                    "messages.activation_mode_help",
                    "⚙️ Activation mode: 'connection' (auto-save on Bluetooth disconnect), 'position' (auto-save when stationary), 'combined' (both triggers), 'manual' (you control via buttons).",
                ),
                "webhook_help": await translate(
                    self.hass,
                    "messages.webhook_help",
                    "🔗 Optional: custom webhook token for advanced users (leave empty for auto-generated secure token).",
                ),
                "debug_help": await translate(
                    self.hass,
                    "messages.debug_help",
                    "🐛 Enable debug logging for troubleshooting (generates detailed logs — disable after diagnosis).",
                ),
            }

            # CSV stub for pre-filling configuration during debug
            # Reads from debug_stub.csv if present (file is in .gitignore)
            # Format: device_tracker,person,notifier,tolerance,activation_mode,tag_model,webhook_token,debug_mode
            stub_data = {}
            try:
                import os
                from homeassistant.util import loop
                
                stub_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "debug_stub.csv")
                _LOGGER.info("Looking for debug stub at: %s", stub_path)
                
                if os.path.exists(stub_path):
                    # Use async file read to avoid blocking the event loop
                    debug_csv_stub = await self.hass.async_add_executor_job(
                        lambda: open(stub_path, 'r').read().strip()
                    )
                    _LOGGER.info("Debug stub found, content: %s", debug_csv_stub)
                    parts = debug_csv_stub.split(',')
                    if len(parts) >= 8:
                        stub_data = {
                            CONF_DEVICE_TRACKER: parts[0].strip(),
                            CONF_PERSON_ENTITY: parts[1].strip(),
                            CONF_NOTIFIER: parts[2].strip(),
                            CONF_TOLERANCE_RADIUS: int(parts[3].strip()) if parts[3].strip().isdigit() else 200,
                            CONF_ACTIVATION_MODE: parts[4].strip() if parts[4].strip() in ["connection", "position", "combined", "manual"] else "manual",
                            "tag_model": parts[5].strip() if parts[5].strip() in TAG_MODELS else "samsung_smarttag2",
                            "webhook_token": parts[6].strip() or "",
                            "debug_mode": parts[7].strip().lower() == "true",
                        }
                        _LOGGER.info("Parsed stub_data: %s", stub_data)
                    else:
                        _LOGGER.warning("Debug stub has only %d fields, expected 8", len(parts))
                else:
                    _LOGGER.info("Debug stub file not found at: %s", stub_path)
            except Exception as e:
                # If stub file doesn't exist or parsing fails, use empty dict (no pre-fill)
                _LOGGER.exception("Failed to load debug stub: %s", e)
                stub_data = {}


            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                {
                    # 1. Tag Model - FIRST FIELD (primary selection)
                    vol.Required("tag_model", default=stub_data.get("tag_model", "samsung_smarttag2")): SelectSelector(
                        SelectSelectorConfig(
                            options=list(TAG_MODELS.keys()),
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    
                    # 2. Device Tracker - SECOND FIELD (all device_trackers available)
                    # EntitySelector doesn't support string defaults, only use default if value exists
                    vol.Required(CONF_DEVICE_TRACKER, default=stub_data.get(CONF_DEVICE_TRACKER) or vol.UNDEFINED): EntitySelector(
                        EntitySelectorConfig(domain="device_tracker")
                    ),
                    
                    # 3. Person Entity
                    vol.Required(CONF_PERSON_ENTITY, default=stub_data.get(CONF_PERSON_ENTITY) or vol.UNDEFINED): EntitySelector(
                        EntitySelectorConfig(domain="person")
                    ),
                    
                    # 4. Notifier Service
                    # Use SelectSelector if services found, otherwise TextSelector
                    vol.Required(CONF_NOTIFIER, default=stub_data.get(CONF_NOTIFIER, "demo_user" if not notify_services else notify_services[0].replace("notify.", ""))): 
                        SelectSelector(SelectSelectorConfig(
                            options=[s.replace("notify.", "") for s in notify_services] if notify_services else ["demo_user", "telegram"],
                            mode=SelectSelectorMode.DROPDOWN,
                            custom_value=True,  # Allow custom input
                        )) if notify_services else TextSelector(TextSelectorConfig(
                            type=TextSelectorType.TEXT,
                        )),
                    
                    # 5. Tolerance Radius
                    vol.Required(CONF_TOLERANCE_RADIUS, default=stub_data.get(CONF_TOLERANCE_RADIUS, 200)): NumberSelector(
                        NumberSelectorConfig(min=1, max=1000, step=1, mode=NumberSelectorMode.SLIDER, unit_of_measurement="m")
                    ),
                    
                    # 6. Activation Mode
                    vol.Required(CONF_ACTIVATION_MODE, default=stub_data.get(CONF_ACTIVATION_MODE, "manual")): SelectSelector(
                        SelectSelectorConfig(
                            options=["manual", "connection", "position", "combined"],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    
                    # 7. Webhook Token (Optional) - Password field with show/hide toggle
                    vol.Optional("webhook_token", default=stub_data.get("webhook_token", "")): TextSelector(
                        TextSelectorConfig(
                            type=TextSelectorType.PASSWORD,
                        )
                    ),
                    
                    # 8. Debug Mode
                    vol.Required("debug_mode", default=stub_data.get("debug_mode", False)): BooleanSelector(BooleanSelectorConfig()),
                }
            ),
                errors=errors,
                description_placeholders=placeholders,
            )

        # If we reach here user_input was provided and handled above.

    async def async_step_stationary(self, user_input=None):
        """Collect stationary-related parameters (only for position/combined).

        We ask for both a time threshold (minutes) and a number of repeated
        reports (count) that must be observed in the same area before
        activating the guard mode.
        """
        if user_input is not None:
            # merge with stored user_data and generate webhook token
            base = getattr(self, "_user_data", {})
            data, options = build_create_payload(user_input, base=base)
            # stash and show token before finalizing
            self._create_payload = (data, options)
            return await self.async_step_show_token()

        # show stationary form
        if user_input is None:
            placeholders = {
                "stationary_help": await translate(
                    self.hass,
                    "messages.stationary_help",
                        "Position mode activates when vehicle remains stationary for the configured time. "
                        "Time: how many minutes the position must remain stable. "
                        "Count: how many GPS samples must be received (0 = bypass counter check, use time only). "
                        "Example: 10 minutes + 3 samples = activate after 10 minutes with at least 3 stable GPS readings.",
                ),
            }

            return self.async_show_form(
                step_id="stationary",
                data_schema=vol.Schema(
                {
                    vol.Required(CONF_STATIONARY_MINUTES, default=10): NumberSelector(
                        NumberSelectorConfig(min=1, max=60, step=1, mode=NumberSelectorMode.SLIDER, unit_of_measurement="min")
                    ),
                    vol.Required(CONF_STATIONARY_COUNT, default=3): NumberSelector(
                        NumberSelectorConfig(min=0, max=20, step=1, mode=NumberSelectorMode.SLIDER, unit_of_measurement="samples")
                    ),
                }
            ),
                description_placeholders=placeholders,
            )

        # If user_input provided, handled above

    async def async_step_show_token(self, user_input=None):
        """Show the generated webhook token to the user before finishing.

        The token is included in the options persisted to the created entry.
        """
        data, options = getattr(self, "_create_payload", ({}, {}))
        token = options.get("webhook_token", "")
        # try to build a full webhook URL using HA's configured external/base URL
        webhook_url = token
        try:
            # prefer api.base_url when available (includes protocol/port)
            api_cfg = getattr(self.hass.config, "api", None)
            if api_cfg and getattr(api_cfg, "base_url", None):
                base = api_cfg.base_url
            else:
                # fall back to external_url or internal_url if present
                base = getattr(self.hass.config, "external_url", None) or getattr(self.hass.config, "internal_url", None) or ""

            if base and token:
                webhook_url = f"{base.rstrip('/')}/api/webhook/{token}"
        except Exception:
            # best-effort: if we can't compute it, fall back to token only
            webhook_url = token
        
        if user_input is not None:
            # user confirmed by clicking Submit (no fields to validate)
            # The actual webhook token is already in options from previous steps
            
            # Include device_tracker in title for easier identification in UI
            device_tracker = data.get("device_tracker", "")
            if device_tracker:
                # Extract just the name part (e.g., "smarttagscooter" from "device_tracker.smarttagscooter")
                tracker_name = device_tracker.replace("device_tracker.", "").replace("_", " ").title()
                title = f"Tag Guard Vehicle ({tracker_name})"
            else:
                title = "Tag Guard Vehicle"
            return self.async_create_entry(title=title, data=data, options=options)

        # Build description with webhook information
        # Show everything in description - no editable fields needed
        device_tracker_name = data.get("device_tracker", "your_device")
        
        # Build placeholders for the description
        # The description_placeholders are used to replace {key} in translation strings
        placeholders = {
            "webhook_url": webhook_url,
            "webhook_token": token,
            "device_tracker": device_tracker_name,
        }

        # Show form with NO input fields - just description and Submit button
        # The description will use placeholders from description_placeholders
        return self.async_show_form(
            step_id="show_token",
            data_schema=vol.Schema({}),  # Empty schema = no input fields
            description_placeholders=placeholders,
        )
