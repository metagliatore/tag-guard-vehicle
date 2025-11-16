"""Options flow for Tag Guard Vehicle."""
import voluptuous as vol

from homeassistant import config_entries
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
)

from .const import (
    CONF_PERSON_ENTITY,
    CONF_NOTIFIER,
    CONF_TOLERANCE_RADIUS,
    CONF_STATIONARY_MINUTES,
    CONF_STATIONARY_COUNT,
    CONF_ACTIVATION_MODE,
    CONF_WEBHOOK_TOKEN,
    TAG_MODELS,
    DOMAIN,
)
from .utils import translate


def is_webhook_token_in_use(hass, token, exclude_entry_id=None):
    """Check if a webhook token is already in use by another entry."""
    if not token:
        return False
    
    entries = hass.config_entries.async_entries(DOMAIN)
    for entry in entries:
        if exclude_entry_id and entry.entry_id == exclude_entry_id:
            continue
        existing_token = entry.options.get(CONF_WEBHOOK_TOKEN) or entry.data.get(CONF_WEBHOOK_TOKEN)
        if existing_token == token:
            return True
    return False
 


class TagGuardVehicleOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Initial options step: collect main options; branch to stationary if needed."""
        current = self.config_entry.options or {}
        errors = {}
        
        if user_input is not None:
            # Validate webhook token uniqueness if provided and different from current
            new_token = user_input.get("webhook_token", "").strip()
            current_token = current.get(CONF_WEBHOOK_TOKEN, "")
            
            if new_token and new_token != current_token:
                hass = getattr(self, "hass", None) or getattr(self.config_entry, "hass", None)
                if hass and is_webhook_token_in_use(hass, new_token, self.config_entry.entry_id):
                    errors["webhook_token"] = "webhook_token_in_use"
            
            if not errors:
                # if activation requires stationary params, keep partial and ask
                activation = user_input.get(CONF_ACTIVATION_MODE, current.get(CONF_ACTIVATION_MODE))
                self._user_input = {**current, **user_input}
                if activation in ("position", "combined"):
                    return await self.async_step_stationary()
                return self.async_create_entry(title="Options updated", data=self._user_input)

        # show initial options form
        if user_input is None:
            # tests may construct the flow without wiring hass to the config entry
            hass = getattr(self, "hass", None) or getattr(self.config_entry, "hass", None)
            if hass:
                activation_help = await translate(
                    hass,
                    "messages.activation_help",
                    "Activation modes: 'connection' — save when the tag disconnects (e.g. Bluetooth lost); 'position' — save when location is stable (e.g. parked); 'combined' — both; 'manual' — no automatic saves (manual control).",
                )
            else:
                # fallback when running under tests where hass isn't available
                activation_help = "The 'manual' activation mode disables automatic saves and requires manual control."
            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema(
                {
                    vol.Required(CONF_PERSON_ENTITY, default=current.get(CONF_PERSON_ENTITY)): EntitySelector(
                        EntitySelectorConfig(domain="person")
                    ),
                    vol.Required(CONF_NOTIFIER, default=current.get(CONF_NOTIFIER)): EntitySelector(
                        EntitySelectorConfig(domain="notify")
                    ),
                    vol.Required(CONF_TOLERANCE_RADIUS, default=current.get(CONF_TOLERANCE_RADIUS, 200)): NumberSelector(
                        NumberSelectorConfig(min=1, max=1000, step=1, mode=NumberSelectorMode.SLIDER, unit_of_measurement="m")
                    ),
                    vol.Required(CONF_ACTIVATION_MODE, default=current.get(CONF_ACTIVATION_MODE, "position")): SelectSelector(
                        SelectSelectorConfig(
                            options=["connection", "position", "combined", "manual"],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional("tag_model", default=current.get("tag_model", list(TAG_MODELS.keys())[0])): SelectSelector(
                        SelectSelectorConfig(
                            options=list(TAG_MODELS.keys()),
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional("webhook_token", default=current.get("webhook_token", "")): str,
                    vol.Required("debug_mode", default=current.get("debug_mode", False)): BooleanSelector(BooleanSelectorConfig()),
                }
            ),
                errors=errors,
                description_placeholders={"activation_help": activation_help},
            )

        # user_input provided -> handled above

    async def async_step_stationary(self, user_input=None):
        """Collect stationary-specific options (minutes + count) when required."""
        current = self.config_entry.options or {}
        if user_input is not None:
            merged = {**getattr(self, "_user_input", {}), **user_input}
            return self.async_create_entry(title="Options updated", data=merged)

        if user_input is None:
            hass = getattr(self, "hass", None) or getattr(self.config_entry, "hass", None)
            if hass:
                stationary_text = await translate(
                    hass,
                    "messages.stationary_help",
                    "Position mode activates when vehicle remains stationary for the configured time. "
                    "Time: how many minutes the position must remain stable. "
                    "Count: how many GPS samples must be received (0 = bypass counter check, use time only). "
                    "Example: 10 minutes + 3 samples = activate after 10 minutes with at least 3 stable GPS readings.",
                )
            else:
                stationary_text = "Stationary checks: Time (minutes) and Count (GPS samples, 0=bypass). Example: 10 min + 3 samples."
            placeholders = {"stationary_help": stationary_text}
            return self.async_show_form(
                step_id="stationary",
                data_schema=vol.Schema(
                {
                    vol.Required(CONF_STATIONARY_MINUTES, default=current.get(CONF_STATIONARY_MINUTES, 10)): NumberSelector(
                        NumberSelectorConfig(min=1, max=60, step=1, mode=NumberSelectorMode.SLIDER, unit_of_measurement="min")
                    ),
                    vol.Required(CONF_STATIONARY_COUNT, default=current.get(CONF_STATIONARY_COUNT, 3)): NumberSelector(
                        NumberSelectorConfig(min=0, max=20, step=1, mode=NumberSelectorMode.SLIDER, unit_of_measurement="samples")
                    ),
                }
            ),
                description_placeholders=placeholders,
            )

    # user_input provided -> handled above
