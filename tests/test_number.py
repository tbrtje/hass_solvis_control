"""
Tests for Solvis Number Entity

Version: v2.1.0
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from custom_components.solvis_leo.number import SolvisNumber, async_setup_entry
from custom_components.solvis_leo.const import CONF_HOST, DATA_COORDINATOR, DOMAIN


@pytest.fixture
def mock_solvis_number(mock_coordinator, mock_device_info):
    """Fixture returning a preconfigured SolvisNumber instance."""
    return SolvisNumber(
        coordinator=mock_coordinator,
        device_info=mock_device_info,
        host="test_host",
        name="Test Number Sensor",
        unit_of_measurement="°C",
        device_class="temperature",
        state_class="measurement",
        enabled_by_default=True,
        range_data=(0, 100),
        step_size=0.5,
        modbus_address=1,
        multiplier=2.0,
    )


def test_number_initialization(mock_solvis_number):
    """Test initialization of the number sensor entity."""
    assert mock_solvis_number is not None
    assert mock_solvis_number._host == "test_host"
    assert mock_solvis_number._response_key == "Test Number Sensor"
    assert mock_solvis_number.native_unit_of_measurement == "°C"
    assert mock_solvis_number.device_class == "temperature"
    assert mock_solvis_number.state_class == "measurement"
    assert mock_solvis_number.native_step == 0.5
    assert mock_solvis_number.native_min_value == 0
    assert mock_solvis_number.native_max_value == 100
    assert mock_solvis_number.unique_id == "1_Test_Number_Sensor"


def test_number_initialization_default_step():
    """Test initialization when step_size is None (default native_step)."""
    number_entity = SolvisNumber(
        coordinator=AsyncMock(),
        device_info=MagicMock(),
        host="test_host",
        name="Test Number Default Step",
        unit_of_measurement="°C",
        device_class="",
        state_class="",
        enabled_by_default=True,
        range_data=None,
        step_size=None,
        modbus_address=2,
        multiplier=1.0,
    )
    # native_step should default to 1.0 if step_size is not provided
    assert number_entity.native_step == 1.0


@pytest.mark.asyncio
async def test_handle_coordinator_update_valid(mock_solvis_number):
    """Test _handle_coordinator_update when coordinator data is valid."""
    mock_solvis_number.hass = MagicMock()
    # Simulate valid update value: coordinator returns 42
    mock_solvis_number.coordinator.data = {"Test Number Sensor": 42}
    with patch("custom_components.solvis_leo.entity.process_coordinator_data", return_value=(True, 42, {"raw_value": 42})) as proc_patch:
        mock_solvis_number._handle_coordinator_update()
        proc_patch.assert_called_with({"Test Number Sensor": 42}, "Test Number Sensor")
    assert mock_solvis_number._attr_native_value == 42
    assert mock_solvis_number._attr_extra_state_attributes["raw_value"] == 42
    assert mock_solvis_number._attr_available is True


@pytest.mark.asyncio
async def test_handle_coordinator_update_not_available(mock_solvis_number):
    """Test _handle_coordinator_update when coordinator data indicates not available."""
    mock_solvis_number.hass = MagicMock()
    with patch("custom_components.solvis_leo.entity.process_coordinator_data", return_value=(False, None, {})) as proc_patch:
        mock_solvis_number._handle_coordinator_update()
        proc_patch.assert_called_with(mock_solvis_number.coordinator.data, "Test Number Sensor")
    assert mock_solvis_number._attr_extra_state_attributes == {}


@pytest.mark.asyncio
async def test_handle_coordinator_update_no_data(mock_solvis_number):
    """Test _handle_coordinator_update when coordinator data is None."""
    mock_solvis_number.hass = MagicMock(loop=MagicMock())
    mock_solvis_number.coordinator.data = None
    with patch("custom_components.solvis_leo.entity.process_coordinator_data", return_value=(None, None, {})) as proc_patch:
        mock_solvis_number._handle_coordinator_update()
        proc_patch.assert_called_with(None, "Test Number Sensor")
    assert mock_solvis_number._attr_available is False


@pytest.mark.asyncio
async def test_async_setup_entry_no_host_number(hass, mock_config_entry):
    """Test setup entry when no host is provided for number sensor."""
    mock_config_entry.data.pop(CONF_HOST, None)
    with patch("custom_components.solvis_leo.utils.helpers._LOGGER.error") as mock_logger:
        hass.data = {DOMAIN: {mock_config_entry.entry_id: {DATA_COORDINATOR: AsyncMock()}}}
        await async_setup_entry(hass, mock_config_entry, AsyncMock())
        mock_logger.assert_called_with("Device has no address")
