"""Home Assistant configuration flows for the SolvisLeo 180 integration."""

import voluptuous as vol
from voluptuous.schema_builder import Schema

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONFIG_ENTRY_MINOR_VERSION,
    CONFIG_ENTRY_VERSION,
    DOMAIN,
    POLL_RATE_DEFAULT,
    POLL_RATE_HIGH,
    POLL_RATE_SLOW,
)


def validate_poll_rates(data: ConfigType) -> ConfigType:
    """Require nested polling intervals so each group has a regular cadence."""
    if data[POLL_RATE_DEFAULT] % data[POLL_RATE_HIGH] != 0:
        raise vol.Invalid(cv.string("poll_rate_invalid_high"))
    if data[POLL_RATE_SLOW] % data[POLL_RATE_DEFAULT] != 0:
        raise vol.Invalid(cv.string("poll_rate_invalid_slow"))
    return data


def get_connection_schema(data: ConfigType) -> Schema:
    """Build the complete, deliberately small configuration schema."""
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=data.get(CONF_HOST, "")): str,
            vol.Required(CONF_PORT, default=data.get(CONF_PORT, 502)): vol.Coerce(int),
            vol.Required(POLL_RATE_HIGH, default=data.get(POLL_RATE_HIGH, 10)): vol.All(vol.Coerce(int), vol.Range(min=2)),
            vol.Required(POLL_RATE_DEFAULT, default=data.get(POLL_RATE_DEFAULT, 30)): vol.All(vol.Coerce(int), vol.Range(min=2)),
            vol.Required(POLL_RATE_SLOW, default=data.get(POLL_RATE_SLOW, 300)): vol.All(vol.Coerce(int), vol.Range(min=10)),
        }
    )


class SolvisConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure a controller connection and its three polling intervals."""

    VERSION = CONFIG_ENTRY_VERSION
    MINOR_VERSION = CONFIG_ENTRY_MINOR_VERSION

    async def async_step_user(self, user_input: ConfigType | None = None) -> FlowResult:
        """Handle the single setup step."""
        errors = {}
        if user_input is not None:
            try:
                validate_poll_rates(user_input)
            except vol.Invalid as exc:
                errors["base"] = exc.error_message
            else:
                return self.async_create_entry(
                    title="SolvisLeo 180",
                    data={CONF_NAME: "SolvisLeo 180", **user_input},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=get_connection_schema(user_input or {}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the connection and polling settings options flow."""
        return SolvisOptionsFlow(config_entry)


class SolvisOptionsFlow(config_entries.OptionsFlow):
    """Allow the controller address and polling intervals to be changed."""

    VERSION = CONFIG_ENTRY_VERSION
    MINOR_VERSION = CONFIG_ENTRY_MINOR_VERSION

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Seed the one options form with the saved configuration."""
        self.entry_id = config_entry.entry_id
        self._title = config_entry.title
        self.data = {**config_entry.data, **config_entry.options}

    async def async_step_init(self, user_input: ConfigType | None = None) -> FlowResult:
        """Handle the single options step."""
        errors = {}
        if user_input is not None:
            try:
                validate_poll_rates(user_input)
            except vol.Invalid as exc:
                errors["base"] = exc.error_message
            else:
                return self.async_create_entry(title=self._title, data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=get_connection_schema(self.data),
            errors=errors,
        )
