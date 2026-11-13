"""
Solvis Modbus Data Coordinator
"""

import asyncio
import logging
import struct
from datetime import timedelta

from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers import entity_registry as er
from pymodbus.exceptions import ConnectionException, ModbusException
from .utils.helpers import ensure_connected, generate_unique_id
from .const import (
    CONF_HOST,
    CONF_PORT,
    DOMAIN,
    DERIVATIVE_SENSORS,
    POLL_RATE_SLOW,
    POLL_RATE_DEFAULT,
    POLL_RATE_HIGH,
    REGISTERS,
    REGISTER_ADDRESSES_BY_NAME,
    SCHEDULES,
)

from .registers import DataType, EntityType, ModbusFieldConfig, PollingGroup, RegisterType

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
        self._io_lock = asyncio.Lock()
        self._poll_remaining: dict[str, int] = {}
        self._register_failures: dict[int, int] = {}
        self.host = entry.data.get(CONF_HOST)
        self.port = entry.data.get(CONF_PORT)
        self.poll_rate_default = entry.data.get(POLL_RATE_DEFAULT)
        self.poll_rate_slow = entry.data.get(POLL_RATE_SLOW)
        self.poll_rate_high = entry.data.get(POLL_RATE_HIGH)

        _LOGGER.debug("Creating Modbus client")
        self.modbus = entry.runtime_data["modbus"]

    async def _async_update_data(self):
        """Serialize complete snapshots with write/read-back transactions."""
        async with self._io_lock:
            return await self._async_poll_data()

    async def _async_poll_data(self):
        """Fetch and process the required registers."""

        _LOGGER.debug("Polling data...")
        required_names = self._required_register_names()
        # A coordinator update is a complete current snapshot, even though each
        # poll cycle reads only the registers whose cadence is due.
        parsed_data = {key: value for key, value in (self.data or {}).items() if key in required_names}
        # Inactive sources must not retain cached data, cadence or error streaks.
        # Enabling a consumer again makes its first read due on the next update.
        self._poll_remaining = {key: remaining for key, remaining in self._poll_remaining.items() if key in required_names}
        required_addresses = {register.address for register in REGISTERS if register.name in required_names}
        self._register_failures = {address: failures for address, failures in self._register_failures.items() if address in required_addresses}
        failed_addresses: set[int] = set()

        if not required_names:
            return parsed_data

        # check connection
        if not await ensure_connected(self.modbus):
            _LOGGER.error("Initial Modbus (re)connect failed, aborting update")
            raise UpdateFailed("Initial Modbus (re)connect failed")

        for register in REGISTERS:
            _LOGGER.debug(f"[{register.name} | {register.address}] Checking...")

            if register.name not in required_names:
                _LOGGER.debug("[%s | %s] Skipping register without enabled consumers", register.name, register.address)
                continue

            # Each coordinator owns its cadence; register definitions are immutable
            # metadata shared by every setup and reload.
            poll_remaining = self._poll_remaining.get(register.name, 0)

            if register.poll_rate == PollingGroup.SLOW:  # SLOW_POLL_GROUP
                if poll_remaining > self.poll_rate_high:
                    self._poll_remaining[register.name] = poll_remaining - self.poll_rate_high
                    _LOGGER.debug(f"[{register.name} | {register.address}] Skipping entity due to slow poll rate. Remaining time: {self._poll_remaining[register.name]}s")
                    continue
                self._poll_remaining[register.name] = self.poll_rate_slow

            elif register.poll_rate == PollingGroup.DEFAULT:  # DEFAULT_POLL_GROUP
                if poll_remaining > self.poll_rate_high:
                    self._poll_remaining[register.name] = poll_remaining - self.poll_rate_high
                    _LOGGER.debug(f"[{register.name} | {register.address}] Skipping entity due to standard poll rate. Remaining time: {self._poll_remaining[register.name]}s")
                    continue
                self._poll_remaining[register.name] = self.poll_rate_default

            # check connection / reconnect
            if not await ensure_connected(self.modbus):
                _LOGGER.error(f"[{register.name} | {register.address}] Cannot read: connection lost")
                raise UpdateFailed(f"[{register.name} | {register.address}] Connection lost")

            try:
                words = await self._async_read_words(register)
                parsed_data[register.name] = self._decode_words(register, words)
            except (ModbusException, OSError, TimeoutError) as err:
                if isinstance(err, ConnectionException) or not self.modbus.connected:
                    raise UpdateFailed(f"[{register.name} | {register.address}] Connection lost during read") from err
                self._record_register_failure(register, parsed_data, failed_addresses, f"Exception during read: {err}")
                continue
            except (ValueError, struct.error) as err:
                self._record_register_failure(register, parsed_data, failed_addresses, str(err))
                continue
            self._record_register_success(register.address, failed_addresses)

        _LOGGER.debug(f"Returned data: {parsed_data}")

        return parsed_data

    async def _async_read_words(self, register: ModbusFieldConfig) -> list[int]:
        """Read one declared register/block and reject incomplete responses."""
        read = self.modbus.read_input_registers if register.register == RegisterType.INPUT else self.modbus.read_holding_registers
        response = await read(address=register.address, count=register.count)
        if response is None or hasattr(response, "isError") and response.isError():
            raise ValueError(f"Modbus error while reading register: {response}")
        words = getattr(response, "registers", None)
        if not words:
            raise ValueError(f"Invalid Modbus response: {response}")
        if len(words) < register.count:
            raise ValueError(f"Short block read: expected {register.count} registers, got {len(words)}")
        return words[: register.count]

    def _decode_words(self, register: ModbusFieldConfig, words: list[int]) -> int | float | tuple[int, ...]:
        """Use the same scaling and encoding for polling and command read-back."""
        if register.count > 1:
            words = tuple(word & 0xFFFF for word in words)
            if register.datatype == DataType.UINT32:
                return round((words[0] | words[1] << 16) * register.multiplier, 2)
            return words
        raw = self.modbus.convert_from_registers(words, data_type=self.modbus.DATATYPE.INT16, word_order="big")
        if register.byte_swap:
            raw = struct.unpack("<h", struct.pack(">h", raw))[0]
        value = round(raw * register.multiplier, 2)
        return abs(value) if register.absolute_value else value

    async def async_write_register(self, name: str, raw_value: int) -> None:
        """Send one command and publish only values read back from the SC3."""
        register = next((item for item in REGISTERS if item.name == name), None)
        if register is None or register.input_type not in (EntityType.SELECT, EntityType.NUMBER, EntityType.SWITCH) or register.count != 1:
            raise ServiceValidationError(f"Register {name} is not writable")
        if type(raw_value) is not int or not -32768 <= raw_value <= 65535:
            raise ServiceValidationError("The register value must fit into 16 bits")
        word = raw_value & 0xFFFF
        if register.byte_swap:
            word = int.from_bytes(word.to_bytes(2, "little"), "big")
        async with self._io_lock:
            try:
                if not await ensure_connected(self.modbus):
                    raise HomeAssistantError("Could not connect to the SC3")
                response = await self.modbus.write_register(register.address, word, device_id=1)
            except (ModbusException, OSError, TimeoutError) as err:
                raise HomeAssistantError(f"Could not write {name}: {err}") from err
            if response is None or response.isError():
                raise HomeAssistantError(f"The SC3 rejected the write to {name}")

            data = dict(self.data or {})
            try:
                words = await self._async_read_words(register)
                required = self._required_register_names()
                for alias in REGISTERS:
                    if alias.address == register.address and alias.register == register.register and alias.name in required:
                        data[alias.name] = self._decode_words(alias, words)
            except (ModbusException, OSError, TimeoutError, ValueError, struct.error) as err:
                self._record_register_failure(register, data, set(), f"Command read-back failed: {err}")
                self._poll_remaining[name] = 0
                self.data = data
                self.async_update_listeners()
                raise HomeAssistantError(f"Value was sent to {name}, but could not be read back: {err}") from err
            self._record_register_success(register.address, set())
            # A partial update must not clear a coordinator-wide connection error
            # or postpone the next regular poll as async_set_updated_data would.
            self.data = data
            self.async_update_listeners()

    def _required_register_names(self) -> set[str]:
        """Resolve enabled consumers by stable registry identity on every update."""
        registry = er.async_get(self.hass)

        def enabled(domain: str, name: str, address: int, default: bool) -> bool:
            entity_id = registry.async_get_entity_id(domain, DOMAIN, generate_unique_id(address, name))
            entity = registry.async_get(entity_id) if entity_id is not None else None
            if entity is None or entity.config_entry_id != self.config_entry.entry_id:
                # The first refresh precedes platform setup and registration.
                return default
            return not entity.disabled

        required = {
            register.name for register in REGISTERS if register.input_type.domain is not None and enabled(register.input_type.domain, register.name, register.address, register.enabled_by_default)
        }

        for name, config in DERIVATIVE_SENSORS.items():
            source_keys = config["source_keys"]
            if enabled("sensor", name, REGISTER_ADDRESSES_BY_NAME[source_keys[0]], True):
                required.update(source_keys)

        for name in SCHEDULES:
            address = REGISTER_ADDRESSES_BY_NAME[name]
            if enabled("sensor", name, address, False) or enabled("binary_sensor", f"{name}_active", address, False):
                required.add(name)

        return required

    def is_register_available(self, address: int) -> bool:
        """Return whether an address is below the consecutive-failure threshold."""
        return self._register_failures.get(address, 0) < REGISTER_FAILURE_THRESHOLD

    def diagnostic_snapshot(self) -> dict:
        """Describe cached values and failures without opening a connection."""
        data = self.data or {}
        required = self._required_register_names()
        return {
            "loaded": True,
            "connected": self.modbus.connected,
            "last_update_success": self.last_update_success,
            "last_exception": str(self.last_exception) if self.last_exception is not None else None,
            "registers": {
                register.name: {
                    "address": register.address,
                    "register_type": register.register.name.lower(),
                    "polling_group": register.poll_rate.name.lower(),
                    "count": register.count,
                    "unit": register.unit,
                    "multiplier": register.multiplier,
                    "required": register.name in required,
                    "value": list(data[register.name]) if isinstance(data.get(register.name), tuple) else data.get(register.name),
                    "available": self.last_update_success and data.get(register.name) is not None and self.is_register_available(register.address),
                    "failure_count": self._register_failures.get(register.address, 0),
                }
                for register in REGISTERS
            },
        }

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
