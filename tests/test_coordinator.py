"""
Tests for Solvis Modbus Coordinator

Version: v2.1.0
"""

import struct
import pytest
from unittest.mock import MagicMock
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import UpdateFailed
from custom_components.solvis_leo.coordinator import SolvisModbusCoordinator
from pymodbus.exceptions import ConnectionException, ModbusException, ModbusIOException
from pymodbus.pdu import ExceptionResponse
from tests.dummies import DummyConfigEntry, DummyEntity, DummyEntityRegistry, DummyRegister
from tests.dummies import DummyModbusClient, DummyModbusResponse, DummyResponseObj
from custom_components.solvis_leo.const import (
    DOMAIN,
    CONF_NAME,
    CONF_HOST,
    CONF_PORT,
    POLL_RATE_DEFAULT,
    POLL_RATE_HIGH,
    POLL_RATE_SLOW,
    CONF_OPTION_1,
    CONF_OPTION_2,
    CONF_OPTION_3,
    CONF_OPTION_4,
    CONF_OPTION_5,
    CONF_OPTION_6,
    CONF_OPTION_7,
    CONF_OPTION_8,
)


@pytest.fixture
def patch_registers(monkeypatch):
    dummy_register = DummyRegister(
        name="dummy_sensor",
        address=100,
        poll_rate=0,  # DEFAULT_POLL_GROUP
        poll_time=0,  # it's polling time!
        reg=1,  # read input register
        multiplier=1.0,
        absolute_value=False,
        byte_swap=0,
    )
    monkeypatch.setattr("custom_components.solvis_leo.coordinator.REGISTERS", [dummy_register])
    return dummy_register


@pytest.mark.asyncio
async def test_async_update_data_success(dummy_coordinator, patch_registers):
    data = await dummy_coordinator._async_update_data()

    assert "dummy_sensor" in data
    assert data["dummy_sensor"] == 123


@pytest.mark.asyncio
async def test_async_update_data_skip_poll_rate(dummy_coordinator, monkeypatch):
    dummy_register = DummyRegister(
        name="slow_sensor",
        address=200,
        poll_rate=0,  # DEFAULT_POLL_GROUP
        poll_time=5,  # no polling time
        reg=1,
        multiplier=1.0,
        absolute_value=False,
        byte_swap=0,
    )
    monkeypatch.setattr("custom_components.solvis_leo.coordinator.REGISTERS", [dummy_register])
    dummy_coordinator.poll_rate_high = 2
    data = await dummy_coordinator._async_update_data()

    assert "slow_sensor" not in data
    assert dummy_register.poll_time == 3


@pytest.mark.asyncio
async def test_block_read_uint32_uses_csv_word_order(dummy_coordinator, monkeypatch):
    """32768 is the low word, 32769 the high word (order per the SC3 GLT CSV)."""
    reg = DummyRegister(name="controller_unix_time", address=32768, poll_rate=0, poll_time=0, reg=1, multiplier=1)
    reg.count = 2
    reg.datatype = "UINT32"
    monkeypatch.setattr("custom_components.solvis_leo.coordinator.REGISTERS", [reg])

    # 1755028224 = 0x689B9B00 -> low word 0x9B00, high word 0x689B
    requested = {}

    async def read(address, count=1, **kwargs):
        requested["address"], requested["count"] = address, count
        return DummyModbusResponse([0x9B00, 0x689B])

    dummy_coordinator.modbus.read_input_registers = read

    data = await dummy_coordinator._async_update_data()

    assert requested == {"address": 32768, "count": 2}  # one request, not two
    assert data["controller_unix_time"] == 1755028224  # low word first
    # die vertauschte Reihenfolge waere ein voellig anderer Zeitpunkt
    assert data["controller_unix_time"] != (0x9B00 << 16) | 0x689B


@pytest.mark.asyncio
async def test_block_read_without_datatype_keeps_raw_words(dummy_coordinator, monkeypatch):
    """A block without a combining datatype is kept as unsigned words (weekly schedules)."""
    reg = DummyRegister(name="schedule", address=34048, poll_rate=0, poll_time=0, reg=2, multiplier=1)
    reg.count = 42
    monkeypatch.setattr("custom_components.solvis_leo.coordinator.REGISTERS", [reg])

    words = list(range(42))

    async def read(address, count=1, **kwargs):
        assert count == 42
        return DummyModbusResponse(words)

    dummy_coordinator.modbus.read_holding_registers = read

    data = await dummy_coordinator._async_update_data()

    assert data["schedule"] == tuple(words)


@pytest.mark.asyncio
async def test_short_block_read_is_skipped(dummy_coordinator, monkeypatch):
    """A truncated block must not be silently interpreted as a valid value."""
    reg = DummyRegister(name="controller_unix_time", address=32768, poll_rate=0, poll_time=0, reg=1, multiplier=1)
    reg.count = 2
    reg.datatype = "UINT32"
    monkeypatch.setattr("custom_components.solvis_leo.coordinator.REGISTERS", [reg])

    async def read(address, count=1, **kwargs):
        return DummyModbusResponse([0x9B00])  # only one word came back

    dummy_coordinator.modbus.read_input_registers = read

    data = await dummy_coordinator._async_update_data()

    assert "controller_unix_time" not in data
    assert dummy_coordinator._register_failures[32768] == 1


