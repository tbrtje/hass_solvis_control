"""
Tests for SolvisLeo 180 Control Init

Version: v2.1.0
"""

import pytest
import asyncio

import homeassistant.helpers.event as event

from unittest.mock import AsyncMock
from custom_components.solvis_leo.coordinator import SolvisModbusCoordinator
from custom_components.solvis_leo.const import DATA_COORDINATOR
from homeassistant.config_entries import ConfigEntry, ConfigEntryState, ConfigEntryNotReady
from custom_components.solvis_leo import (
    async_setup_entry,
    async_unload_entry,
    async_migrate_entry,
    options_update_listener,
)
from custom_components.solvis_leo.const import (
    DOMAIN,
    CONF_NAME,
    CONF_HOST,
    CONF_PORT,
    POLL_RATE_DEFAULT,
    POLL_RATE_HIGH,
    POLL_RATE_SLOW,
    CONFIG_ENTRY_MINOR_VERSION,
    CONFIG_ENTRY_VERSION,
)


def dummy_update_entry(entry, **kwargs):
    if "data" in kwargs:
        entry.data = kwargs["data"]
    for key, value in kwargs.items():
        setattr(entry, key, value)
    return True


@pytest.fixture
def extended_config_entry(mock_config_entry) -> ConfigEntry:
    mock_config_entry.entry_id = "test_entry"
    mock_config_entry.data.update(
        {
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 502,
            POLL_RATE_DEFAULT: 30,
            POLL_RATE_SLOW: 300,
            POLL_RATE_HIGH: 10,
        }
    )

    mock_config_entry.version = 1
    mock_config_entry.minor_version = 2
    mock_config_entry.options = {}

    mock_config_entry.add_update_listener = lambda listener: lambda: None
    return mock_config_entry


# # # Tests for async_setup_entry # # #


@pytest.mark.asyncio
async def test_async_setup_entry(hass, extended_config_entry, monkeypatch):
    """Test async_setup_entry sets up the integration data correctly."""

    async def dummy_forward(*args, **kwargs):
        return True

    monkeypatch.setattr(hass.config_entries, "async_forward_entry_setups", dummy_forward)
    monkeypatch.setattr(hass.config_entries, "async_update_entry", dummy_update_entry)

    fake_client = AsyncMock()
    fake_client.connect.return_value = True
    monkeypatch.setattr("custom_components.solvis_leo.create_modbus_client", lambda host, port: fake_client)

    async def dummy_first_refresh(self):
        return

    monkeypatch.setattr(SolvisModbusCoordinator, "async_config_entry_first_refresh", dummy_first_refresh)

    result = await async_setup_entry(hass, extended_config_entry)
    assert result is True
    assert DOMAIN in hass.data
    assert extended_config_entry.entry_id in hass.data[DOMAIN]


@pytest.mark.asyncio
async def test_setup_entry_missing_host(hass, extended_config_entry, monkeypatch):
    """Test async_setup_entry returns False if CONF_HOST is missing."""
    extended_config_entry.data.pop(CONF_HOST, None)

    monkeypatch.setattr(hass.config_entries, "async_forward_entry_setups", lambda *args, **kwargs: True)
    monkeypatch.setattr(hass.config_entries, "async_update_entry", dummy_update_entry)

    result = await async_setup_entry(hass, extended_config_entry)

    assert result is False


@pytest.mark.asyncio
async def test_setup_entry_missing_port(hass, extended_config_entry, monkeypatch):
    """Test async_setup_entry returns False if CONF_PORT is missing."""
    extended_config_entry.data.pop(CONF_PORT, None)

    monkeypatch.setattr(hass.config_entries, "async_forward_entry_setups", lambda *args, **kwargs: True)
    monkeypatch.setattr(hass.config_entries, "async_update_entry", dummy_update_entry)

    result = await async_setup_entry(hass, extended_config_entry)

    assert result is False


@pytest.mark.asyncio
async def test_setup_entry_connect_returns_false_raises_not_ready(hass, extended_config_entry, monkeypatch):
    """Test Modbus connect returns False triggers ConfigEntryNotReady."""
    fake_client = AsyncMock()
    fake_client.connect.return_value = False
    monkeypatch.setattr(
        "custom_components.solvis_leo.create_modbus_client",
        lambda host, port: fake_client,
    )
    with pytest.raises(ConfigEntryNotReady):
        await async_setup_entry(hass, extended_config_entry)


@pytest.mark.asyncio
async def test_setup_entry_connect_exception_raises_not_ready(hass, extended_config_entry, monkeypatch):
    """Test Modbus connect exception triggers ConfigEntryNotReady."""
    fake_client = AsyncMock()
    fake_client.connect.side_effect = Exception("Connection error")
    monkeypatch.setattr(
        "custom_components.solvis_leo.create_modbus_client",
        lambda host, port: fake_client,
    )
    with pytest.raises(ConfigEntryNotReady):
        await async_setup_entry(hass, extended_config_entry)


# # # Tests for async_unload_entry # # #


@pytest.mark.asyncio
async def test_async_unload_entry(hass, extended_config_entry, monkeypatch):
    """Test async_unload_entry."""

    hass.data.setdefault(DOMAIN, {})[extended_config_entry.entry_id] = {}

    client = AsyncMock()
    client.close = lambda: None
    extended_config_entry.runtime_data = {"modbus": client}

    async def dummy_unload(*args, **kwargs):
        return True

    monkeypatch.setattr(hass.config_entries, "async_unload_platforms", dummy_unload)
    result = await async_unload_entry(hass, extended_config_entry)

    assert result is True
    assert extended_config_entry.entry_id not in hass.data[DOMAIN]


