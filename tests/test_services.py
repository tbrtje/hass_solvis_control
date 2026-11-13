"""Exercise the range scan through Home Assistant's action registry."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import voluptuous as vol
import yaml
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.selector import selector
from pymodbus.exceptions import ConnectionException

from custom_components.solvis_leo import async_setup
from custom_components.solvis_leo import services
from custom_components.solvis_leo.const import DOMAIN
from tests.test_integration import setup_recorded_anlage


async def call_scan(hass, **data):
    return await hass.services.async_call(
        DOMAIN,
        services.SERVICE_SCAN_MODBUS_RANGE,
        {"start_address": 33024, "end_address": 33041, **data},
        blocking=True,
        return_response=True,
    )


async def test_service_returns_data_and_survives_entry_unload(hass, monkeypatch):
    _, entry, _ = await setup_recorded_anlage(hass)
    scan = AsyncMock(return_value={"results": [{"register": 33024}], "errors": [], "aborted": False})
    monkeypatch.setattr(services, "scan_modbus_range", scan)

    response = await call_scan(hass)

    assert response["config_entry_id"] == entry.entry_id
    assert response["results"] == [{"register": 33024}]
    scan.assert_awaited_once_with(
        host="172.16.0.73",
        port=502,
        start_address=33024,
        end_address=33041,
        register_type="both",
        slave_id=1,
        batch_size=20,
        delay=0.05,
    )
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert hass.services.has_service(DOMAIN, services.SERVICE_SCAN_MODBUS_RANGE)
    with pytest.raises(ServiceValidationError, match="No SolvisLeo 180 config entry is loaded"):
        await call_scan(hass)


async def test_service_is_available_even_without_a_working_controller(hass):
    assert await async_setup(hass, {})
    with pytest.raises(ServiceValidationError, match="No SolvisLeo 180 config entry is loaded"):
        await call_scan(hass)


def test_scan_fields_have_valid_home_assistant_selectors():
    path = Path(__file__).parents[1] / "custom_components" / DOMAIN / "services.yaml"
    fields = yaml.safe_load(path.read_text())[services.SERVICE_SCAN_MODBUS_RANGE]["fields"]
    assert fields["start_address"]["required"] is True
    assert fields["end_address"]["required"] is True
    for field in fields.values():
        assert selector(field["selector"])


async def test_service_registration_is_idempotent(hass):
    await async_setup(hass, {})
    # Repeated setup must leave one action, including its response support.
    handler = hass.services.async_services()[DOMAIN][services.SERVICE_SCAN_MODBUS_RANGE]
    await async_setup(hass, {})
    assert hass.services.async_services()[DOMAIN][services.SERVICE_SCAN_MODBUS_RANGE] is handler


@pytest.mark.parametrize(
    "data",
    [
        {"start_address": -1},
        {"end_address": 65536},
        {"start_address": 33042},
        {"batch_size": 0},
        {"batch_size": 126},
        {"slave_id": -1},
        {"slave_id": 256},
        {"delay": -0.1},
        {"delay": 6},
        {"delay": float("nan")},
        {"delay": float("inf")},
        {"register_type": "coil"},
    ],
)
async def test_invalid_scan_is_rejected_before_connecting(hass, monkeypatch, data):
    await async_setup(hass, {})
    scan = AsyncMock()
    monkeypatch.setattr(services, "scan_modbus_range", scan)
    with pytest.raises(vol.Invalid):
        await call_scan(hass, **data)
    scan.assert_not_awaited()


async def test_explicit_entry_must_be_loaded_and_belong_to_this_integration(hass):
    await setup_recorded_anlage(hass)
    with pytest.raises(ServiceValidationError, match="selected.*not loaded"):
        await call_scan(hass, config_entry_id="missing")


async def test_multiple_entries_require_an_explicit_target(hass, monkeypatch):
    _, entry, _ = await setup_recorded_anlage(hass)
    # This Anlage normally has one entry, but an accidental duplicate must not
    # silently select a different SC3 controller.
    monkeypatch.setattr(hass.config_entries, "async_loaded_entries", lambda domain: [entry, entry])
    with pytest.raises(ServiceValidationError, match="Specify config_entry_id"):
        await call_scan(hass)

    scan = AsyncMock(return_value={"results": [], "errors": []})
    monkeypatch.setattr(services, "scan_modbus_range", scan)
    assert (await call_scan(hass, config_entry_id=entry.entry_id))["config_entry_id"] == entry.entry_id


async def test_scan_connection_error_becomes_a_home_assistant_error(hass, monkeypatch):
    await setup_recorded_anlage(hass)
    monkeypatch.setattr(services, "scan_modbus_range", AsyncMock(side_effect=ConnectionException("offline")))
    with pytest.raises(HomeAssistantError, match="Could not start the Modbus scan"):
        await call_scan(hass)


async def test_concurrent_scan_is_rejected_and_lock_recovers_after_cancellation(hass, monkeypatch):
    await setup_recorded_anlage(hass)
    started = asyncio.Event()

    async def wait_for_cancellation(**kwargs):
        started.set()
        await asyncio.Future()

    monkeypatch.setattr(services, "scan_modbus_range", wait_for_cancellation)
    first = asyncio.create_task(call_scan(hass))
    await started.wait()
    try:
        with pytest.raises(ServiceValidationError, match="already running"):
            await call_scan(hass)
    finally:
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first

    monkeypatch.setattr(services, "scan_modbus_range", AsyncMock(return_value={"results": []}))
    assert (await call_scan(hass))["results"] == []
