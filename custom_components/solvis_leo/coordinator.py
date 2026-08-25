"""
Solvis Modbus Data Coordinator
"""

import logging
import struct
from datetime import timedelta

import pymodbus
from pymodbus.client import AsyncModbusTcpClient
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers import entity_registry as er
from pymodbus.exceptions import ConnectionException, ModbusException, ModbusIOException
from .utils.helpers import ensure_connected
from .const import (
    CONF_HOST,
    CONF_PORT,
    DOMAIN,
    POLL_RATE_SLOW,
    POLL_RATE_DEFAULT,
    POLL_RATE_HIGH,
    REGISTERS,
)

_LOGGER = logging.getLogger(__name__)

REGISTER_FAILURE_THRESHOLD = 3


class SolvisModbusCoordinator(DataUpdateCoordinator):
    """Coordinates data updates from a Solvis device via Modbus."""

    def __init__(self, hass, entry):
        """Initializes the Solvis Modbus data coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=entry.data.get(POLL_RATE_HIGH)),
        )
        self.config_entry = entry  # !
        self._register_failures: dict[int, int] = {}
        self.host = entry.data.get(CONF_HOST)
        self.port = entry.data.get(CONF_PORT)
        self.poll_rate_default = entry.data.get(POLL_RATE_DEFAULT)
        self.poll_rate_slow = entry.data.get(POLL_RATE_SLOW)
        self.poll_rate_high = entry.data.get(POLL_RATE_HIGH)

        _LOGGER.debug("Creating Modbus client")
        self.modbus = entry.runtime_data["modbus"]

    async def _async_update_data(self):
        """Fetches and processes data from the Solvis device."""

        _LOGGER.debug("Polling data...")
        parsed_data = {}
        failed_addresses: set[int] = set()

        # check connection
        if not await ensure_connected(self.modbus):
            _LOGGER.error("Initial Modbus (re)connect failed, aborting update")
            raise UpdateFailed("Initial Modbus (re)connect failed")

        for register in REGISTERS:
            _LOGGER.debug(f"[{register.name} | {register.address}] Checking...")

            # Calculation for passing entites, which are in SLOW_POLL_GROUP or STANDARD_POLL_GROUP
            if register.poll_rate == 1:  # SLOW_POLL_GROUP
                if register.poll_time > 0:
                    register.poll_time -= self.poll_rate_high  # formerly: self.poll_rate_default
                    _LOGGER.debug(f"[{register.name} | {register.address}] Skipping entity due to slow poll rate. Remaining time: {register.poll_time}s")
                    continue
                else:  # register.poll_time <= 0:
                    register.poll_time = self.poll_rate_slow

            elif register.poll_rate == 0:  # DEFAULT_POLL_GROUP
                if register.poll_time > 0:
                    register.poll_time -= self.poll_rate_high
                    _LOGGER.debug(f"[{register.name} | {register.address}] Skipping entity due to standard poll rate. Remaining time: {register.poll_time}s")
                    continue
                else:  # if register.poll_time <= 0:
                    register.poll_time = self.poll_rate_default

            entity_id = f"{DOMAIN}.{register.name}"
            entity_registry = er.async_get(self.hass)
            entity_entry = entity_registry.entities.get(entity_id)

            # skip disabled entities
            if entity_entry and entity_entry.disabled:
                _LOGGER.debug(f"[{register.name} | {register.address}] Skipping disabled entity")
                continue

            # check connection / reconnect
            if not await ensure_connected(self.modbus):
                _LOGGER.error(f"[{register.name} | {register.address}] Cannot read: connection lost")
                raise UpdateFailed(f"[{register.name} | {register.address}] Connection lost")

            # READ
            try:
                # read input registers
                if register.register == 1:
                    _LOGGER.debug(f"[{register.name} | {register.address}] Reading {register.count} input register(s)...")
                    result = await self.modbus.read_input_registers(address=register.address, count=register.count)

                # read holding registers
                else:
                    _LOGGER.debug(f"[{register.name} | {register.address}] Reading {register.count} holding register(s)...")
                    result = await self.modbus.read_holding_registers(address=register.address, count=register.count)

            except (ConnectionException, ModbusIOException, ModbusException) as err:
                if isinstance(err, ConnectionException) or not self.modbus.connected:
                    _LOGGER.error(f"[{register.name} | {register.address}] Connection lost during read: {err}")
                    raise UpdateFailed(f"[{register.name} | {register.address}] Connection lost during read") from err
                self._record_register_failure(register, parsed_data, failed_addresses, f"Exception during read: {err}")
                continue

            # check for error response
            if not result or hasattr(result, "isError") and result.isError():
                self._record_register_failure(register, parsed_data, failed_addresses, f"Modbus error while reading register: {result}")
                continue

            # check for invalid results
            if not hasattr(result, "registers") or not result.registers:
                self._record_register_failure(register, parsed_data, failed_addresses, f"Invalid Modbus response: {result}")
                continue

            if len(result.registers) < register.count:
                self._record_register_failure(
                    register,
                    parsed_data,
                    failed_addresses,
                    f"Short block read: expected {register.count} registers, got {len(result.registers)}",
                )
                continue

            # conversion
            try:
                if register.count > 1:
                    # pymodbus hands back raw unsigned words
                    words = [word & 0xFFFF for word in result.registers[: register.count]]

                    if register.datatype == "UINT32":
                        # low word first, as documented in the SC3 GLT CSV
                        raw_value = words[0] | (words[1] << 16)
                        _LOGGER.debug(f"[{register.name} | {register.address}] UINT32 from words {words}: {raw_value}")
                        parsed_data[register.name] = round(raw_value * register.multiplier, 2)
                    else:
                        _LOGGER.debug(f"[{register.name} | {register.address}] Block of {len(words)} words: {words}")
                        parsed_data[register.name] = tuple(words)

                    self._record_register_success(register.address, failed_addresses)
                    continue

                data_from_register = self.modbus.convert_from_registers(registers=result.registers, data_type=self.modbus.DATATYPE.INT16, word_order="big")

                if register.byte_swap == 1:  # little endian
                    _LOGGER.debug(f"[{register.name} | {register.address}] Converting to Little Endian: {data_from_register}")
                    data_from_register = struct.unpack("<h", struct.pack(">h", data_from_register))[0]

                _LOGGER.debug(f"[{register.name} | {register.address}] Raw value: {data_from_register}")

                value = round(data_from_register * register.multiplier, 2)
                parsed_data[register.name] = abs(value) if register.absolute_value else value

            except (struct.error, ValueError) as err:
                self._record_register_failure(register, parsed_data, failed_addresses, f"Data conversion error: {err}")
                continue

            self._record_register_success(register.address, failed_addresses)

        _LOGGER.debug(f"Returned data: {parsed_data}")

        return parsed_data

    def is_register_available(self, address: int) -> bool:
        """Return whether an address is below the consecutive-failure threshold."""
        return self._register_failures.get(address, 0) < REGISTER_FAILURE_THRESHOLD

    def _record_register_failure(self, register, parsed_data: dict, failed_addresses: set[int], message: str) -> None:
        """Record one failed attempt without failing the whole poll cycle."""
        first_failure_for_address_this_cycle = register.address not in failed_addresses
        if first_failure_for_address_this_cycle:
            self._register_failures[register.address] = self._register_failures.get(register.address, 0) + 1
            failed_addresses.add(register.address)
        failures = self._register_failures[register.address]
        emit_failure = _LOGGER.warning if failures == 1 and first_failure_for_address_this_cycle else _LOGGER.debug
        emit_failure(
            "[%s | %s] %s; skipping register for this cycle (consecutive failures: %s)",
            register.name,
            register.address,
            message,
            failures,
        )
        if failures >= REGISTER_FAILURE_THRESHOLD:
            parsed_data[register.name] = None

    def _record_register_success(self, address: int, failed_addresses: set[int]) -> None:
        """Reset an address after any successful read in the current cycle."""
        self._register_failures.pop(address, None)
        failed_addresses.discard(address)
