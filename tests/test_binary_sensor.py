"""
Tests for Solvis Binary Sensor Entity

Version: v2.1.0
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from homeassistant.core import HomeAssistant
from custom_components.solvis_leo.binary_sensor import SolvisBinarySensor, async_setup_entry, _LOGGER
from custom_components.solvis_leo.const import CONF_HOST, CONF_NAME, DATA_COORDINATOR, DOMAIN, POLL_RATE_DEFAULT, POLL_RATE_SLOW
from homeassistant.helpers.device_registry import DeviceInfo


@pytest.fixture
def mock_solvis_binary_sensor(mock_coordinator, mock_device_info):
    """Fixture returning a preconfigured SolvisBinarySensor instance."""
    sensor = SolvisBinarySensor(
        coordinator=mock_coordinator,
        device_info=mock_device_info,
        host="test_host",
        name="Test Binary Sensor",
        device_class="",
        state_class="",
        entity_category=None,
        enabled_by_default=True,
        data_processing=0,
        poll_rate=False,
        modbus_address=1,
    )
    return sensor


def test_sensor_initialization(mock_solvis_binary_sensor):
    """Test initialization of the binary sensor entity."""
    assert mock_solvis_binary_sensor is not None
    assert mock_solvis_binary_sensor._host == "test_host"
    assert mock_solvis_binary_sensor._response_key == "Test Binary Sensor"
    assert mock_solvis_binary_sensor.entity_registry_enabled_default is True
    assert mock_solvis_binary_sensor.device_info is not None
    assert mock_solvis_binary_sensor.unique_id == "1_Test_Binary_Sensor"


@pytest.mark.asyncio
async def test_handle_coordinator_update_valid_on(mock_solvis_binary_sensor):
    """Test update when binary sensor should be on."""
    mock_solvis_binary_sensor.hass = MagicMock()

    # Simulate a valid update value causing sensor to be on
    mock_solvis_binary_sensor.coordinator.data = {"Test Binary Sensor": 1}
    mock_solvis_binary_sensor.data_processing = 0
    mock_solvis_binary_sensor._handle_coordinator_update()
    assert mock_solvis_binary_sensor._attr_is_on is True
    assert mock_solvis_binary_sensor._attr_extra_state_attributes["unprocessed_value"] == 1


@pytest.mark.asyncio
async def test_handle_coordinator_update_valid_off(mock_solvis_binary_sensor):
    """Test update when binary sensor should be off."""
    mock_solvis_binary_sensor.hass = MagicMock()
    mock_solvis_binary_sensor.coordinator.data = {"Test Binary Sensor": 0}
    mock_solvis_binary_sensor.data_processing = 0
    mock_solvis_binary_sensor._handle_coordinator_update()

    assert mock_solvis_binary_sensor._attr_is_on is False
    assert mock_solvis_binary_sensor._attr_extra_state_attributes["unprocessed_value"] == 0


@pytest.mark.asyncio
async def test_handle_coordinator_update_invalid_data(mock_solvis_binary_sensor):
    """Test update when coordinator data type is invalid."""
    mock_solvis_binary_sensor.hass = MagicMock()
    mock_solvis_binary_sensor.coordinator.data = {"Test Binary Sensor": {"unexpected": "dict"}}

    with patch("custom_components.solvis_leo.utils.helpers._LOGGER.warning") as mock_logger:
        mock_solvis_binary_sensor._handle_coordinator_update()
        mock_logger.assert_called()
    assert mock_solvis_binary_sensor._attr_available is False


@pytest.mark.asyncio
async def test_handle_coordinator_update_no_data(mock_solvis_binary_sensor):
    """Test update when no coordinator data is available."""
    mock_solvis_binary_sensor.hass = MagicMock(loop=MagicMock())
    mock_solvis_binary_sensor.coordinator.data = None
    mock_solvis_binary_sensor._handle_coordinator_update()

    assert mock_solvis_binary_sensor._attr_available is False


def _coordinator_mock():
    """AsyncMock coordinator whose async_add_listener stays synchronous, as in real HA."""
    coordinator = AsyncMock()
    coordinator.async_add_listener = MagicMock()
    coordinator.data = {}
    return coordinator


@pytest.mark.asyncio
async def test_async_setup_entry_no_host_binary_sensor(hass, mock_config_entry):
    """Test setup entry when no host is provided for binary sensor."""
    mock_config_entry.data.pop(CONF_HOST, None)
    with patch("custom_components.solvis_leo.utils.helpers._LOGGER.error") as mock_logger:
        hass.data = {DOMAIN: {mock_config_entry.entry_id: {DATA_COORDINATOR: _coordinator_mock()}}}
        await async_setup_entry(hass, mock_config_entry, AsyncMock())
        mock_logger.assert_called_with("Device has no address")
