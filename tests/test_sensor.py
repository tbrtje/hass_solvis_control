"""
Tests for Solvis Sensor Entity

Version: v2.1.0
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from custom_components.solvis_leo.sensor import SolvisSensor, async_setup_entry, _LOGGER, SolvisDerivativeSensor
from custom_components.solvis_leo.const import CONF_HOST, CONF_NAME, DATA_COORDINATOR, DOMAIN
from custom_components.solvis_leo.coordinator import SolvisModbusCoordinator
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers import issue_registry as ir


def test_sensor_initialization(mock_solvis_sensor):
    """Test initialization of the sensor entity."""
    assert mock_solvis_sensor is not None
    assert mock_solvis_sensor._host == "test_host"
    assert mock_solvis_sensor._response_key == "Test Number Sensor"
    assert mock_solvis_sensor.native_unit_of_measurement == "°C"
    assert mock_solvis_sensor.device_class == "temperature"
    assert mock_solvis_sensor.state_class == "measurement"
    assert mock_solvis_sensor.suggested_display_precision == 2
    assert mock_solvis_sensor.unique_id == "1_Test_Number_Sensor"


@pytest.mark.asyncio
async def test_handle_coordinator_update_default(mock_solvis_sensor):
    """Test _handle_coordinator_update passes through an ordinary sensor value."""
    mock_solvis_sensor.hass = MagicMock()
    mock_solvis_sensor.data_processing = 99
    test_value = 123
    with patch("custom_components.solvis_leo.entity.process_coordinator_data", return_value=(True, test_value, {"raw_value": test_value})):
        mock_solvis_sensor._handle_coordinator_update()
    assert mock_solvis_sensor._attr_native_value == test_value


@pytest.mark.asyncio
async def test_async_setup_entry_no_host_sensor(hass, mock_config_entry):
    """Test setup entry when no host is provided for sensor."""
    mock_config_entry.data.pop(CONF_HOST, None)
    with patch("custom_components.solvis_leo.utils.helpers._LOGGER.error") as mock_logger:
        hass.data = {DOMAIN: {mock_config_entry.entry_id: {DATA_COORDINATOR: AsyncMock()}}}
        await async_setup_entry(hass, mock_config_entry, AsyncMock())
        mock_logger.assert_called_with("Device has no address")


@pytest.mark.asyncio
async def test_handle_coordinator_update_not_available_extra_attrs(mock_solvis_sensor):
    """Test that when coordinator data is not available, extra state attributes are set to an empty dict."""
    mock_solvis_sensor.hass = MagicMock()
    with patch("custom_components.solvis_leo.entity.process_coordinator_data", return_value=(False, None, {"raw_value": None})):
        mock_solvis_sensor._handle_coordinator_update()
    assert mock_solvis_sensor._attr_extra_state_attributes == {}


def test_compute_stored_energy_12_uses_the_two_leo_storage_zones(mock_coordinator):
    t1, t2, t3 = 50.0, 40.0, 30.0

    rho = 1.0
    c = 4.186
    e1 = 80 * rho * c * ((t1 + t2) / 2 - 12)
    e2 = 100 * rho * c * ((t2 + t3) / 2 - 12)
    expected_kwh = (e1 + e2) / 3600

    dummy_device_info = DeviceInfo(identifiers={("solvis", "dummy")})
    sensor = SolvisDerivativeSensor(
        coordinator=mock_coordinator,
        device_info=dummy_device_info,
        host="dummy_host",
        name="test_energy",
        source_keys=["warm1", "warm2", "warm3"],
        unit="kWh",
        device_class=None,
        state_class=None,
        entity_category=None,
        suggested_display_precision=2,
        compute_mode="stored_energy_12",
    )

    mock_coordinator.data = {
        "warm1": t1,
        "warm2": t2,
        "warm3": t3,
    }

    result = sensor._compute_stored_energy_12([t1, t2, t3])

    assert pytest.approx(result, rel=1e-6) == expected_kwh


def test_compute_stored_energy_12_sensor_count_mismatch(mock_coordinator):
    """The fixed two-zone geometry requires the three delimiting Fühler."""
    dummy_device_info = DeviceInfo(identifiers={("solvis", "dummy")})
    sensor = SolvisDerivativeSensor(
        coordinator=mock_coordinator,
        device_info=dummy_device_info,
        host="dummy_host",
        name="test_energy",
        source_keys=["a", "b"],
        unit="kWh",
        device_class=None,
        state_class=None,
        entity_category=None,
        suggested_display_precision=2,
        compute_mode="stored_energy_12",
    )

    assert sensor._compute_stored_energy_12([20.0, 22.0]) == 0.0


def test_compute_combined_fallback(monkeypatch, mock_coordinator):
    dummy_device_info = DeviceInfo(identifiers={("solvis", "dummy")})

    sensor = SolvisDerivativeSensor(
        coordinator=mock_coordinator,
        device_info=dummy_device_info,
        host="h",
        name="c",
        source_keys=["x", "y"],
        unit="kWh",
        device_class=None,
        state_class=None,
        entity_category=None,
        suggested_display_precision=2,
        compute_mode=None,
    )

    mock_coordinator.data = {"x": 2.5, "y": 3.5}
    result = sensor._compute_combined()
    assert result == 6.0


def test_compute_combined_missing_key(monkeypatch, mock_coordinator):
    dummy_device_info = DeviceInfo(identifiers={("solvis", "dummy")})
    sensor = SolvisDerivativeSensor(
        coordinator=mock_coordinator,
        device_info=dummy_device_info,
        host="h",
        name="c",
        source_keys=["x", "z"],
        unit="kWh",
        device_class=None,
        state_class=None,
        entity_category=None,
        suggested_display_precision=2,
        compute_mode=None,
    )

    mock_coordinator.data = {"x": 2.5}
    result = sensor._compute_combined()
    assert result is None


@pytest.mark.asyncio
async def test_async_update_from_coordinator_sets_value(monkeypatch):
    coord = SolvisModbusCoordinator.__new__(SolvisModbusCoordinator)
    coord.async_add_listener = lambda _callback: None
    coord.data = {
        "t1": 20.0,
        "t2": 22.0,
        "t3": 24.0,
    }

    dummy_device_info = DeviceInfo(identifiers={("solvis", "dummy")})
    sensor = SolvisDerivativeSensor(
        coordinator=coord,
        device_info=dummy_device_info,
        host="h",
        name="c",
        source_keys=["t1", "t2", "t3"],
        unit="kWh",
        device_class=None,
        state_class=None,
        entity_category=None,
        suggested_display_precision=3,
        compute_mode="stored_energy_12",
    )
    sensor.hass = MagicMock()
    sensor.async_write_ha_state = lambda: None

    assert sensor._attr_native_value is None

    sensor._async_update_from_coordinator()

    expected_raw = {"t1": 20.0, "t2": 22.0, "t3": 24.0}
    assert isinstance(sensor._attr_native_value, float)
    assert "raw_values" in sensor._attr_extra_state_attributes
    assert sensor._attr_extra_state_attributes["raw_values"] == expected_raw


@pytest.mark.asyncio
async def test_async_update_from_coordinator_missing(monkeypatch):
    coord = SolvisModbusCoordinator.__new__(SolvisModbusCoordinator)
    coord.async_add_listener = lambda _callback: None
    coord.data = {"t1": 20.0}

    dummy_device_info = DeviceInfo(identifiers={("solvis", "dummy")})
    sensor = SolvisDerivativeSensor(
        coordinator=coord,
        device_info=dummy_device_info,
        host="h",
        name="c",
        source_keys=["t1", "t2", "t3"],
        unit="kWh",
        device_class=None,
        state_class=None,
        entity_category=None,
        suggested_display_precision=3,
        compute_mode="stored_energy_12",
    )
    sensor.hass = MagicMock()
    sensor.async_write_ha_state = lambda: None

    sensor._attr_native_value = 99.9
    sensor._attr_extra_state_attributes = {"foo": "bar"}

    sensor._async_update_from_coordinator()
    assert sensor._attr_native_value is None
    assert sensor._attr_extra_state_attributes == {}


def test_handle_coordinator_update_noop(monkeypatch, mock_coordinator):
    coord = mock_coordinator
    coord.data = {"any": 1.0}

    dummy_device_info = DeviceInfo(identifiers={("solvis", "dummy")})
    sensor = SolvisDerivativeSensor(
        coordinator=coord,
        device_info=dummy_device_info,
        host="h",
        name="c",
        source_keys=["any"],
        unit="kWh",
        device_class=None,
        state_class=None,
        entity_category=None,
        suggested_display_precision=2,
        compute_mode=None,
    )

    sensor._attr_native_value = 42.0
    sensor._attr_extra_state_attributes = {"foo": "bar"}

    sensor._handle_coordinator_update()

    assert sensor._attr_native_value == 42.0
    assert sensor._attr_extra_state_attributes == {"foo": "bar"}
