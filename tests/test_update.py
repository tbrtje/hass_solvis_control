"""
Tests for Solvis Update Entity

Version: v2.0.0
"""

import logging
import pytest
from unittest.mock import MagicMock, patch

from custom_components.solvis_leo.update import SolvisUpdateEntity
from custom_components.solvis_leo.const import LATEST_SW_VERSION, DOMAIN


@pytest.fixture
def mock_solvis_update_entity_firmware(mock_coordinator, mock_device_info):
    """Fixture for a firmware update entity."""
    entity = SolvisUpdateEntity(
        coordinator=mock_coordinator,
        device_info=mock_device_info,
        host="test_host",
        name="version_sc",
        modbus_address=32770,  # Corresponds to VERSIONSC
    )
    entity.hass = MagicMock()
    return entity


@pytest.fixture
def mock_solvis_update_entity_hardware(mock_coordinator, mock_device_info):
    """Fixture for a hardware update entity."""
    entity = SolvisUpdateEntity(
        coordinator=mock_coordinator,
        device_info=mock_device_info,
        host="test_host",
        name="version_nbg",
        modbus_address=32771,  # Corresponds to VERSIONNBG
    )
    entity.hass = MagicMock()
    return entity


def test_firmware_update_initialization(mock_solvis_update_entity_firmware):
    """Test initialization of the firmware update entity."""
    entity = mock_solvis_update_entity_firmware
    assert entity.title == "Controller Firmware"
    assert entity.unique_id == "32770_version_sc"


def test_hardware_update_initialization(mock_solvis_update_entity_hardware):
    """Test initialization of the hardware update entity."""
    entity = mock_solvis_update_entity_hardware
    assert entity.title == "Network Board Firmware"
    assert entity.unique_id == "32771_version_nbg"


@pytest.mark.asyncio
async def test_firmware_update_version_processing(mock_solvis_update_entity_firmware):
    """Test the firmware update entity's version processing."""
    entity = mock_solvis_update_entity_firmware
    test_value = 32016  # Represents "3.20.16"

    with (
        patch("custom_components.solvis_leo.entity.process_coordinator_data", return_value=(True, test_value, {})) as proc_patch,
        patch("custom_components.solvis_leo.update.dr.async_get") as mock_async_get,
    ):

        mock_device_registry = MagicMock()
        mock_device = MagicMock()
        mock_device.id = "test_device_id"
        mock_async_get.return_value = mock_device_registry
        mock_device_registry.async_get_device.return_value = mock_device

        entity._handle_coordinator_update()

        proc_patch.assert_called_with(entity.coordinator.data, "version_sc")
        assert entity.installed_version == "3.20.16"
        assert entity.latest_version == LATEST_SW_VERSION
        mock_device_registry.async_update_device.assert_called_once_with(mock_device.id, sw_version="3.20.16")


@pytest.mark.asyncio
async def test_hardware_update_version_processing(mock_solvis_update_entity_hardware):
    """Test the hardware update entity's version processing."""
    entity = mock_solvis_update_entity_hardware
    test_value = 10203  # Represents "1.02.03"

    with (
        patch("custom_components.solvis_leo.entity.process_coordinator_data", return_value=(True, test_value, {})) as proc_patch,
        patch("custom_components.solvis_leo.update.dr.async_get") as mock_async_get,
    ):

        mock_device_registry = MagicMock()
        mock_device = MagicMock()
        mock_device.id = "test_device_id"
        mock_async_get.return_value = mock_device_registry
        mock_device_registry.async_get_device.return_value = mock_device

        entity._handle_coordinator_update()

        proc_patch.assert_called_with(entity.coordinator.data, "version_nbg")
        assert entity.installed_version == "1.02.03"
        assert entity.latest_version == "1.02.03"  # Hardware version is its own latest
        mock_device_registry.async_update_device.assert_called_once_with(mock_device.id, hw_version="1.02.03")


