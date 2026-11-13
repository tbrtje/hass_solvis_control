"""Diagnostics describe the cached snapshot without contacting the SC3."""

import json
from unittest.mock import AsyncMock, patch

from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.solvis_leo.const import DATA_COORDINATOR, DOMAIN
from custom_components.solvis_leo.diagnostics import async_get_config_entry_diagnostics


async def test_diagnostics_do_not_read_registers(hass, dummy_coordinator, dummy_config_entry):
    coordinator = dummy_coordinator
    coordinator.data = {
        "controller_unix_time": 1755028224,
        "hkr1_schedule": tuple(range(42)),
        "warm_water_temp_s2": None,
    }
    coordinator._register_failures = {33025: 3}
    coordinator.last_update_success = False
    coordinator.last_exception = UpdateFailed("Recorded connection failure")
    coordinator.modbus.read_input_registers = AsyncMock()
    coordinator.modbus.read_holding_registers = AsyncMock()
    hass.data[DOMAIN] = {dummy_config_entry.entry_id: {DATA_COORDINATOR: coordinator}}

    with patch("pymodbus.client.AsyncModbusTcpClient", side_effect=AssertionError("Diagnostics must not open a connection")):
        result = await async_get_config_entry_diagnostics(hass, dummy_config_entry)

    coordinator.modbus.read_input_registers.assert_not_awaited()
    coordinator.modbus.read_holding_registers.assert_not_awaited()
    snapshot = result["coordinator"]
    assert snapshot["last_update_success"] is False
    assert snapshot["last_exception"] == "Recorded connection failure"
    assert snapshot["registers"]["controller_unix_time"]["value"] == 1755028224
    assert snapshot["registers"]["controller_unix_time"]["count"] == 2
    assert snapshot["registers"]["hkr1_schedule"]["value"] == list(range(42))
    assert snapshot["registers"]["hkr1_schedule"]["count"] == 42
    assert snapshot["registers"]["warm_water_temp_s2"]["failure_count"] == 3
    assert snapshot["registers"]["warm_water_temp_s2"]["value"] is None
    assert result["entry_data"]["host"] == "**REDACTED**"
    json.dumps(result, allow_nan=False)


async def test_diagnostics_without_loaded_coordinator(hass, dummy_config_entry):
    result = await async_get_config_entry_diagnostics(hass, dummy_config_entry)

    assert result["coordinator"] == {"loaded": False}
