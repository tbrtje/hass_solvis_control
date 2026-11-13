"""Commands report failures and publish the SC3 read-back immediately."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import UpdateFailed
from pymodbus.exceptions import ConnectionException

from tests.modbus import FakeModbusResponse
from tests.test_integration import setup_recorded_anlage


@pytest.mark.parametrize(
    ("domain", "service", "entity_id", "data", "address", "word", "expected"),
    [
        ("number", "set_value", "number.solvisleo_180_warm_water_target_temp", {"value": 48}, 2305, 48, "48"),
        ("number", "set_value", "number.solvisleo_180_hkr1_room_temp", {"value": 21.4}, 34304, 214, "21.4"),
        ("select", "select_option", "select.solvisleo_180_hkr_1_operating_mode", {"option": "3"}, 2818, 3, "3"),
        ("switch", "turn_on", "switch.solvisleo_180_warm_water_reheat_start", {}, 2322, 1, "on"),
    ],
)
async def test_command_publishes_read_back_without_waiting_for_polling(hass, domain, service, entity_id, data, address, word, expected):
    client, _, _ = await setup_recorded_anlage(hass, poll_rate_slow=300)
    reads_before = client.request_count("holding", address)
    healthy_reads = client.request_count("input", 33025)

    await hass.services.async_call(domain, service, {"entity_id": entity_id, **data}, blocking=True)
    await hass.async_block_till_done()

    assert client.writes == [(address, word, 1)]
    assert client.request_count("holding", address) == reads_before + 1
    assert client.request_count("input", 33025) == healthy_reads
    assert hass.states.get(entity_id).state == expected


@pytest.mark.parametrize("response", [None, FakeModbusResponse([], exception_code=2), ConnectionException("Offline")])
@pytest.mark.parametrize(
    ("domain", "service", "entity_id", "data", "address"),
    [
        ("number", "set_value", "number.solvisleo_180_warm_water_target_temp", {"value": 48}, 2305),
        ("select", "select_option", "select.solvisleo_180_hkr_1_operating_mode", {"option": "3"}, 2818),
        ("switch", "turn_on", "switch.solvisleo_180_warm_water_reheat_start", {}, 2322),
    ],
)
async def test_failed_write_raises_in_home_assistant(hass, response, domain, service, entity_id, data, address):
    client, _, _ = await setup_recorded_anlage(hass)
    previous = hass.states.get(entity_id).state
    read_count = client.request_count("holding", address)
    writer = AsyncMock(side_effect=response) if isinstance(response, Exception) else AsyncMock(return_value=response)

    with patch.object(client, "write_register", writer), pytest.raises(HomeAssistantError):
        await hass.services.async_call(domain, service, {"entity_id": entity_id, **data}, blocking=True)

    assert hass.states.get(entity_id).state == previous
    assert client.request_count("holding", address) == read_count


async def test_read_back_failure_does_not_retry_the_write(hass):
    client, _, coordinator = await setup_recorded_anlage(hass, poll_rate_slow=300)
    entity_id = "select.solvisleo_180_hkr_1_operating_mode"
    previous = hass.states.get(entity_id).state
    with patch.object(client, "read_holding_registers", AsyncMock(side_effect=TimeoutError("Read-back timeout"))):
        with pytest.raises(HomeAssistantError, match="sent.*read back"):
            await hass.services.async_call("select", "select_option", {"entity_id": entity_id, "option": "3"}, blocking=True)

    assert client.writes == [(2818, 3, 1)]
    assert hass.states.get(entity_id).state == previous
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "3"
    assert len(client.writes) == 1


async def test_actual_controller_value_is_published_for_shared_register(hass):
    client, _, coordinator = await setup_recorded_anlage(hass)
    writer = client.write_register

    async def write_adjusted(address, value, **kwargs):
        response = await writer(address, value, **kwargs)
        client.set_registers("holding", address, [215])
        return response

    with patch.object(client, "write_register", write_adjusted):
        await coordinator.async_write_register("hkr1_room_temp_write", 220)
    await hass.async_block_till_done()

    assert hass.states.get("number.solvisleo_180_hkr1_room_temp").state == "21.5"
    assert hass.states.get("sensor.solvisleo_180_hkr1_room_temp").state == "21.5"


async def test_partial_read_back_does_not_clear_a_coordinator_error(hass):
    _, _, coordinator = await setup_recorded_anlage(hass)
    error = UpdateFailed("Earlier poll failed")
    coordinator.async_set_update_error(error)

    await coordinator.async_write_register("hkr1_operating_mode", 3)
    await hass.async_block_till_done()

    assert coordinator.last_update_success is False
    assert coordinator.last_exception is error
    assert coordinator.data["hkr1_operating_mode"] == 3
    assert hass.states.get("sensor.solvisleo_180_hot_water_temperature_s2").state == "unavailable"


async def test_poll_and_write_cannot_overwrite_each_others_snapshot(hass):
    client, _, coordinator = await setup_recorded_anlage(hass)
    started = asyncio.Event()
    release = asyncio.Event()
    requested = asyncio.Event()
    reader = client.read_holding_registers

    async def pause_poll(address, count):
        if address == 2818 and not started.is_set():
            started.set()
            await release.wait()
        return await reader(address, count)

    async def write():
        requested.set()
        await coordinator.async_write_register("hkr1_operating_mode", 3)

    async with asyncio.timeout(3):
        with patch.object(client, "read_holding_registers", pause_poll):
            poll_task = asyncio.create_task(coordinator.async_refresh())
            await started.wait()
            write_task = asyncio.create_task(write())
            await requested.wait()
            assert client.writes == []
            release.set()
            await asyncio.gather(poll_task, write_task)

    assert hass.states.get("select.solvisleo_180_hkr_1_operating_mode").state == "3"