@pytest.mark.asyncio
async def test_invalid_version_data(mock_solvis_update_entity_firmware):
    """Test that the entity handles invalid or incomplete version data."""
    entity = mock_solvis_update_entity_firmware

    # Test with None value
    with patch("custom_components.solvis_leo.entity.process_coordinator_data", return_value=(True, None, {})):
        entity._handle_coordinator_update()
        assert entity.installed_version is None
        assert entity.latest_version is None

    # Test with short value
    with patch("custom_components.solvis_leo.entity.process_coordinator_data", return_value=(True, 1234, {})):
        entity._handle_coordinator_update()
        assert entity.installed_version is None
        assert entity.latest_version is None


@pytest.mark.asyncio
async def test_version_zero_is_not_a_warning(mock_solvis_update_entity_firmware, caplog):
    """A SolvisLeo answers the version registers with 0; that is expected, not a warning."""
    entity = mock_solvis_update_entity_firmware

    with patch("custom_components.solvis_leo.entity.process_coordinator_data", return_value=(True, 0, {})):
        with caplog.at_level(logging.WARNING, logger="custom_components.solvis_leo.update"):
            entity._handle_coordinator_update()

    assert entity.installed_version is None
    assert entity.latest_version is None
    assert caplog.records == []


@pytest.mark.asyncio
async def test_version_int16_overflow(mock_solvis_update_entity_firmware):
    """Firmware >= 3.28.00 exceeds INT16 and arrives negative; it must still parse."""
    entity = mock_solvis_update_entity_firmware
    test_value = 33001 - 65536  # -32535, i.e. "3.30.01" wrapped by the signed read

    with (
        patch("custom_components.solvis_leo.entity.process_coordinator_data", return_value=(True, test_value, {})),
        patch("custom_components.solvis_leo.update.dr.async_get") as mock_async_get,
    ):
        mock_device_registry = MagicMock()
        mock_device = MagicMock()
        mock_device.id = "test_device_id"
        mock_async_get.return_value = mock_device_registry
        mock_device_registry.async_get_device.return_value = mock_device

        entity._handle_coordinator_update()

        assert entity.installed_version == "3.30.01"
        mock_device_registry.async_update_device.assert_called_once_with(mock_device.id, sw_version="3.30.01")


@pytest.mark.asyncio
async def test_version_boundary_still_parses(mock_solvis_update_entity_firmware):
    """32767 is the largest value a signed read returns unharmed: version 3.27.67."""
    entity = mock_solvis_update_entity_firmware

    with (
        patch("custom_components.solvis_leo.entity.process_coordinator_data", return_value=(True, 32767, {})),
        patch("custom_components.solvis_leo.update.dr.async_get") as mock_async_get,
    ):
        mock_async_get.return_value = MagicMock()
        entity._handle_coordinator_update()

        assert entity.installed_version == "3.27.67"


@pytest.mark.asyncio
async def test_version_non_numeric_rejected(mock_solvis_update_entity_firmware):
    """A 5-character non-numeric value must not be sliced into a bogus version."""
    entity = mock_solvis_update_entity_firmware

    with patch("custom_components.solvis_leo.entity.process_coordinator_data", return_value=(True, "ab.cd", {})):
        entity._handle_coordinator_update()
        assert entity.installed_version is None
        assert entity.latest_version is None


@pytest.mark.asyncio
async def test_update_value_device_none(mock_solvis_update_entity_firmware):
    """Test _update_value with device=None."""
    entity = mock_solvis_update_entity_firmware
    test_value = 12345  # "1.23.45"

    with patch("custom_components.solvis_leo.update.dr.async_get") as mock_async_get:
        mock_device_registry = MagicMock()
        mock_async_get.return_value = mock_device_registry
        mock_device_registry.async_get_device.return_value = None  # Device is None

        entity._update_value(test_value, extra_attrs={})

        mock_device_registry.async_update_device.assert_not_called()


def test_reset_value(mock_solvis_update_entity_firmware):
    """Test that _reset_value resets installed and latest version."""
    entity = mock_solvis_update_entity_firmware

    entity._attr_installed_version = "9.99.99"
    entity._attr_latest_version = "9.99.99"

    entity._reset_value()

    assert entity.installed_version is None
    assert entity.latest_version is None