@pytest.mark.asyncio
async def test_async_unload_entry_failure(hass, extended_config_entry, monkeypatch):
    """Test async_unload_entry does not remove the entry from hass.data if unload fails."""

    hass.data.setdefault(DOMAIN, {})[extended_config_entry.entry_id] = {}

    client = AsyncMock()
    client.close = lambda: None
    extended_config_entry.runtime_data = {"modbus": client}

    async def dummy_unload_fail(*args, **kwargs):
        return False

    monkeypatch.setattr(hass.config_entries, "async_unload_platforms", dummy_unload_fail)
    result = await async_unload_entry(hass, extended_config_entry)

    assert result is False
    assert extended_config_entry.entry_id in hass.data[DOMAIN]


@pytest.mark.asyncio
async def test_unload_entry_close_exception_removes_entry(hass, extended_config_entry, monkeypatch):
    """Test exception in close() triggers removal of entry from hass.data."""
    hass.data.setdefault(DOMAIN, {})[extended_config_entry.entry_id] = {}
    client = AsyncMock()

    def close_raise():
        raise Exception("Close failed")

    client.close = close_raise
    extended_config_entry.runtime_data = {"modbus": client}

    async def dummy_unload_platforms(entry, platforms):
        return False

    monkeypatch.setattr(hass.config_entries, "async_unload_platforms", dummy_unload_platforms)

    result = await async_unload_entry(hass, extended_config_entry)

    assert result is False
    assert extended_config_entry.entry_id not in hass.data[DOMAIN]


# # # Tests for async_migrate_entry # # #


@pytest.mark.asyncio
async def test_migrate_keeps_only_connection_and_polling_settings(hass, extended_config_entry, monkeypatch):
    """Discard every setting that does not belong to the reduced setup surface."""
    extended_config_entry.data.update(
        {
            "storage_type": "SolvisMax 957 Hybrid (82/34/796)",
            "hkr2": True,
            "hkr3_name": "Attic",
            "solar collector": True,
        }
    )
    extended_config_entry.options = {
        CONF_HOST: "192.0.2.10",
        "heat pump": False,
    }

    monkeypatch.setattr(hass.config_entries, "async_update_entry", dummy_update_entry)

    assert await async_migrate_entry(hass, extended_config_entry)

    assert extended_config_entry.version == CONFIG_ENTRY_VERSION
    assert extended_config_entry.minor_version == CONFIG_ENTRY_MINOR_VERSION
    assert extended_config_entry.data == {
        CONF_NAME: "TestDevice",
        CONF_HOST: "192.0.2.10",
        CONF_PORT: 502,
        POLL_RATE_HIGH: 10,
        POLL_RATE_DEFAULT: 30,
        POLL_RATE_SLOW: 300,
    }
    assert extended_config_entry.options == {}


# # # Tests for options_update_listener # # #


class FakeEntries:
    def __init__(self, entries):
        self.data = entries

    def __iter__(self):
        return iter(self.data)

    def __contains__(self, key):
        return key in self.data

    def values(self):
        return self.data.values()

    def get(self, key, default=None):
        return self.data.get(key, default)


@pytest.mark.asyncio
async def test_options_update_listener(hass, extended_config_entry, monkeypatch):
    """Test options_update_listener: unloads platforms, forwards entry setups and refreshes the coordinator."""
    fake_coordinator = AsyncMock()
    fake_coordinator.async_refresh = AsyncMock()
    hass.data.setdefault(DOMAIN, {})[extended_config_entry.entry_id] = {
        DATA_COORDINATOR: fake_coordinator,
        "unsub_options_update_listener": lambda: None,
    }

    extended_config_entry.state = ConfigEntryState.LOADED
    extended_config_entry.setup_lock = asyncio.Lock()

    hass.config_entries._entries = FakeEntries({extended_config_entry.entry_id: extended_config_entry})
    extended_config_entry.options = {
        CONF_HOST: "192.0.2.20",
        POLL_RATE_HIGH: 5,
        "hkr2": True,
    }

    monkeypatch.setattr(event, "async_track_time_interval", lambda hass, action, interval: lambda: None)
    monkeypatch.setattr(hass.config_entries, "async_update_entry", dummy_update_entry)

    unloaded = False

    async def dummy_unload(*args, **kwargs):
        nonlocal unloaded
        unloaded = True
        return True

    monkeypatch.setattr(hass.config_entries, "async_unload_platforms", dummy_unload)

    forward_called = False

    async def dummy_forward(*args, **kwargs):
        nonlocal forward_called
        forward_called = True
        return True

    monkeypatch.setattr(hass.config_entries, "async_forward_entry_setups", dummy_forward)

    async def dummy_reload(entry_id):
        await fake_coordinator.async_refresh()
        await hass.config_entries.async_unload_platforms(extended_config_entry, [])
        await hass.config_entries.async_forward_entry_setups(extended_config_entry, [])
        return True

    monkeypatch.setattr(hass.config_entries, "async_reload", dummy_reload)

    await options_update_listener(hass, extended_config_entry)
    assert unloaded is True
    assert forward_called is True
    fake_coordinator.async_refresh.assert_called_once()
    assert extended_config_entry.data[CONF_HOST] == "192.0.2.20"
    assert extended_config_entry.data[POLL_RATE_HIGH] == 5
    assert "hkr2" not in extended_config_entry.data
    assert extended_config_entry.options == {}
