"""Tests for the reduced Home Assistant configuration surface."""

import pytest

from homeassistant.config_entries import ConfigEntry
from homeassistant.data_entry_flow import FlowResultType

from custom_components.solvis_control.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    DOMAIN,
    POLL_RATE_DEFAULT,
    POLL_RATE_HIGH,
    POLL_RATE_SLOW,
)


POLLING_INTERVALS = {
    POLL_RATE_HIGH: 10,
    POLL_RATE_DEFAULT: 30,
    POLL_RATE_SLOW: 300,
}


async def add_config_entry(hass) -> ConfigEntry:
    """Add a minimal saved entry without allowing the integration to start."""
    config_entry = ConfigEntry(
        version=2,
        minor_version=7,
        domain=DOMAIN,
        title="SolvisLeo 180",
        data={
            CONF_NAME: "SolvisLeo 180",
            CONF_HOST: "10.0.0.131",
            CONF_PORT: 502,
            **POLLING_INTERVALS,
        },
        source="user",
        entry_id="test_entry_id",
        unique_id=None,
        options={},
        discovery_keys={},
        subentries_data={},
    )
    await hass.config_entries.async_add(config_entry)
    return config_entry


@pytest.fixture
def skip_integration_setup(hass, monkeypatch) -> None:
    """Keep config-flow tests focused on the Home Assistant flow seam."""
    async def skip(*_args, **_kwargs) -> bool:
        return True

    monkeypatch.setattr(hass.config_entries, "async_setup", skip)


@pytest.mark.asyncio
async def test_setup_creates_an_entry_from_only_connection_and_polling_settings(hass, skip_integration_setup) -> None:
    """A new setup ends after collecting the controller connection and intervals."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    user_input = {
        CONF_HOST: "10.0.0.131",
        CONF_PORT: 502,
        **POLLING_INTERVALS,
    }
    result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "SolvisLeo 180"
    assert result["data"] == {CONF_NAME: "SolvisLeo 180", **user_input}


@pytest.mark.asyncio
async def test_setup_rejects_incompatible_polling_intervals(hass) -> None:
    """The one setup form retains the polling-interval validation."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "10.0.0.131",
            CONF_PORT: 502,
            POLL_RATE_HIGH: 15,
            POLL_RATE_DEFAULT: 10,
            POLL_RATE_SLOW: 300,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "poll_rate_invalid_high"}


@pytest.mark.asyncio
async def test_options_flow_updates_address_and_polling_intervals(hass, skip_integration_setup) -> None:
    """Address and polling intervals remain configurable after setup."""
    config_entry = await add_config_entry(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    user_input = {
        CONF_HOST: "10.0.0.132",
        CONF_PORT: 1502,
        POLL_RATE_HIGH: 5,
        POLL_RATE_DEFAULT: 10,
        POLL_RATE_SLOW: 60,
    }
    result = await hass.config_entries.options.async_configure(result["flow_id"], user_input)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "SolvisLeo 180"
    assert result["data"] == user_input


@pytest.mark.asyncio
async def test_options_flow_rejects_incompatible_polling_intervals(hass, skip_integration_setup) -> None:
    """Editing intervals keeps their setup-time safety checks."""
    config_entry = await add_config_entry(hass)
    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "10.0.0.132",
            CONF_PORT: 502,
            POLL_RATE_HIGH: 15,
            POLL_RATE_DEFAULT: 10,
            POLL_RATE_SLOW: 60,
        }
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"] == {"base": "poll_rate_invalid_high"}
