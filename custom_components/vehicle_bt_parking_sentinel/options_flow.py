"""Options flow for Vehicle BT Parking Sentinel."""
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
    TAG_MODELS,
)
from .utils import translate
 


class VehicleBtParkingSentinelOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Initial options step: collect main options; branch to stationary if needed."""
        current = self.config_entry.options or {}
        if user_input is not None:
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
                    "Stationary checks — how long (minutes) and how many samples must be observed in the same area before saving (e.g. 10 minutes and 3 samples).",
                )
            else:
                stationary_text = "Stationary checks: how long and how many samples to consider a stable position before saving."
            placeholders = {"stationary_help": stationary_text}
            return self.async_show_form(
                step_id="stationary",
                data_schema=vol.Schema(
                {
                    vol.Required(CONF_STATIONARY_MINUTES, default=current.get(CONF_STATIONARY_MINUTES, 10)): NumberSelector(
                        NumberSelectorConfig(min=1, max=60, step=1, mode=NumberSelectorMode.SLIDER, unit_of_measurement="min")
                    ),
                    vol.Required(CONF_STATIONARY_COUNT, default=current.get(CONF_STATIONARY_COUNT, 3)): NumberSelector(
                        NumberSelectorConfig(min=1, max=20, step=1, mode=NumberSelectorMode.SLIDER)
                    ),
                }
            ),
                description_placeholders=placeholders,
            )

    # user_input provided -> handled above
