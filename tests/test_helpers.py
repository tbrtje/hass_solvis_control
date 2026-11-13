"""
Tests for SolvisLeo 180 Control Helpers

Version: v2.1.0
"""

import asyncio
import json
import pathlib
import pytest
from custom_components.solvis_leo.utils import helpers
from tests.dummies import DummyConfigEntry, DummyEntity, DummyEntityRegistry, DummyRegister
from custom_components.solvis_leo.sensor import SolvisSensor
from homeassistant.const import EntityCategory
from custom_components.solvis_leo.const import (
    DOMAIN,
    MANUFACTURER,
    DATA_COORDINATOR,
    REGISTERS,
    SCHEDULES,
)

# # # Tests for generate_device_info # # #


def test_generate_device_info():
    data = {
        "VERSIONSC": "1.0.1",
        "VERSIONNBG": "1.0",
    }
    entry = DummyConfigEntry(data)
    host = "192.168.1.100"
    name = "TestDevice"
    info = helpers.generate_device_info(entry, host, name)

    assert isinstance(info, dict)
    assert (DOMAIN, host) in info["identifiers"]
    assert info["name"] == name
    assert info["manufacturer"] == MANUFACTURER
    assert info["model"] == "SolvisLeo 180 (SC3)"
    assert info["sw_version"] == "1.0.1"
    assert info["hw_version"] == "1.0"


# # # Tests for remove_old_entities # # #


def test_remove_old_entities(monkeypatch):
    ent1 = DummyEntity("unique_1", "entity.one", "dummy_entry")
    ent2 = DummyEntity("unique_2", "entity.two", "dummy_entry")
    registry = DummyEntityRegistry({"entity.one": ent1, "entity.two": ent2})

    monkeypatch.setattr(helpers, "er", type("DummyER", (), {"async_get": lambda hass: registry}))

    asyncio.run(helpers.remove_old_entities(hass=None, config_entry_id="dummy_entry", active_entity_ids={"unique_1"}))

    assert "entity.one" in registry.entities
    assert "entity.two" not in registry.entities


def test_active_entity_unique_ids_cover_the_complete_anlage():
    active_ids = helpers.active_entity_unique_ids()

    assert len(active_ids) == 154
    assert "33024_stored_energy_12" in active_ids
    assert "33025_warm_water_power_calculated" in active_ids
    assert "33549_warm_water_power" in active_ids
    assert "34090_hkr2_schedule" in active_ids
    assert "34090_hkr2_schedule_active" in active_ids
    assert "33045_digin_error" not in active_ids


# # # Tests for generate_unique_id # # #


def test_generate_unique_id_normal():
    uid = helpers.generate_unique_id(modbus_address=100, name="Test Sensor")

    assert uid == "100_Test_Sensor"


def test_generate_unique_id_special_chars():
    uid = helpers.generate_unique_id(modbus_address=100, name="@@@")

    assert uid == "100"


# # # Tests for process_coordinator_data # # #


def test_process_coordinator_data_none():
    available, value, attrs = helpers.process_coordinator_data(None, "test")

    assert available is False
    assert value is None
    assert attrs == {}


def test_process_coordinator_data_not_dict():
    available, value, attrs = helpers.process_coordinator_data("invalid", "test")

    assert available is False
    assert value is None


def test_process_coordinator_data_key_missing():
    data = {"other": 42}
    available, value, attrs = helpers.process_coordinator_data(data, "test")

    assert available is None
    assert value is None
    assert attrs == {}


def test_process_coordinator_data_value_none():
    data = {"test": None}
    available, value, attrs = helpers.process_coordinator_data(data, "test")

    assert available is False
    assert value is None


def test_process_coordinator_data_invalid_type():
    data = {"test": "string"}
    available, value, attrs = helpers.process_coordinator_data(data, "test")

    assert available is False
    assert value is None


def test_process_coordinator_data_error_value():
    data = {"test": -300}
    available, value, attrs = helpers.process_coordinator_data(data, "test")

    assert available is False
    assert value is None


def test_process_coordinator_data_valid():
    data = {"test": 42}
    available, value, attrs = helpers.process_coordinator_data(data, "test")

    assert available is True
    assert value == 42
    assert attrs == {"raw_value": 42}


