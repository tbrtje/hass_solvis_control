"""
Module to integrate solvis heaters to.
"""

"""Solvis integration."""

import logging
import os, json

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from pymodbus.client import AsyncModbusTcpClient
from homeassistant.config_entries import ConfigEntryNotReady
from .utils.helpers import active_entity_unique_ids, create_modbus_client, remove_old_entities
from .coordinator import SolvisModbusCoordinator
from .services import async_setup_services

from .const import (
    CONF_HOST,
    CONF_PORT,
    CONF_NAME,
    CONFIG_ENTRY_DATA_KEYS,
    CONFIG_ENTRY_MINOR_VERSION,
    CONFIG_ENTRY_VERSION,
    DATA_COORDINATOR,
    DOMAIN,
    POLL_RATE_SLOW,
    POLL_RATE_DEFAULT,
    POLL_RATE_HIGH,
)

PLATFORMS: [Platform] = [
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SWITCH,
    Platform.BINARY_SENSOR,
    Platform.UPDATE,
]

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


# read version from manifest.json
manifest = json.load(open(os.path.join(os.path.dirname(__file__), "manifest.json")))
VERSION = manifest.get("version", "unbekannt")


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register actions independently of the connection to the Anlage."""
    async_setup_services(hass)
    return True


def _normalized_config_data(*sources: dict) -> dict:
    """Merge saved settings and keep only the supported configuration surface."""
    combined = {}
    for source in sources:
        combined.update(source)

    data = {key: combined[key] for key in CONFIG_ENTRY_DATA_KEYS if key in combined}
    data.setdefault(CONF_NAME, "SolvisLeo 180")
    data.setdefault(CONF_PORT, 502)
    data.setdefault(POLL_RATE_HIGH, 10)
    data.setdefault(POLL_RATE_DEFAULT, 30)
    data.setdefault(POLL_RATE_SLOW, 300)
    return data


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Solvis device from a config entry."""

    conf_host = entry.data.get(CONF_HOST)
    conf_port = entry.data.get(CONF_PORT)

    if conf_host is None or conf_port is None:
        return False

    hass.data.setdefault(DOMAIN, {})

    # Create modbus client
    client = create_modbus_client(
        host=conf_host,
        port=conf_port,
    )
    entry.runtime_data = {"modbus": client}

    try:
        try:
            if not await client.connect():
                raise ConfigEntryNotReady("SolvisLeo 180 Control not reachable")
        except Exception as err:
            raise ConfigEntryNotReady("SolvisLeo 180 Control not reachable") from err

        coordinator = SolvisModbusCoordinator(hass, entry)
        await coordinator.async_config_entry_first_refresh()
        hass.data[DOMAIN][entry.entry_id] = {DATA_COORDINATOR: coordinator}

        try:
            await remove_old_entities(hass, entry.entry_id, active_entity_unique_ids())
        except Exception:
            _LOGGER.exception("Error removing old entities")

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        entry.async_on_unload(entry.add_update_listener(options_update_listener))
    except BaseException:
        # Cancellation and failed first refreshes also own a connected client.
        _close_client(client)
        hass.data[DOMAIN].pop(entry.entry_id, None)
        raise

    _LOGGER.info(f"SolvisLeo 180 Control - Version {VERSION}")

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    _close_client(entry.runtime_data["modbus"])
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return True


def _close_client(client: AsyncModbusTcpClient) -> None:
    """Preserve the original setup failure and always finish unload cleanup."""
    try:
        client.close()
    except Exception:
        _LOGGER.exception("Error closing Modbus connection")


async def options_update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
    """Handle options update."""
    # Persist connection and polling changes before reloading the entry.
    new_data = _normalized_config_data(config_entry.data, config_entry.options)
    hass.config_entries.async_update_entry(config_entry, data=new_data, options={})

    # Trigger a full reload of the config entry. This unloads and then sets up the integration again.
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_migrate_entry(hass, config_entry: ConfigEntry):
    """Keep only the connection and polling settings supported by this fork."""
    new_data = _normalized_config_data(config_entry.data, config_entry.options)

    hass.config_entries.async_update_entry(
        config_entry,
        data=new_data,
        options={},
        minor_version=CONFIG_ENTRY_MINOR_VERSION,
        version=CONFIG_ENTRY_VERSION,
    )

    _LOGGER.info(
        "Migration to version %s_%s successful",
        CONFIG_ENTRY_VERSION,
        CONFIG_ENTRY_MINOR_VERSION,
    )

    return True
