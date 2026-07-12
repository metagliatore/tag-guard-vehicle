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
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_NOTIFIER,
    CONF_TOLERANCE_RADIUS,
    CONF_STATIONARY_MINUTES,
    CONF_STATIONARY_COUNT,
    CONF_ACTIVATION_MODE,
    TAG_MODELS,
)
 


class TagGuardVehicleOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Initial options step: collect main options; branch to stationary if needed."""
        current = self.config_entry.options or {}
        errors = {}
        
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
            notifier_services = []
            if hass:
                try:
                    all_services = hass.services.async_services()
                    notify_services = [
                        f"notify.{service}"
                        for service in all_services.get("notify", {}).keys()
                        if service not in ["persistent_notification"]
                    ]
                    telegram_services = [
                        "telegram_bot.send_message"
                    ] if "send_message" in all_services.get("telegram_bot", {}) else []
                    notifier_services = notify_services + telegram_services
                except Exception:
                    notifier_services = []

            if hass:
                pass  # activation modes explained by dropdown labels only
            else:
                pass

            notifier_selector = (
                SelectSelector(
                    SelectSelectorConfig(
                        options=notifier_services,
                        mode=SelectSelectorMode.DROPDOWN,
                        custom_value=True,
                    )
                )
                if notifier_services
                else TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT))
            )

            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema(
                {
                    vol.Required(CONF_NOTIFIER, default=current.get(CONF_NOTIFIER, notifier_services[0] if notifier_services else "notify.notify")): notifier_selector,
                    vol.Required(CONF_TOLERANCE_RADIUS, default=current.get(CONF_TOLERANCE_RADIUS, 200)): NumberSelector(
                        NumberSelectorConfig(min=1, max=1000, step=1, mode=NumberSelectorMode.SLIDER, unit_of_measurement="m")
                    ),
                    vol.Required(CONF_ACTIVATION_MODE, default=current.get(CONF_ACTIVATION_MODE, "combined")): SelectSelector(
                        SelectSelectorConfig(
                            options=["connection", "position", "combined", "manual"],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional("tag_model", default=current.get("tag_model", list(TAG_MODELS.keys())[0])): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                {"value": k, "label": v}
                                for k, v in TAG_MODELS.items()
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required("debug_mode", default=current.get("debug_mode", False)): BooleanSelector(BooleanSelectorConfig()),
                }
            ),
                errors=errors,
            )

        # user_input provided -> handled above

    async def async_step_stationary(self, user_input=None):
        """Collect stationary-specific options (minutes + count) when required."""
        current = self.config_entry.options or {}
        if user_input is not None:
            merged = {**getattr(self, "_user_input", {}), **user_input}
            return self.async_create_entry(title="Options updated", data=merged)

        if user_input is None:
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
            )

    # user_input provided -> handled above
