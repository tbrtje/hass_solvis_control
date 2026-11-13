"""Diagnostics from the current snapshot, with no additional Modbus traffic."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_HOST, CONF_NAME, DATA_COORDINATOR, DOMAIN


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Return cached values, register metadata and the current failure state."""
    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id, {}).get(DATA_COORDINATOR)
    return {
        "entry_data": async_redact_data(dict(entry.data), {CONF_HOST, CONF_NAME}),
        "coordinator": coordinator.diagnostic_snapshot() if coordinator is not None else {"loaded": False},
    }
