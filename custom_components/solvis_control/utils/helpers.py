"""
Helper file for various config modules
"""

import logging
import re
import socket

from decimal import Decimal
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import async_resolve_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from scapy.all import ARP, Ether, srp
from pymodbus.exceptions import ConnectionException, ModbusException
from pymodbus.client import AsyncModbusTcpClient

from custom_components.solvis_control.const import (
    CONF_NAME,
    PORT,
    CONF_HOST,
    CONF_PORT,
    DOMAIN,
    MANUFACTURER,
    DATA_COORDINATOR,
    CONF_OPTION_1,
    CONF_OPTION_2,
    CONF_OPTION_3,
    CONF_OPTION_4,
    CONF_OPTION_5,
    CONF_OPTION_6,
    CONF_OPTION_7,
    CONF_OPTION_8,
    CONF_OPTION_9,
    CONF_OPTION_10,
    CONF_OPTION_11,
    CONF_OPTION_12,
    POLL_RATE_SLOW,
    POLL_RATE_DEFAULT,
    POLL_RATE_HIGH,
    REGISTERS,
    CONF_HKR1_NAME,
    CONF_HKR2_NAME,
    CONF_HKR3_NAME,
)

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
        "model": "Solvis Control 3",
    }

    if "VERSIONSC" in entry.data:
        info["sw_version"] = entry.data["VERSIONSC"]
    if "VERSIONNBG" in entry.data:
        info["hw_version"] = entry.data["VERSIONNBG"]

    return DeviceInfo(**info)


async def fetch_modbus_value(
    register,
    register_type,
    host: str,
    port: int,
    datatype="INT16",
    order="big",
) -> int | list[int] | None:
    """
    Fetch one or multiple values from the Modbus device.
    If 'register' is an int, returns a single value.
    If 'register' is a list of ints, returns a list of values.
    """

    single = False
    if isinstance(register, int):
        single = True
        registers = [register]
    else:
        registers = register

    results = []

    async with create_modbus_client(
        host=host,
        port=port,
    ) as client:

        for reg in registers:
            if register_type == 1:
                data = await client.read_input_registers(address=reg, count=1)
            else:
                data = await client.read_holding_registers(address=reg, count=1)

            if not data or not hasattr(data, "registers") or data.isError():
                raise ModbusException(f"[fetch_modbus_value] Invalid response from Modbus for register {reg} at {host}:{port}")

            value = client.convert_from_registers(
                data.registers,
                data_type=client.DATATYPE.INT16,
                word_order=order,
            )
            results.append(value)

        return results[0] if single else results


conf_options_map = {
    1: CONF_OPTION_1,
    2: CONF_OPTION_2,
    3: CONF_OPTION_3,
    4: CONF_OPTION_4,
    5: CONF_OPTION_5,
    6: CONF_OPTION_6,
    7: CONF_OPTION_7,
    8: CONF_OPTION_8,
    9: CONF_OPTION_9,
    10: CONF_OPTION_10,
    11: CONF_OPTION_11,
    12: CONF_OPTION_12,
}


def get_mac(ip):
    arp_request = ARP(pdst=ip)
    ether = Ether(dst="ff:ff:ff:ff:ff:ff")  # Broadcast-Adresse
    packet = ether / arp_request

    responses = srp(packet, timeout=3, verbose=0)
    if not responses or len(responses) == 0:
        return None

    result = responses[0]

    if not result or len(result) == 0 or len(result[0]) < 2 or result[0][1] is None:
        return None

    return result[0][1].hwsrc


async def remove_old_entities(hass: HomeAssistant, config_entry_id: str, active_entity_ids: set) -> None:
    """Remove entities from the registry that are not in active_entity_ids."""

    entity_registry = er.async_get(hass)

    existing_entity_ids = {entity_entry.unique_id for entity_entry in entity_registry.entities.values() if entity_entry.config_entry_id == config_entry_id}

    entities_to_remove = existing_entity_ids - active_entity_ids

    _LOGGER.debug(f"Existing unique_ids: {existing_entity_ids}")
    _LOGGER.debug(f"Active unique_ids: {active_entity_ids}")
    _LOGGER.debug(f"Existing but not active unique_ids to remove: {entities_to_remove}")

    for unique_id in entities_to_remove:
        # entities_to_remove contains unique_id's and not entity_id's,
        # but we need entity-id's here to get the entity_entries
        entity_id = async_resolve_entity_id(entity_registry, unique_id)  # resolve unique_id to entity_id
        entity_entry = entity_registry.entities.get(entity_id)  # get the entity_entry by entity_id
        if entity_entry:  # check if the entity_entry exists
            entity_registry.async_remove(entity_entry.entity_id)  # remove by entity_id
            _LOGGER.debug(f"Removed old entity: {unique_id} (entity_id: {entity_entry.entity_id})")


