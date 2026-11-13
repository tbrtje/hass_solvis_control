"""Home Assistant actions for the configured SolvisLeo 180 Anlage."""

import asyncio
import math

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from pymodbus.exceptions import ModbusException

from .const import CONF_HOST, CONF_PORT, DOMAIN
from .modbus_scan import scan_modbus_range

SERVICE_SCAN_MODBUS_RANGE = "scan_modbus_range"


def _validate_range(data: dict) -> dict:
    if data["end_address"] < data["start_address"]:
        raise vol.Invalid("end_address must be greater than or equal to start_address")
    if not math.isfinite(data["delay"]):
        raise vol.Invalid("delay must be finite")
    return data


SCAN_MODBUS_RANGE_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Optional("config_entry_id"): str,
            vol.Required("start_address"): vol.All(vol.Coerce(int), vol.Range(min=0, max=65535)),
            vol.Required("end_address"): vol.All(vol.Coerce(int), vol.Range(min=0, max=65535)),
            vol.Optional("register_type", default="both"): vol.In(("input", "holding", "both")),
            vol.Optional("slave_id", default=1): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
            vol.Optional("delay", default=0.05): vol.All(vol.Coerce(float), vol.Range(min=0, max=5)),
            vol.Optional("batch_size", default=20): vol.All(vol.Coerce(int), vol.Range(min=1, max=125)),
        }
    ),
    _validate_range,
)


def _resolve_scan_entry(hass: HomeAssistant, config_entry_id: str | None) -> ConfigEntry:
    """Only scan the address belonging to a loaded integration entry."""
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if config_entry_id is not None:
        for entry in entries:
            if entry.entry_id == config_entry_id:
                return entry
        raise ServiceValidationError("The selected SolvisLeo 180 config entry is not loaded.")
    if not entries:
        raise ServiceValidationError("No SolvisLeo 180 config entry is loaded.")
    if len(entries) > 1:
        raise ServiceValidationError("Specify config_entry_id when multiple SolvisLeo 180 entries are loaded.")
    return entries[0]


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register once during integration setup, including when entries fail."""
    if hass.services.has_service(DOMAIN, SERVICE_SCAN_MODBUS_RANGE):
        return
    locks: dict[str, asyncio.Lock] = {}

    async def handle_scan(call: ServiceCall) -> dict:
        entry = _resolve_scan_entry(hass, call.data.get("config_entry_id"))
        lock = locks.setdefault(entry.entry_id, asyncio.Lock())
        if lock.locked():
            raise ServiceValidationError("A Modbus scan is already running for this Anlage.")
        options = {key: value for key, value in call.data.items() if key != "config_entry_id"}
        async with lock:
            try:
                result = await scan_modbus_range(host=entry.data[CONF_HOST], port=entry.data[CONF_PORT], **options)
            except (ModbusException, OSError, TimeoutError) as error:
                raise HomeAssistantError(f"Could not start the Modbus scan: {error}") from error
        return {**result, "config_entry_id": entry.entry_id}

    hass.services.async_register(
        DOMAIN,
        SERVICE_SCAN_MODBUS_RANGE,
        handle_scan,
        schema=SCAN_MODBUS_RANGE_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
