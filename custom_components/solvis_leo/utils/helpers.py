"""
Helper file for various config modules
"""

import logging
import re

from decimal import Decimal
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pymodbus.exceptions import ConnectionException
from pymodbus.client import AsyncModbusTcpClient

from custom_components.solvis_leo.const import (
    CONF_NAME,
    CONF_HOST,
    DOMAIN,
    MANUFACTURER,
    DATA_COORDINATOR,
    DERIVATIVE_SENSORS,
    REGISTER_ADDRESSES_BY_NAME,
    REGISTERS,
    SCHEDULES,
)

from ..registers import EntityType

_LOGGER = logging.getLogger(__name__)


def parse_solvis_version(raw) -> str | None:
    """
    Convert a raw version register value (32770 / 32771) into a "X.YY.ZZ" string.

    Returns None if the device does not report a usable version. Some models, e.g. the
    SolvisLeo, answer the version registers with 0 instead of a version number.
    """
    if raw is None:
        return None

    # The registers are read as signed INT16, but a version is unsigned: everything
    # from 3.28.00 on exceeds 32767 and wraps negative. Undo that wrap before parsing.
    if isinstance(raw, (int, float)) and not isinstance(raw, bool) and raw < 0:
        raw = int(raw) + 65536

    raw_str = str(raw)
    if len(raw_str) != 5 or not raw_str.isdigit():
        return None

    return f"{raw_str[0]}.{raw_str[1:3]}.{raw_str[3:5]}"


def generate_device_info(entry: ConfigEntry, host: str, name: str) -> DeviceInfo:
    """Generate device info."""
    _LOGGER.debug(f"Generating device info for {host}")
    _LOGGER.debug(f"Entry data: {entry.data}")

    info = {
        "identifiers": {(DOMAIN, host)},
        "name": name,
        "manufacturer": MANUFACTURER,
        "model": "SolvisLeo 180 (SC3)",
    }

    if "VERSIONSC" in entry.data:
        info["sw_version"] = entry.data["VERSIONSC"]
    if "VERSIONNBG" in entry.data:
        info["hw_version"] = entry.data["VERSIONNBG"]

    return DeviceInfo(**info)


async def remove_old_entities(hass: HomeAssistant, config_entry_id: str, active_entity_ids: set) -> None:
    """Remove entities from the registry that are not in active_entity_ids."""

    entity_registry = er.async_get(hass)

    existing_entities = [entity_entry for entity_entry in entity_registry.entities.values() if entity_entry.config_entry_id == config_entry_id]
    existing_entity_ids = {entity_entry.unique_id for entity_entry in existing_entities}
    entities_to_remove = [entity_entry for entity_entry in existing_entities if entity_entry.unique_id not in active_entity_ids]

    _LOGGER.debug(f"Existing unique_ids: {existing_entity_ids}")
    _LOGGER.debug(f"Active unique_ids: {active_entity_ids}")
    _LOGGER.debug(f"Existing but not active unique_ids to remove: {[entity.unique_id for entity in entities_to_remove]}")

    for entity_entry in entities_to_remove:
        entity_registry.async_remove(entity_entry.entity_id)
        _LOGGER.debug(f"Removed old entity: {entity_entry.unique_id} (entity_id: {entity_entry.entity_id})")


def active_entity_unique_ids() -> set[str]:
    """Return the complete entity set owned by this fixed Anlage model."""
    active_ids = {generate_unique_id(register.address, register.name) for register in REGISTERS if register.input_type != EntityType.BLOCK}

    for name, config in DERIVATIVE_SENSORS.items():
        source_address = REGISTER_ADDRESSES_BY_NAME[config["source_keys"][0]]
        active_ids.add(generate_unique_id(source_address, name))

    for schedule in SCHEDULES:
        address = REGISTER_ADDRESSES_BY_NAME[schedule]
        active_ids.add(generate_unique_id(address, schedule))
        active_ids.add(generate_unique_id(address, f"{schedule}_active"))

    return active_ids


def generate_unique_id(modbus_address: int, name: str) -> str:
    """Generate a unique ID by cleaning the given name."""
    cleaned_name = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")
    if cleaned_name:
        return f"{modbus_address}_{cleaned_name}"
    return str(modbus_address)  # if name consists of special chars only


