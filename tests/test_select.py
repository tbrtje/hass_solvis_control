"""
Tests for Solvis Select Entity

Version: v2.1.0
"""

import pytest
from pytest import LogCaptureFixture
from unittest.mock import AsyncMock, patch, MagicMock
from homeassistant.exceptions import ServiceValidationError
from custom_components.solvis_leo.select import async_setup_entry
from custom_components.solvis_leo.const import CONF_HOST, DATA_COORDINATOR, DOMAIN

# # # Tests for initialization # # #


def test_select_solvis_select_initialization(dummy_solvisselect_entity):
    select_entity = dummy_solvisselect_entity()
    assert select_entity is not None
    assert select_entity._host == "test_host"
    assert select_entity._response_key == "Test Entity"
    assert select_entity.entity_registry_enabled_default is True
    assert select_entity.device_info is not None
    assert select_entity.unique_id == "1_Test_Entity"
    assert select_entity._attr_options == ("Option 1", "Option 2")
    assert select_entity.modbus_address == 1


def test_select_translation_key(dummy_solvisselect_entity):
    """Test correct setting of translation_key."""
    select_entity = dummy_solvisselect_entity(name="Test Entity", entity_id="select.test")
    assert select_entity.translation_key == "Test Entity"


# # # Tests for select_option # # #


@pytest.mark.asyncio
async def test_async_select_option_invalid_option(hass, mock_coordinator, mock_device_info, dummy_solvisselect_entity, caplog: LogCaptureFixture):
    """Test select_option with invalid (non-integer) input."""
    select_entity = dummy_solvisselect_entity(host="host", name="test", enabled_by_default=True, modbus_address=100, entity_id="select.test")
    with pytest.raises(ServiceValidationError, match="Invalid option"):
        await select_entity.async_select_option("invalid")


# # # Tests for handle_coordinator_update # # #


def test_handle_coordinator_update(dummy_solvisselect_entity):
    """Test coordinator update handling with valid data."""
    select_entity = dummy_solvisselect_entity(name="Test Entity", entity_id="select.test")
    # Simulate a valid update from the coordinator.
    select_entity.coordinator.data = {"Test Entity": 2}
    select_entity._handle_coordinator_update()
    # Check that the current option and extra attributes are set correctly.
    assert select_entity._attr_current_option == "2"
    assert select_entity._attr_extra_state_attributes["raw_value"] == 2
    assert select_entity._attr_available is True


def test_handle_coordinator_update_no_data(dummy_solvisselect_entity):
    """Test coordinator update when no data is available."""
    select_entity = dummy_solvisselect_entity(name="Test Entity", entity_id="select.test")
    select_entity.coordinator.data = None
    select_entity.hass = MagicMock(loop=MagicMock())
    select_entity._handle_coordinator_update()
    assert select_entity._attr_available is False


def test_handle_coordinator_update_invalid_data(dummy_solvisselect_entity):
    """Test coordinator update when data type is invalid."""
    select_entity = dummy_solvisselect_entity(name="Test Entity", entity_id="select.test")
    select_entity.hass = MagicMock()
    select_entity.coordinator.data = {"Test Entity": "invalid_value"}
    select_entity._handle_coordinator_update()
    assert select_entity._attr_available is False


def test_handle_coordinator_update_error_code(dummy_solvisselect_entity):
    """Test coordinator update when response is error code (-300)."""
    select_entity = dummy_solvisselect_entity(name="Test Entity", entity_id="select.test")
    select_entity.coordinator.data = {"Test Entity": -300}
    select_entity._handle_coordinator_update()
    assert select_entity._attr_available is False


def test_handle_coordinator_update_skip_slow_polling(dummy_solvisselect_entity):
    """Test skipping updates for slow polling."""
    select_entity = dummy_solvisselect_entity(name="Test Entity", entity_id="select.test")
    select_entity.coordinator.poll_rate_slow = 30
    register_mock = MagicMock()
    register_mock.poll_rate = 1
    register_mock.poll_time = 10
    with patch("custom_components.solvis_leo.utils.helpers.REGISTERS", [register_mock]):
        select_entity._handle_coordinator_update()
    assert select_entity._attr_current_option is None


def test_handle_coordinator_update_skip_standard_polling(dummy_solvisselect_entity):
    """Test skipping updates for standard polling."""
    select_entity = dummy_solvisselect_entity(name="Test Entity", entity_id="select.test")
    select_entity.coordinator.poll_rate_default = 10
    register_mock = MagicMock()
    register_mock.poll_rate = 0
    register_mock.poll_time = 5
    with patch("custom_components.solvis_leo.utils.helpers.REGISTERS", [register_mock]):
        select_entity._handle_coordinator_update()
    assert select_entity._attr_current_option is None


