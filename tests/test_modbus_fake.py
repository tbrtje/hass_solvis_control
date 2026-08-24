"""Tests for the addressable Modbus fake used at the integration seam."""

from pathlib import Path

import pytest
from pymodbus.exceptions import ModbusIOException

from tests.modbus import AddressableModbusClient

INVENTORY = Path(__file__).parents[1] / "inventory" / "solvisleo_180_sc3.json"


@pytest.mark.asyncio
async def test_fake_answers_by_function_code_and_address() -> None:
    client = AddressableModbusClient.from_inventory(INVENTORY)

    input_response = await client.read_input_registers(address=33024, count=1)
    holding_response = await client.read_holding_registers(address=33035, count=1)

    assert input_response.registers == [495]
    assert holding_response.registers == [285]


@pytest.mark.asyncio
async def test_fake_replays_illegal_address_rejections() -> None:
    client = AddressableModbusClient.from_inventory(INVENTORY)

    response = await client.read_input_registers(address=33045, count=1)

    assert response.isError()
    assert response.exception_code == 2


@pytest.mark.asyncio
async def test_fake_can_reject_one_address() -> None:
    client = AddressableModbusClient.from_inventory(INVENTORY)
    client.reject("input", 33024)

    response = await client.read_input_registers(address=33024, count=1)

    assert response.isError()
    assert response.exception_code == 2


@pytest.mark.asyncio
async def test_fake_can_raise_a_communication_error_for_one_address() -> None:
    client = AddressableModbusClient.from_inventory(INVENTORY)
    client.fail("input", 33024)

    with pytest.raises(ModbusIOException, match="33024"):
        await client.read_input_registers(address=33024, count=1)


@pytest.mark.asyncio
async def test_fake_can_return_a_malformed_answer_for_one_address() -> None:
    client = AddressableModbusClient.from_inventory(INVENTORY)
    client.malform("input", 33024)

    response = await client.read_input_registers(address=33024, count=1)

    assert not hasattr(response, "registers")
    assert not response.isError()
