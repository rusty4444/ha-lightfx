"""Config flow for HA LightFX integration."""

from homeassistant import config_entries
from homeassistant.core import callback
import voluptuous as vol

from .const import DOMAIN, CONF_NAME


class LightFXConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HA LightFX."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(title="HA LightFX", data={})

        return self.async_show_form(step_id="user")

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return LightFXOptionsFlow(config_entry)


class LightFXOptionsFlow(config_entries.OptionsFlow):
    """Options flow for HA LightFX."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return self.async_abort(reason="no_options")