def test_handle_coordinator_update_no_matching_register(dummy_solvisselect_entity):
    """Test _handle_coordinator_update when no matching register is found."""
    select_entity = dummy_solvisselect_entity(name="Test Entity", entity_id="select.test")
    with patch("custom_components.solvis_leo.utils.helpers.REGISTERS", []):
        select_entity._handle_coordinator_update()
    assert select_entity._attr_available is False


def test_handle_coordinator_update_missing_poll_rate(dummy_solvisselect_entity):
    """Test _handle_coordinator_update when poll rate is missing."""
    select_entity = dummy_solvisselect_entity(name="Test Entity", entity_id="select.test")
    select_entity.coordinator.poll_rate_slow = 30
    register_mock = MagicMock()
    register_mock.poll_rate = None
    with patch("custom_components.solvis_leo.utils.helpers.REGISTERS", [register_mock]):
        select_entity._handle_coordinator_update()
    assert select_entity._attr_available is False


def test_handle_coordinator_update_unexpected_data_type(dummy_solvisselect_entity):
    """Test handling of unexpected data types in coordinator data."""
    select_entity = dummy_solvisselect_entity(name="Test Entity", entity_id="select.test")
    select_entity.coordinator.data = {"Test Entity": {"unexpected": "dict"}}

    with patch("custom_components.solvis_leo.utils.helpers._LOGGER.warning") as mock_logger:
        select_entity._handle_coordinator_update()
        mock_logger.assert_called_with("[Test Entity] Invalid response data type from coordinator: {'unexpected': 'dict'} has type <class 'dict'>")


def test_handle_coordinator_update_with_float_value(dummy_solvisselect_entity):
    """Test that float values are correctly processed in _handle_coordinator_update."""
    select_entity = dummy_solvisselect_entity(name="Test Entity", entity_id="select.test")
    select_entity.coordinator.data = {"Test Entity": 12.34}
    select_entity._handle_coordinator_update()
    assert select_entity._attr_current_option == "12.34"
    assert select_entity._attr_extra_state_attributes["raw_value"] == 12.34
    assert select_entity._attr_available is True


def test_handle_coordinator_update_with_complex_value(dummy_solvisselect_entity):
    """Test that complex numbers are correctly rejected in _handle_coordinator_update."""
    select_entity = dummy_solvisselect_entity(name="Test Entity", entity_id="select.test")
    select_entity.coordinator.data = {"Test Entity": complex(2, 3)}
    with patch("custom_components.solvis_leo.utils.helpers._LOGGER.warning") as mock_logger:
        select_entity._handle_coordinator_update()
        mock_logger.assert_called_with("[Test Entity] Invalid response data type from coordinator: (2+3j) has type <class 'complex'>")
        assert select_entity._attr_available is False


def test_handle_coordinator_update_missing_key(hass, mock_coordinator, mock_device_info, dummy_solvisselect_entity):
    """Test handling coordinator update with missing response key."""
    select_entity = dummy_solvisselect_entity(host="host", name="missing_key", enabled_by_default=True, entity_id="select.missing_key")
    mock_coordinator.data = {"other_key": 123}
    select_entity._handle_coordinator_update()
    assert select_entity._attr_available is False


# # # Tests for select_options # # #


def test_select_options(dummy_solvisselect_entity):
    """Test that options are correctly assigned."""
    select_entity = dummy_solvisselect_entity()
    assert select_entity._attr_options == ("Option 1", "Option 2")


def test_select_options_none(dummy_solvisselect_entity):
    """Test that options default to an empty list when None is passed."""
    select_entity = dummy_solvisselect_entity(options=None)
    assert select_entity._attr_options == []


# # # Tests for unique_id # # #


def test_select_unique_id(dummy_solvisselect_entity):
    """Test that unique_id is generated correctly."""
    select_entity = dummy_solvisselect_entity()
    assert select_entity.unique_id == "1_Test_Entity"


def test_select_unique_id_special_chars(dummy_solvisselect_entity):
    """Test unique_id generation with special characters in name."""
    select_entity = dummy_solvisselect_entity(name="Test! Entity@#")
    assert select_entity.unique_id == "1_Test_Entity"


def test_select_unique_id_all_special_chars(dummy_solvisselect_entity):
    """Test unique_id with name having only special chars."""
    entity = dummy_solvisselect_entity(name="!@#$%^&*()")
    assert entity.unique_id == "1"


# # # Tests for setup_entry


@pytest.mark.asyncio
async def test_select_async_setup_entry_no_host(hass, mock_config_entry):
    """Test setup entry when no host is provided."""
    mock_config_entry.data.pop(CONF_HOST, None)
    with patch("custom_components.solvis_leo.utils.helpers._LOGGER.error") as mock_logger:
        hass.data = {DOMAIN: {mock_config_entry.entry_id: {DATA_COORDINATOR: AsyncMock()}}}
        await async_setup_entry(hass, mock_config_entry, AsyncMock())
        mock_logger.assert_called_with("Device has no address")