def process_coordinator_data(coordinator_data: dict, response_key: str):
    """
    Process data from the coordinator for a given response key.

    Returns a tuple (available, value, extra_state_attributes):
    - available: Boolean indicating if data is valid.
    - value: The raw value from the coordinator.
    - extra_state_attributes: Additional attributes (e.g. raw_value).

    If the data is not valid, available is False.
    If response_key is not present, None is returned.
    """
    if coordinator_data is None:
        _LOGGER.warning("Data from coordinator is None. Skipping update")
        return False, None, {}

    if not isinstance(coordinator_data, dict):
        _LOGGER.warning("Invalid data from coordinator")
        return False, None, {}

    if response_key not in coordinator_data:
        _LOGGER.debug(f"[{response_key}] Skipping update: no data available in coordinator. Skipped update!?")
        return None, None, {}

    response_data = coordinator_data.get(response_key)

    if response_data is None:
        _LOGGER.debug(f"[{response_key}] No data available: response data is None.")
        return False, None, {}

    if not isinstance(response_data, (int, float, Decimal)) or isinstance(response_data, complex):  # complex numbers are not valid
        _LOGGER.warning(f"[{response_key}] Invalid response data type from coordinator: {response_data} has type {type(response_data)}")
        return False, None, {}

    if response_data == -300:
        _LOGGER.warning(f"[{response_key}] The coordinator failed to fetch data.")
        return False, None, {}

    extra_state_attributes = {"raw_value": response_data}

    return True, response_data, extra_state_attributes


async def async_setup_solvis_entities(
    hass,
    entry,
    async_add_entities: AddEntitiesCallback,
    entity_cls,
    input_type: EntityType,
):
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    host = entry.data.get(CONF_HOST)
    name = entry.data.get(CONF_NAME)

    if host is None:
        _LOGGER.error("Device has no address")
        return

    device_info = generate_device_info(entry, host, name)

    entities = []
    for register in REGISTERS:
        if register.input_type != input_type:
            continue

        kwargs = {
            "coordinator": coordinator,
            "device_info": device_info,
            "host": host,
            "name": register.name,
            "enabled_by_default": register.enabled_by_default,
            "modbus_address": register.address,
        }

        if register.input_type == EntityType.SELECT:
            kwargs["options"] = register.options

        if register.input_type == EntityType.SENSOR:
            kwargs["unit_of_measurement"] = register.unit
            kwargs["device_class"] = register.device_class
            kwargs["state_class"] = register.state_class
            kwargs["entity_category"] = register.entity_category
            kwargs["suggested_precision"] = register.suggested_precision

        if register.input_type == EntityType.NUMBER:
            kwargs["unit_of_measurement"] = register.unit
            kwargs["device_class"] = register.device_class
            kwargs["state_class"] = register.state_class
            kwargs["range_data"] = register.range_data
            kwargs["step_size"] = register.step_size
            kwargs["multiplier"] = register.multiplier

        if register.input_type == EntityType.BINARY_SENSOR:
            kwargs["device_class"] = register.device_class
            kwargs["state_class"] = register.state_class
            kwargs["entity_category"] = register.entity_category

        entity = entity_cls(**kwargs)
        entities.append(entity)
        _LOGGER.debug(f"Erstellte unique_id: {entity.unique_id}")

    async_add_entities(entities)
    _LOGGER.info(f"Successfully added {len(entities)} entities")


async def ensure_connected(client) -> bool:
    """
    Ensure the Modbus client is connected.
    If not, attempt one reconnect and return success state.
    """
    if not client.connected:
        _LOGGER.debug("Modbus client not connected. Reconnecting...")
        try:
            connected = await client.connect()
            if connected is False:
                _LOGGER.error("Modbus reconnect failed: connect() returned False")
                return False
            _LOGGER.debug("Modbus reconnect successful")
        except ConnectionException as e:
            _LOGGER.error(f"Modbus reconnect failed: {e}")
            return False
    return True


def create_modbus_client(
    host: str,
    port: int,
    timeout: float = 2.0,
    retries: int = 1,
    reconnect_delay: float = 0.5,
    reconnect_delay_max: float = 5.0,
) -> AsyncModbusTcpClient:
    """Create the Modbus client with settings suitable for the SC3 controller."""
    return AsyncModbusTcpClient(
        host=host,
        port=port,
        timeout=timeout,
        retries=retries,
        reconnect_delay=reconnect_delay,
        reconnect_delay_max=reconnect_delay_max,
    )
