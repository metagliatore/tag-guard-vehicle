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
from .utils import needs_stationary_step, build_create_payload, get_webhook_url

_LOGGER = logging.getLogger(__name__)


class TagGuardVehicleConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tag Guard Vehicle."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        from .options_flow import TagGuardVehicleOptionsFlowHandler

        return TagGuardVehicleOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Initial step: collect device_tracker and basic options.

        We intentionally *don't* always ask for stationary parameters. If the
        user chooses an activation mode that requires position-based checks
        ("position" or "combined") we'll present an additional step to
        collect stationary parameters (minutes + count).
        """
        errors = {}
        if user_input is not None:
            # store the partial results and branch depending on activation mode
            self._user_data = user_input
            activation = user_input.get(CONF_ACTIVATION_MODE)
            if needs_stationary_step(activation):
                return await self.async_step_stationary()

            # activation doesn't require stationary params: build payload via helper
            data, options = build_create_payload(user_input)
            _LOGGER.info("Generated webhook token for new config entry (shown to user in next step)")
            # stash the built payload and show token page
            self._create_payload = (data, options)
            return await self.async_step_show_token()

        # present initial form
        if user_input is None:
            # Get available notification services (notify + telegram_bot.send_message)
            notify_services = []
            telegram_services = []
            notifier_services = []
            try:
                all_services = self.hass.services.async_services()
                notify_domain_services = all_services.get("notify", {})
                notify_services = [
                    f"notify.{service}"
                    for service in notify_domain_services.keys()
                    if service not in ["persistent_notification"]
                ]
                telegram_domain_services = all_services.get("telegram_bot", {})
                if "send_message" in telegram_domain_services:
                    telegram_services = ["telegram_bot.send_message"]
                notifier_services = notify_services + telegram_services
            except Exception:
                pass
            
            notify_services_text = ", ".join(notifier_services) if notifier_services else "No notification services found"
            
            # CSV stub for pre-filling configuration during debug
            # Reads from debug_stub.csv if present (file is in .gitignore)
            # Format: device_tracker,person,notifier,tolerance,activation_mode,tag_model,webhook_token,debug_mode
            stub_data = {}
            try:
                import os

                stub_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "debug_stub.csv")
                _LOGGER.info("Looking for debug stub at: %s", stub_path)

                if os.path.exists(stub_path):
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
                            CONF_ACTIVATION_MODE: parts[4].strip() if parts[4].strip() in ["connection", "position", "combined", "manual"] else "combined",
                            "tag_model": parts[5].strip() if parts[5].strip() in TAG_MODELS else "vedeneb_ha_smartthings_find",
                            "webhook_token": parts[6].strip() or "",
                            "debug_mode": parts[7].strip().lower() == "true",
                        }
                        _LOGGER.info("Parsed stub_data: %s", stub_data)
                    else:
                        _LOGGER.warning("Debug stub has only %d fields, expected 8", len(parts))
                else:
                    _LOGGER.info("Debug stub file not found at: %s", stub_path)
            except Exception as e:
                _LOGGER.exception("Failed to load debug stub: %s", e)
                stub_data = {}


            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                {
                    # ── 1. Device Tracker ──────────────────────────────
                    vol.Required(CONF_DEVICE_TRACKER, default=stub_data.get(CONF_DEVICE_TRACKER) or vol.UNDEFINED): EntitySelector(
                        EntitySelectorConfig(domain="device_tracker")
                    ),

                    # ── 2. Tag Model / Parser ──────────────────────────
                    vol.Required("tag_model", default=stub_data.get("tag_model", "vedeneb_ha_smartthings_find")): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                {"value": k, "label": v}
                                for k, v in TAG_MODELS.items()
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),

                    # ── 3. Activation Mode ─────────────────────────────
                    vol.Required(CONF_ACTIVATION_MODE, default=stub_data.get(CONF_ACTIVATION_MODE, "combined")): SelectSelector(
                        SelectSelectorConfig(
                            options=["combined", "position", "connection", "manual"],
                            mode=SelectSelectorMode.DROPDOWN,
                            translation_key="activation_mode",
                        )
                    ),

                    # ── 4. Notifier Service ────────────────────────────
                    vol.Required(CONF_NOTIFIER, default=stub_data.get(CONF_NOTIFIER, notifier_services[0] if notifier_services else "notify.notify")):
                        SelectSelector(SelectSelectorConfig(
                            options=notifier_services if notifier_services else ["notify.notify", "telegram_bot.send_message"],
                            mode=SelectSelectorMode.DROPDOWN,
                            custom_value=True,
                        )) if notifier_services else TextSelector(TextSelectorConfig(
                            type=TextSelectorType.TEXT,
                        )),

                    # ── 5. Tolerance Radius ────────────────────────────
                    vol.Required(CONF_TOLERANCE_RADIUS, default=stub_data.get(CONF_TOLERANCE_RADIUS, 200)): NumberSelector(
                        NumberSelectorConfig(min=1, max=1000, step=1, mode=NumberSelectorMode.SLIDER, unit_of_measurement="m")
                    ),

                    # ── 6. Debug Mode ──────────────────────────────────
                    vol.Required("debug_mode", default=stub_data.get("debug_mode", False)): BooleanSelector(BooleanSelectorConfig()),
                }
            ),
                errors=errors,
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
            )

        # If user_input provided, handled above

    async def async_step_show_token(self, user_input=None):
        """Show the generated webhook token to the user before finishing.

        The token is included in the options persisted to the created entry.
        """
        data, options = getattr(self, "_create_payload", ({}, {}))
        token = options.get("webhook_token", "")
        webhook_url = get_webhook_url(self.hass, token)
        
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