@pytest.mark.parametrize(
    "raw, expected",
    [
        (32016, "3.20.16"),  # documented current firmware
        (10203, "1.02.03"),
        (32767, "3.27.67"),  # largest value an INT16 read returns unharmed
        (33001 - 65536, "3.30.01"),  # wrapped by the signed read
        (0, None),  # SolvisLeo: register present but not populated
        (None, None),
        (1234, None),  # too short
        ("ab.cd", None),  # right length, not a number
    ],
)
def test_parse_solvis_version(raw, expected):
    assert helpers.parse_solvis_version(raw) == expected


@pytest.mark.parametrize("lang", ["en", "de", "it", "nl"])
def test_every_register_has_a_translation(lang):
    """Guard against drift: a new register without a name shows up as its raw key in the UI."""
    platform_of = {0: "sensor", 1: "select", 2: "number", 3: "switch", 4: "binary_sensor", 5: "update"}
    path = pathlib.Path("custom_components/solvis_leo/translations") / f"{lang}.json"
    entity = json.loads(path.read_text(encoding="utf-8"))["entity"]

    # input_type 6 is raw block data; its entities are declared in SCHEDULES, not per register
    missing = sorted({(platform_of[r.input_type], r.name) for r in REGISTERS if r.input_type in platform_of and r.name not in entity.get(platform_of[r.input_type], {})})

    assert not missing, f"{lang}.json is missing names for: {missing}"


@pytest.mark.parametrize("lang", ["en", "de", "it", "nl"])
def test_every_schedule_has_translations(lang):
    """Each schedule yields a sensor and a companion binary sensor; both need a name."""
    path = pathlib.Path("custom_components/solvis_leo/translations") / f"{lang}.json"
    entity = json.loads(path.read_text(encoding="utf-8"))["entity"]

    missing = []
    for key in SCHEDULES:
        if key not in entity.get("sensor", {}):
            missing.append(("sensor", key))
        if f"{key}_active" not in entity.get("binary_sensor", {}):
            missing.append(("binary_sensor", f"{key}_active"))

    assert not missing, f"{lang}.json is missing names for: {missing}"


# # # Tests for async_setup_solvis_entities # # #


@pytest.mark.asyncio
async def test_async_setup_solvis_entities_sensor(monkeypatch):
    dummy_register = DummyRegister("Test Sensor", 101, 1, 1)
    dummy_register.unit = "°C"
    dummy_register.device_class = "temperature"
    dummy_register.state_class = "measurement"
    dummy_register.entity_category = "diagnostic"
    dummy_register.suggested_precision = 1
    dummy_register.options = None
    dummy_register.input_type = 0
    dummy_register.enabled_by_default = True

    monkeypatch.setattr(helpers, "REGISTERS", [dummy_register])

    dummy_entry = DummyConfigEntry()
    dummy_entry.entry_id = "test_entry"

    class DummyHass:
        def __init__(self):
            self.data = {DOMAIN: {dummy_entry.entry_id: {DATA_COORDINATOR: object()}}}
            self.config = type("DummyConfig", (), {"config_dir": "."})()
            self.bus = object()

    async def dummy_remove_old_entities(hass, entry_id, active_entity_ids):
        return

    monkeypatch.setattr(helpers, "remove_old_entities", dummy_remove_old_entities)
    dummy_hass = DummyHass()
    created_entities = []

    def dummy_add_entities(entities):
        created_entities.extend(entities)

    await helpers.async_setup_solvis_entities(
        dummy_hass,
        dummy_entry,
        dummy_add_entities,
        entity_cls=SolvisSensor,
        input_type=0,
    )

    assert len(created_entities) == 1
    sensor = created_entities[0]
    assert sensor.native_unit_of_measurement == "°C"
    assert sensor.device_class == "temperature"
    assert sensor.state_class == "measurement"
    assert sensor.entity_category == EntityCategory.DIAGNOSTIC
    assert sensor.suggested_display_precision == 1


# # # Tests for create_modbus_client # # #


def test_create_modbus_client_uses_sc3_defaults(monkeypatch):
    captured = {}

    class DummyClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(helpers, "AsyncModbusTcpClient", DummyClient)
    client = helpers.create_modbus_client("127.0.0.1", 502)

    assert isinstance(client, DummyClient)
    assert captured == {
        "host": "127.0.0.1",
        "port": 502,
        "timeout": 2.0,
        "retries": 1,
        "reconnect_delay": 0.5,
        "reconnect_delay_max": 5.0,
    }