@pytest.mark.asyncio
async def test_single_register_still_reads_count_one(dummy_coordinator, patch_registers):
    """The default path must be untouched: count=1, signed INT16."""
    requested = {}
    real = dummy_coordinator.modbus.read_input_registers

    async def read(address, count=1, **kwargs):
        requested["count"] = count
        return await real(address=address, count=count, **kwargs)

    dummy_coordinator.modbus.read_input_registers = read

    data = await dummy_coordinator._async_update_data()

    assert requested["count"] == 1
    assert data["dummy_sensor"] == 123


class IllegalAddressResponse:
    """Mimics pymodbus ExceptionResponse for code 2 (ILLEGAL DATA ADDRESS)."""

    exception_code = 2
    registers = []

    def isError(self):
        return True


@pytest.mark.asyncio
async def test_illegal_data_address_does_not_fail_update(dummy_coordinator, patch_registers, monkeypatch):
    """A register the device does not implement must not take the whole poll down."""
    good = DummyRegister(name="good_sensor", address=100, poll_rate=0, poll_time=0, reg=1, multiplier=1.0)
    missing = DummyRegister(name="missing_sensor", address=33045, poll_rate=0, poll_time=0, reg=1, multiplier=1.0)
    missing_alias = DummyRegister(name="missing_alias", address=33045, poll_rate=0, poll_time=0, reg=1, multiplier=1.0)
    monkeypatch.setattr("custom_components.solvis_leo.coordinator.REGISTERS", [missing, missing_alias, good])

    real_read = dummy_coordinator.modbus.read_input_registers

    async def read(address, count=1, **kwargs):
        if address == 33045:
            return IllegalAddressResponse()
        return await real_read(address=address, count=count, **kwargs)

    dummy_coordinator.modbus.read_input_registers = read

    data = await dummy_coordinator._async_update_data()

    assert "good_sensor" in data  # the healthy register still made it through
    assert "missing_sensor" not in data
    assert "missing_alias" not in data
    assert dummy_coordinator._register_failures[33045] == 1


@pytest.mark.asyncio
async def test_illegal_data_address_is_retried(dummy_coordinator, monkeypatch):
    """A rejected address must be requested again on its next poll."""
    missing = DummyRegister(name="missing_sensor", address=33045, poll_rate=2, poll_time=0, reg=1, multiplier=1.0)
    monkeypatch.setattr("custom_components.solvis_leo.coordinator.REGISTERS", [missing])

    attempts = []

    async def read(address, count=1, **kwargs):
        attempts.append(address)
        return IllegalAddressResponse()

    dummy_coordinator.modbus.read_input_registers = read

    await dummy_coordinator._async_update_data()
    await dummy_coordinator._async_update_data()

    assert attempts == [33045, 33045]


@pytest.mark.asyncio
async def test_other_modbus_errors_are_skipped(dummy_coordinator, monkeypatch):
    """An SC3 failure response must only cost its own register."""

    class OtherError:
        exception_code = 4  # SLAVE DEVICE FAILURE
        registers = []

        def isError(self):
            return True

    reg = DummyRegister(name="broken", address=100, poll_rate=0, poll_time=0, reg=1, multiplier=1.0)
    monkeypatch.setattr("custom_components.solvis_leo.coordinator.REGISTERS", [reg])

    async def read(address, count=1, **kwargs):
        return OtherError()

    dummy_coordinator.modbus.read_input_registers = read

    assert await dummy_coordinator._async_update_data() == {}
    assert dummy_coordinator._register_failures[100] == 1


@pytest.mark.asyncio
async def test_async_update_data_invalid_response(dummy_coordinator, monkeypatch):
    dummy_register = DummyRegister(
        name="invalid_sensor",
        address=300,
        poll_rate=0,
        poll_time=0,
        reg=1,
        multiplier=1.0,
        absolute_value=False,
        byte_swap=0,
    )
    monkeypatch.setattr("custom_components.solvis_leo.coordinator.REGISTERS", [dummy_register])

    async def invalid_read(address, count):
        class DummyResponse:
            registers = []

        return DummyResponse()

    dummy_coordinator.modbus.read_input_registers = invalid_read

    assert await dummy_coordinator._async_update_data() == {}
    assert dummy_coordinator._register_failures[300] == 1


@pytest.mark.asyncio
async def test_async_update_data_modbus_exception(dummy_coordinator, monkeypatch):
    dummy_register = DummyRegister(
        name="error_sensor",
        address=400,
        poll_rate=0,
        poll_time=0,
        reg=1,
        multiplier=1.0,
        absolute_value=False,
        byte_swap=0,
    )
    monkeypatch.setattr("custom_components.solvis_leo.coordinator.REGISTERS", [dummy_register])

    async def raise_exception(address, count):
        raise ModbusException("Test modbus error")

    dummy_coordinator.modbus.read_input_registers = raise_exception

    assert await dummy_coordinator._async_update_data() == {}
    assert dummy_coordinator._register_failures[400] == 1