def generate_unique_id(modbus_address: int, supported_version: int, name: str) -> str:
    """Generate a unique ID by cleaning the given name."""
    cleaned_name = re.sub(r"[^A-Za-z0-9_-]+", "_", name).strip("_")
    if cleaned_name:
        return f"{modbus_address}_{supported_version}_{cleaned_name}"
    return f"{modbus_address}_{supported_version}"  # if name consists of special chars only


async def write_modbus_value(modbus, address: int, value: int) -> bool:
    """Write a value to a Modbus register."""

    _LOGGER.debug(f"[write_modbus_value] Using Modbus client: {modbus}")

    if not await ensure_connected(modbus):
        _LOGGER.error("[write_modbus_value] Cannot connect to Modbus")
        return False

    _LOGGER.debug("[write_modbus_value] Connected to Modbus device")

    try:
        response = await modbus.write_register(address, value, device_id=1)
        if response.isError():
            _LOGGER.error(f"[write_modbus_value] Modbus error response for register {address}: {response}")
            return False

        _LOGGER.debug(f"[write_modbus_value] Successfully wrote value {value} to register {address}")
        return True

    except ConnectionException as e:
        _LOGGER.error(f"[write_modbus_value] Modbus connection error: {e}")
        return False
    except ModbusException as e:
        _LOGGER.error(f"[write_modbus_value] Modbus error: {e}")
        return False
    except Exception as e:
        _LOGGER.error(f"[write_modbus_value] Unexpected error: {e}")
        return False


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
    input_type: int,
):
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    host = entry.data.get(CONF_HOST)
    name = entry.data.get(CONF_NAME)

    if host is None:
        _LOGGER.error("Device has no address")
        return

    device_info = generate_device_info(entry, host, name)

    hkr1_name = entry.data.get(CONF_HKR1_NAME)
    hkr2_name = entry.data.get(CONF_HKR2_NAME)
    hkr3_name = entry.data.get(CONF_HKR3_NAME)

    entities = []
    active_entity_ids = set()

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
            "data_processing": register.data_processing,
            "poll_rate": register.poll_rate,
            "supported_version": register.supported_version,
            "hkr1_name": hkr1_name,
            "hkr2_name": hkr2_name,
            "hkr3_name": hkr3_name,
        }

        if entity_cls.__name__ == "SolvisSelect":
            kwargs["options"] = register.options

        if entity_cls.__name__ == "SolvisSensor":
            kwargs["unit_of_measurement"] = register.unit
            kwargs["device_class"] = register.device_class
            kwargs["state_class"] = register.state_class
            kwargs["entity_category"] = register.entity_category
            kwargs["suggested_precision"] = register.suggested_precision

        if entity_cls.__name__ == "SolvisNumber":
            kwargs["unit_of_measurement"] = register.unit
            kwargs["device_class"] = register.device_class
            kwargs["state_class"] = register.state_class
            kwargs["range_data"] = register.range_data
            kwargs["step_size"] = register.step_size
            kwargs["multiplier"] = register.multiplier

        if entity_cls.__name__ == "SolvisBinarySensor":
            kwargs["device_class"] = register.device_class
            kwargs["state_class"] = register.state_class
            kwargs["entity_category"] = register.entity_category

        entity = entity_cls(**kwargs)
        entities.append(entity)
        active_entity_ids.add(entity.unique_id)
        _LOGGER.debug(f"Erstellte unique_id: {entity.unique_id}")

    try:
        await remove_old_entities(hass, entry.entry_id, active_entity_ids)
    except Exception as e:
        _LOGGER.error(f"Error removing old entities: {e}", exc_info=True)

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
