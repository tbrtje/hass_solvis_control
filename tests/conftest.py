"""
Fixtures for Testing

Version: v2.1.0
"""

import pytest
import logging

from tests.dummies import DummyConfigEntry, DummyEntity, DummyEntityRegistry
from tests.dummies import DummyModbusClient
from unittest.mock import AsyncMock, MagicMock
from custom_components.solvis_leo.coordinator import SolvisModbusCoordinator
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.config_entries import ConfigEntry
from custom_components.solvis_leo.select import SolvisSelect
from custom_components.solvis_leo.sensor import SolvisSensor
from custom_components.solvis_leo.const import (
    CONF_NAME,
    CONF_HOST,
    CONF_PORT,
    POLL_RATE_SLOW,
    POLL_RATE_DEFAULT,
    POLL_RATE_HIGH,
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture(autouse=True)
def configure_logging():
    logging.basicConfig(level=logging.WARNING)

    debug_modules = [
        "custom_components.solvis_leo.config_flow",
        "custom_components.solvis_leo.utils.helpers",
        "tests.conftest",
    ]

    for module in debug_modules:
        _LOGGER = logging.getLogger(module)
        _LOGGER.setLevel(logging.DEBUG)


@pytest.fixture
def mock_coordinator():
    coordinator = AsyncMock()
    coordinator.data = {"TestEntity": 1}
    coordinator.poll_rate_slow = 30
    coordinator.poll_rate_default = 10
    coordinator.modbus = AsyncMock()
    coordinator.modbus.connect = AsyncMock()
    coordinator.modbus.write_register = AsyncMock()
    coordinator.modbus.close = MagicMock()
    coordinator.async_add_listener = lambda _callback: None
    return coordinator


@pytest.fixture
def mock_config_entry():
    entry = MagicMock(spec=ConfigEntry)
    entry.entry_id = "test_entry"
    entry.data = {
        CONF_HOST: "127.0.0.1",
        CONF_NAME: "TestDevice",
        POLL_RATE_DEFAULT: 10,
        POLL_RATE_SLOW: 30,
    }
    return entry


@pytest.fixture
def mock_entity_registry(hass):
    return er.async_get(hass)


@pytest.fixture
def mock_platform():
    platform = MagicMock()
    platform.platform_name = "solvis_leo"
    platform.domain = "select"
    return platform


@pytest.fixture
def mock_device_info():
    return DeviceInfo(
        identifiers={("solvis", "test_address")},
        connections={("mac", "00:1A:2B:3C:4D:5E")},
        name="Test Device",
        manufacturer="Solvis",
        model="Test Model",
        model_id="SM-1000",
        sw_version="1.0.0",
        hw_version="1.0",
        via_device=("solvis", "hub_identifier"),
        configuration_url="http://192.168.1.100/config",
        suggested_area="Boiler Room",
    )


@pytest.fixture
def dummy_config_entry():
    data = {
        CONF_NAME: "TestDevice",
        CONF_HOST: "127.0.0.1",
        CONF_PORT: 502,
        POLL_RATE_DEFAULT: 30,
        POLL_RATE_SLOW: 300,
        POLL_RATE_HIGH: 10,
        "VERSIONSC": "1.23.45",
        "VERSIONNBG": "5.67.89",
    }
    return DummyConfigEntry(data)


@pytest.fixture
def dummy_entity_registry():
    entities = {
        "entity.one": DummyEntity("unique_1", "entity.one"),
        "entity.two": DummyEntity("unique_2", "entity.two"),
    }
    return DummyEntityRegistry(entities)


@pytest.fixture
def dummy_coordinator(monkeypatch, dummy_config_entry, dummy_entity_registry):
    config_entry = dummy_config_entry
    dummy_modbus = DummyModbusClient()
    config_entry.runtime_data["modbus"] = dummy_modbus

    hass = MagicMock()
    monkeypatch.setattr(er, "async_get", lambda hass_instance: dummy_entity_registry)

    async def fake_executor_job(func, *args, **kwargs):
        return func(*args, **kwargs)

    hass.async_add_executor_job = fake_executor_job

    coordinator = SolvisModbusCoordinator(hass, config_entry)
    return coordinator


@pytest.fixture
def dummy_solvisselect_entity(hass, mock_coordinator, mock_device_info, mock_platform):
    def _factory(
        host="test_host",
        name="Test Entity",
        enabled_by_default=True,
        options=("Option 1", "Option 2"),
        modbus_address=1,
        platform=None,
        entity_id=None,
    ):
        entity = SolvisSelect(
            coordinator=mock_coordinator,
            device_info=mock_device_info,
            host=host,
            name=name,
            enabled_by_default=enabled_by_default,
            options=options,
            modbus_address=modbus_address,
        )
        entity.hass = hass
        entity.platform = platform if platform is not None else mock_platform
        entity.entity_id = entity_id if entity_id is not None else f"select.{name.lower().replace(' ', '_')}"
        return entity

    return _factory


@pytest.fixture
def mock_solvis_sensor(mock_coordinator, mock_device_info):
    """Fixture returning a preconfigured SolvisSensor instance."""
    return SolvisSensor(
        coordinator=mock_coordinator,
        device_info=mock_device_info,
        host="test_host",
        name="Test Number Sensor",
        unit_of_measurement="°C",
        device_class="temperature",
        state_class="measurement",
        entity_category="",
        enabled_by_default=True,
        modbus_address=1,
        suggested_precision=2,
    )