@pytest.mark.asyncio
async def test_poll_rate_slow_reset(dummy_coordinator, monkeypatch):
    dummy_register = DummyRegister(
        name="slow_sensor_reset",
        address=250,
        poll_rate=1,  # SLOW_POLL_GROUP
        poll_time=0,  # reset: <= 0
        reg=1,  # Input
        multiplier=1.0,
        absolute_value=False,
        byte_swap=0,
    )
    monkeypatch.setattr("custom_components.solvis_leo.coordinator.REGISTERS", [dummy_register])
    data = await dummy_coordinator._async_update_data()
    assert "slow_sensor_reset" in data
    assert dummy_register.poll_time == dummy_coordinator.poll_rate_slow


@pytest.mark.asyncio
async def test_poll_rate_default_reset(dummy_coordinator, monkeypatch):
    dummy_register = DummyRegister(
        name="default_sensor_reset",
        address=350,
        poll_rate=0,  # DEFAULT_POLL_GROUP
        poll_time=0,  # reset: <= 0
        reg=1,  # Input
        multiplier=1.0,
        absolute_value=False,
        byte_swap=0,
    )
    monkeypatch.setattr("custom_components.solvis_leo.coordinator.REGISTERS", [dummy_register])
    data = await dummy_coordinator._async_update_data()
    assert "default_sensor_reset" in data
    assert dummy_register.poll_time == dummy_coordinator.poll_rate_default


@pytest.mark.asyncio
async def test_skip_disabled_entity(dummy_coordinator, monkeypatch):
    dummy_register = DummyRegister(
        name="disabled_sensor",
        address=500,
        poll_rate=0,
        poll_time=0,
        reg=1,
        multiplier=1.0,
        absolute_value=False,
        byte_swap=0,
    )
    monkeypatch.setattr("custom_components.solvis_leo.coordinator.REGISTERS", [dummy_register])
    dummy_registry = DummyEntityRegistry({"entity.one": DummyEntity("unique_1", "entity.one", disabled=True)})
    entity_id = f"{DOMAIN}.{dummy_register.name}"
    dummy_registry.entities = {entity_id: MagicMock(disabled=True)}
    monkeypatch.setattr(er, "async_get", lambda hass: dummy_registry)
    data = await dummy_coordinator._async_update_data()

    assert entity_id not in data


@pytest.mark.asyncio
async def test_exception_response(dummy_coordinator, monkeypatch):
    dummy_register = DummyRegister(
        name="exception_sensor",
        address=600,
        poll_rate=0,
        poll_time=0,
        reg=1,
        multiplier=1.0,
        absolute_value=False,
        byte_swap=0,
    )

    monkeypatch.setattr("custom_components.solvis_leo.coordinator.REGISTERS", [dummy_register])

    class DummyExceptionResponse:
        def isError(self):
            return True

    async def exception_response(address, count):
        return DummyExceptionResponse()

    dummy_coordinator.modbus.read_input_registers = exception_response

    assert await dummy_coordinator._async_update_data() == {}
    assert dummy_coordinator._register_failures[600] == 1


@pytest.mark.asyncio
async def test_data_conversion_error(dummy_coordinator, monkeypatch):
    dummy_register = DummyRegister(
        name="conversion_error_sensor",
        address=700,
        poll_rate=0,
        poll_time=0,
        reg=1,
        multiplier=1.0,
        absolute_value=False,
        byte_swap=0,
    )
    monkeypatch.setattr("custom_components.solvis_leo.coordinator.REGISTERS", [dummy_register])

    def raise_value_error(registers, data_type, word_order):
        raise ValueError("Conversion error")

    dummy_coordinator.modbus.convert_from_registers = raise_value_error

    assert await dummy_coordinator._async_update_data() == {}
    assert dummy_coordinator._register_failures[700] == 1


@pytest.mark.asyncio
async def test_initial_reconnect_failed_raises_updatefailed(monkeypatch, dummy_coordinator):
    # Initial ensure_connected → False → UpdateFailed
    monkeypatch.setattr("custom_components.solvis_leo.coordinator.REGISTERS", [])

    dummy_coordinator.modbus.connected = False
    dummy_coordinator.modbus.raise_on_connect = True

    with pytest.raises(UpdateFailed):
        await dummy_coordinator._async_update_data()

@pytest.mark.asyncio
async def test_lost_connection_fails_update(monkeypatch, dummy_coordinator, patch_registers):
    # Inside loop: a lost connection fails the whole update.
    calls = 0

    async def fake_ensure(client):
        nonlocal calls
        calls += 1
        return calls == 1  # 1. call ok, 2. call False

    monkeypatch.setattr("custom_components.solvis_leo.coordinator.ensure_connected", fake_ensure)
    monkeypatch.setattr("custom_components.solvis_leo.coordinator.REGISTERS", [patch_registers])

    with pytest.raises(UpdateFailed):
        await dummy_coordinator._async_update_data()
