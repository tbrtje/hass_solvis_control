"""Integration-level seam for the SolvisLeo 180 installation."""

import logging
from pathlib import Path
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.helpers import entity_registry as er

from custom_components.solvis_leo.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    DATA_COORDINATOR,
    DOMAIN,
    POLL_RATE_DEFAULT,
    POLL_RATE_HIGH,
    POLL_RATE_SLOW,
)
from tests.modbus import AddressableModbusClient

ROOT = Path(__file__).parents[1]

# The recorded inventory rejects GLT addresses 33045 and 33299, so their former
# digin_error and analog_out_o6 entities are deliberately absent here.
EXPECTED_ENTITY_IDS = {
    "binary_sensor.solvisleo_180_heizstab_status_a12",
    "binary_sensor.solvisleo_180_circulation_pump_a1",
    "binary_sensor.solvisleo_180_circulation_schedule_active",
    "binary_sensor.solvisleo_180_eco_schedule_active",
    "binary_sensor.solvisleo_180_heat_pump_changeover_valve_a14",
    "binary_sensor.solvisleo_180_heat_pump_charging_pump_a2",
    "binary_sensor.solvisleo_180_heizstab_stage_2_3_a13",
    "binary_sensor.solvisleo_180_hkr2_mixer_heating_circuit_closed_a11",
    "binary_sensor.solvisleo_180_hkr2_mixer_heating_circuit_open_a10",
    "binary_sensor.solvisleo_180_hkr2_pump_a4",
    "binary_sensor.solvisleo_180_hkr3_mixer_heating_circuit_closed_a7",
    "binary_sensor.solvisleo_180_hkr3_mixer_heating_circuit_open_a6",
    "binary_sensor.solvisleo_180_hkr3_pump_a5",
    "binary_sensor.solvisleo_180_hkr1_mixer_heating_circuit_closed_a9",
    "binary_sensor.solvisleo_180_hkr1_mixer_heating_circuit_open_a8",
    "binary_sensor.solvisleo_180_hkr1_pump_a3",
    "binary_sensor.solvisleo_180_hkr1_schedule_active",
    "binary_sensor.solvisleo_180_hkr2_schedule_active",
    "binary_sensor.solvisleo_180_hkr3_schedule_active",
    "binary_sensor.solvisleo_180_hot_water_schedule_active",
    "number.solvisleo_180_hkr1_fix_flow_day_temperature",
    "number.solvisleo_180_hkr1_fix_flow_set_back_temperature",
    "number.solvisleo_180_hkr1_heating_curve_day_temperature_1",
    "number.solvisleo_180_hkr1_heating_curve_day_temperature_2",
    "number.solvisleo_180_hkr1_heating_curve_day_temperature_3",
    "number.solvisleo_180_hkr1_heating_curve_set_back_temperature",
    "number.solvisleo_180_hkr1_slope_of_the_heating_curve",
    "number.solvisleo_180_hkr1_room_temp",
    "number.solvisleo_180_hkr2_fix_flow_day_temperature",
    "number.solvisleo_180_hkr2_fix_flow_set_back_temperature",
    "number.solvisleo_180_hkr2_heating_curve_day_temperature_1",
    "number.solvisleo_180_hkr2_heating_curve_day_temperature_2",
    "number.solvisleo_180_hkr2_heating_curve_day_temperature_3",
    "number.solvisleo_180_hkr2_heating_curve_set_back_temperature",
    "number.solvisleo_180_hkr2_room_temp",
    "number.solvisleo_180_hkr2_slope_of_the_heating_curve",
    "number.solvisleo_180_hkr3_fix_flow_day_temperature",
    "number.solvisleo_180_hkr3_fix_flow_set_back_temperature",
    "number.solvisleo_180_hkr3_heating_curve_day_temperature_1",
    "number.solvisleo_180_hkr3_heating_curve_day_temperature_2",
    "number.solvisleo_180_hkr3_heating_curve_day_temperature_3",
    "number.solvisleo_180_hkr3_heating_curve_set_back_temperature",
    "number.solvisleo_180_hkr3_room_temp",
    "number.solvisleo_180_hkr3_slope_of_the_heating_curve",
    "number.solvisleo_180_warm_water_target_temp",
    "select.solvisleo_180_hkr_1_operating_mode",
    "select.solvisleo_180_hkr2_operating_mode",
    "select.solvisleo_180_hkr3_operating_mode",
    "sensor.solvisleo_180_analog_in_1",
    "sensor.solvisleo_180_analog_in_2",
    "sensor.solvisleo_180_analog_in_3",
    "sensor.solvisleo_180_analog_out_o6_mode",
    "sensor.solvisleo_180_heizstab_modulation_mode",
    "sensor.solvisleo_180_heizstab_modulation_o1",
    "sensor.solvisleo_180_heizstab_thermal_energy",
    "sensor.solvisleo_180_circulation_mode",
    "sensor.solvisleo_180_circulation_schedule",
    "sensor.solvisleo_180_circulation_temperature_s11",
    "sensor.solvisleo_180_cold_water_temperature_s15",
    "sensor.solvisleo_180_controller_unix_time",
    "sensor.solvisleo_180_cooling_energy",
    "sensor.solvisleo_180_cooling_power",
    "sensor.solvisleo_180_eco_schedule",
    "sensor.solvisleo_180_heizstab_electrical_power",
    "sensor.solvisleo_180_heizstab_runtime",
    "sensor.solvisleo_180_heizstab_thermal_power",
    "sensor.solvisleo_180_heat_meter_output",
    "sensor.solvisleo_180_heat_pump_charging_pump_mode",
    "sensor.solvisleo_180_heat_pump_charging_pump_o4",
    "sensor.solvisleo_180_heat_pump_electrical_power_consumption",
    "sensor.solvisleo_180_heat_pump_hybrid_heating_bivalent_temperature",
    "sensor.solvisleo_180_heat_pump_hybrid_hot_water_bivalent_temperature",
    "sensor.solvisleo_180_heat_pump_runtime",
    "sensor.solvisleo_180_heat_pump_thermal_heat_output",
    "sensor.solvisleo_180_heat_pump_thermal_output",
    "sensor.solvisleo_180_heating_buffer_bottom_temperature_s9",
    "sensor.solvisleo_180_heating_buffer_top_temperature_s4",
    "sensor.solvisleo_180_heating_circuits_heat_output",
    "sensor.solvisleo_180_hkr1_control_state",
    "sensor.solvisleo_180_hkr1_demand_temperature",
    "sensor.solvisleo_180_hkr1_flow_mode",
    "sensor.solvisleo_180_hkr1_mixer_control_state",
    "sensor.solvisleo_180_hkr1_room_temp",
    "sensor.solvisleo_180_hkr1_schedule",
    "sensor.solvisleo_180_hkr1_supply_temperature_s12",
    "sensor.solvisleo_180_hkr2_schedule",
    "sensor.solvisleo_180_hkr3_schedule",
    "sensor.solvisleo_180_heating_circuit_power",
    "sensor.solvisleo_180_heating_circuit_return_temperature",
    "sensor.solvisleo_180_heating_circuit_spread",
    "sensor.solvisleo_180_heating_circuit_supply_temperature",
    "sensor.solvisleo_180_heating_circuit_volume_flow",
    "sensor.solvisleo_180_hkr2_control_state",
    "sensor.solvisleo_180_hkr2_demand_temperature",
    "sensor.solvisleo_180_hkr2_flow_mode",
    "sensor.solvisleo_180_hkr2_mixer_control_state",
    "sensor.solvisleo_180_hkr2_room_temp",
    "sensor.solvisleo_180_hkr2_supply_temperature_s13",
    "sensor.solvisleo_180_hkr3_control_state",
    "sensor.solvisleo_180_hkr3_demand_temperature",
    "sensor.solvisleo_180_hkr3_flow_mode",
    "sensor.solvisleo_180_hkr3_mixer_control_state",
    "sensor.solvisleo_180_hkr3_room_temp",
    "sensor.solvisleo_180_hot_water_buffer_temperature_s1",
    "sensor.solvisleo_180_hot_water_heat_output",
    "sensor.solvisleo_180_hot_water_pump_mode",
    "sensor.solvisleo_180_hot_water_pump_o5",
    "sensor.solvisleo_180_hot_water_power",
    "sensor.solvisleo_180_warm_water_power_calculated",
    "sensor.solvisleo_180_hot_water_schedule",
    "sensor.solvisleo_180_hot_water_temperature_s2",
    "sensor.solvisleo_180_hot_water_volume_flow_s18",
    "sensor.solvisleo_180_message_1_code",
    "sensor.solvisleo_180_message_2_code",
    "sensor.solvisleo_180_message_3_code",
    "sensor.solvisleo_180_message_4_code",
    "sensor.solvisleo_180_message_5_code",
    "sensor.solvisleo_180_message_6_code",
    "sensor.solvisleo_180_message_7_code",
    "sensor.solvisleo_180_message_8_code",
    "sensor.solvisleo_180_message_9_code",
    "sensor.solvisleo_180_message_10_code",
    "sensor.solvisleo_180_number_of_heating_circuits",
    "sensor.solvisleo_180_number_of_messages",
    "sensor.solvisleo_180_outdoor_temperature_s10",
    "sensor.solvisleo_180_primary_solar_pump_o2",
    "sensor.solvisleo_180_pv2heat_electrical_power",
    "sensor.solvisleo_180_pv2heat_heat_output",
    "sensor.solvisleo_180_pv2heat_runtime",
    "sensor.solvisleo_180_secondary_solar_pump_o3",
    "sensor.solvisleo_180_solar_collector_temperature_s8",
    "sensor.solvisleo_180_solar_flow_primary_temperature_s7",
    "sensor.solvisleo_180_solar_pump_primary_mode",
    "sensor.solvisleo_180_solar_pump_primary_runtime",
    "sensor.solvisleo_180_solar_pump_secondary_mode",
    "sensor.solvisleo_180_solar_pump_secondary_running_time",
    "sensor.solvisleo_180_temperature_sensor_s6",
    "sensor.solvisleo_180_solar_thermal_heat_output",
    "sensor.solvisleo_180_solar_thermal_power",
    "sensor.solvisleo_180_solar_volume_flow_s17",
    "sensor.solvisleo_180_solarvorlauf_sekundar_temperatur_s5",
    "sensor.solvisleo_180_smart_energy_consumer_1_status",
    "sensor.solvisleo_180_smart_energy_grid_power",
    "sensor.solvisleo_180_smart_energy_usable_power",
    "sensor.solvisleo_180_storage_tank_reference_temperature_s3",
    "sensor.solvisleo_180_stored_energy_of_stratified_storage_reference_12_degc",
    "sensor.solvisleo_180_temperature_sensor_s14",
    "sensor.solvisleo_180_temperature_sensor_s16",
    "switch.solvisleo_180_hkr1_warm_water_priority",
    "switch.solvisleo_180_hkr2_warm_water_priority",
    "switch.solvisleo_180_hkr3_warm_water_priority",
    "switch.solvisleo_180_warm_water_reheat_start",
    "update.solvisleo_180_firmware_nbg",
    "update.solvisleo_180_firmware_sc",
}


async def setup_recorded_anlage(
    hass,
    *,
    poll_rate_high: int = 10,
    poll_rate_default: int = 10,
    poll_rate_slow: int = 10,
):
    """Set up the integration against the recorded SolvisLeo 180 responses."""
    client = AddressableModbusClient.from_inventory(
        ROOT / "inventory" / "solvisleo_180_sc3.json",
        ROOT / "tests" / "fixtures" / "solvisleo_180_sc3_parameters.json",
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="SolvisLeo 180",
        version=2,
        minor_version=6,
        data={
            CONF_NAME: "SolvisLeo 180",
            CONF_HOST: "172.16.0.73",
            CONF_PORT: 502,
            POLL_RATE_HIGH: poll_rate_high,
            POLL_RATE_DEFAULT: poll_rate_default,
            POLL_RATE_SLOW: poll_rate_slow,
            "hkr1_name": "Ground floor",
            "hkr2_name": "Upper floor",
            "hkr3_name": "Attic",
        },
    )
    entry.add_to_hass(hass)

    with patch("custom_components.solvis_leo.create_modbus_client", return_value=client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    return client, entry, coordinator


@pytest.mark.asyncio
async def test_setup_exposes_the_recorded_anlage(hass) -> None:
    _, entry, coordinator = await setup_recorded_anlage(hass)
    await coordinator.async_refresh()
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    actual_entity_ids = {entity.entity_id for entity in registry.entities.values() if entity.config_entry_id == entry.entry_id}

    assert entry.domain == "solvis_leo"
    assert actual_entity_ids == EXPECTED_ENTITY_IDS
    assert registry.entities["update.solvisleo_180_firmware_sc"].unique_id == "32770_version_sc"
    assert registry.entities["update.solvisleo_180_firmware_nbg"].unique_id == "32771_version_nbg"
    assert registry.entities["sensor.solvisleo_180_hkr1_schedule"].unique_id == "34048_hkr1_schedule"
    assert registry.entities["binary_sensor.solvisleo_180_hkr1_schedule_active"].unique_id == "34048_hkr1_schedule_active"
    assert registry.entities["sensor.solvisleo_180_stored_energy_of_stratified_storage_reference_12_degc"].unique_id == "33024_stored_energy_12"
    assert registry.entities["sensor.solvisleo_180_warm_water_power_calculated"].unique_id == "33025_warm_water_power_calculated"
    assert hass.states.get("sensor.solvisleo_180_hot_water_buffer_temperature_s1").state == "49.5"
    assert hass.states.get("sensor.solvisleo_180_stored_energy_of_stratified_storage_reference_12_degc").state == "5.0"
    assert hass.states.get("sensor.solvisleo_180_warm_water_power_calculated").state == "0.0"
    assert hass.states.get("number.solvisleo_180_warm_water_target_temp").state == "47"
    assert hass.states.get("select.solvisleo_180_hkr_1_operating_mode").state == "5"
    assert hass.states.get("switch.solvisleo_180_warm_water_reheat_start").state == "off"
    assert hass.states.get("binary_sensor.solvisleo_180_heat_pump_charging_pump_a2").state == "on"
    assert hass.states.get("update.solvisleo_180_firmware_sc").state == "unknown"


@pytest.mark.asyncio
async def test_reload_keeps_every_recorded_entity(hass) -> None:
    """Platform setup must not remove entities owned by sibling platforms."""
    client, entry, _ = await setup_recorded_anlage(hass)
    registry = er.async_get(hass)
    customized_entity_id = "sensor.solvisleo_180_hot_water_buffer_temperature_s1"
    registry.async_update_entity(
        customized_entity_id,
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    registry.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id="33045_digin_error",
        config_entry=entry,
    )

    with patch("custom_components.solvis_leo.create_modbus_client", return_value=client):
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    actual_entity_ids = {entity.entity_id for entity in registry.entities.values() if entity.config_entry_id == entry.entry_id}

    assert actual_entity_ids == EXPECTED_ENTITY_IDS
    assert registry.entities[customized_entity_id].disabled_by is er.RegistryEntryDisabler.USER
    assert all(entity.unique_id != "33045_digin_error" for entity in registry.entities.values())


@pytest.mark.asyncio
async def test_register_failure_is_isolated_and_recovers(hass, caplog) -> None:
    client, _, coordinator = await setup_recorded_anlage(hass)
    failed_entity_id = "sensor.solvisleo_180_heizstab_thermal_power"
    healthy_entity_id = "sensor.solvisleo_180_hot_water_power"
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(failed_entity_id).state == "0.0"

    caplog.clear()
    healthy_reads_before_failure = client.request_count("input", 33549)
    client.fail("input", 33546)
    with caplog.at_level(logging.DEBUG, logger="custom_components.solvis_leo.coordinator"):
        for attempt in range(1, 4):
            await coordinator.async_refresh()
            await hass.async_block_till_done()

            assert coordinator.last_update_success
            assert hass.states.get(healthy_entity_id).state != "unavailable"
            assert client.request_count("input", 33549) == healthy_reads_before_failure + attempt
            expected_state = "unavailable" if attempt == 3 else "0.0"
            assert hass.states.get(failed_entity_id).state == expected_state

    failure_logs = [record for record in caplog.records if "heizstab_power_thermal | 33546" in record.getMessage() and "Exception during read" in record.getMessage()]
    assert [record.levelno for record in failure_logs] == [
        logging.WARNING,
        logging.DEBUG,
        logging.DEBUG,
    ]
    failure_warnings = [record for record in caplog.records if record.levelno >= logging.WARNING and "heizstab_power_thermal" in record.getMessage()]
    assert failure_warnings == [failure_logs[0]]

    client.restore("input", 33546)
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(failed_entity_id).state == "0.0"

    client.fail("input", 33546)
    for _ in range(2):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
    assert hass.states.get(failed_entity_id).state == "0.0"

    client.restore("input", 33546)
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    requests_before_rejection = client.request_count("input", 33546)
    client.reject("input", 33546)
    await coordinator.async_refresh()
    client.restore("input", 33546)
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert client.request_count("input", 33546) == requests_before_rejection + 2
    assert hass.states.get(failed_entity_id).state == "0.0"


@pytest.mark.asyncio
async def test_register_timeout_is_isolated_and_recovers(hass) -> None:
    """A slow response costs one register and is retried on the next cycle."""
    client, _, coordinator = await setup_recorded_anlage(hass)
    failed_entity_id = "sensor.solvisleo_180_heizstab_thermal_power"
    healthy_address = 33549
    healthy_reads = client.request_count("input", healthy_address)

    client.timeout("input", 33546)
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert coordinator.last_update_success
    assert client.request_count("input", healthy_address) == healthy_reads + 1
    assert hass.states.get(failed_entity_id).state == "0.0"

    client.restore("input", 33546)
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(failed_entity_id).state == "0.0"


@pytest.mark.asyncio
async def test_slow_polled_value_stays_current_between_reads(hass) -> None:
    """A slow value remains published while its next Modbus read is not due."""
    client, _, coordinator = await setup_recorded_anlage(
        hass,
        poll_rate_high=10,
        poll_rate_default=30,
        poll_rate_slow=300,
    )
    entity_id = "sensor.solvisleo_180_heizstab_thermal_energy"
    slow_address = 33538
    reads_after_initial_poll = client.request_count("input", slow_address)

    assert reads_after_initial_poll == 1
    assert hass.states.get(entity_id).state == "0"

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert client.request_count("input", slow_address) == reads_after_initial_poll
    assert hass.states.get(entity_id).state == "0"


@pytest.mark.asyncio
async def test_connection_loss_fails_the_whole_update(hass) -> None:
    client, _, coordinator = await setup_recorded_anlage(hass)
    client.lose_connection("input", 33549)
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert not coordinator.last_update_success
    assert hass.states.get("sensor.solvisleo_180_hot_water_power").state == "unavailable"
    assert hass.states.get("sensor.solvisleo_180_warm_water_power_calculated").state == "unavailable"
    assert hass.states.get("sensor.solvisleo_180_heizstab_thermal_power").state == "unavailable"


@pytest.mark.asyncio
async def test_calculated_warm_water_power_uses_fast_sources_and_preserves_raw_register(hass) -> None:
    """A draw-off updates at the fast cadence even while 33549 keeps returning zero."""
    client, _, coordinator = await setup_recorded_anlage(hass, poll_rate_default=30, poll_rate_slow=300)
    source_values = {33025: 497, 33038: 135, 33041: 66}
    initial_reads = {address: client.request_count("input", address) for address in source_values}
    for address, value in source_values.items():
        client.set_registers("input", address, [value])

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    calculated = hass.states.get("sensor.solvisleo_180_warm_water_power_calculated")
    assert calculated.state == "16.67"
    assert calculated.attributes["unit_of_measurement"] == "kW"
    assert calculated.attributes["device_class"] == "power"
    assert calculated.attributes["state_class"] == "measurement"
    assert hass.states.get("sensor.solvisleo_180_hot_water_power").state == "0"
    for address, reads in initial_reads.items():
        assert client.request_count("input", address) == reads + 1

    client.fail("input", 33549)
    for _ in range(3):
        await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get("sensor.solvisleo_180_hot_water_power").state == "unavailable"
    assert hass.states.get(calculated.entity_id).state == "16.67"


@pytest.mark.asyncio
@pytest.mark.parametrize("address", [33025, 33038, 33041])
async def test_calculated_warm_water_power_tracks_source_failure_and_recovery(hass, address) -> None:
    """Preserve the snapshot for two failed reads, then publish unavailability."""
    client, _, coordinator = await setup_recorded_anlage(hass)
    entity_id = "sensor.solvisleo_180_warm_water_power_calculated"
    initial_state = hass.states.get(entity_id).state
    client.fail("input", address)

    for attempt in range(1, 4):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert hass.states.get(entity_id).state == ("unavailable" if attempt == 3 else initial_state)
        assert coordinator.last_update_success

    client.restore("input", address)
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == initial_state


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("entity_id", "register_type", "address"),
    [
        ("sensor.solvisleo_180_circulation_temperature_s11", "input", 33034),
        ("select.solvisleo_180_hkr_1_operating_mode", "holding", 2818),
        ("number.solvisleo_180_warm_water_target_temp", "holding", 2305),
        ("switch.solvisleo_180_warm_water_reheat_start", "holding", 2322),
        ("binary_sensor.solvisleo_180_circulation_pump_a1", "input", 33280),
        ("update.solvisleo_180_firmware_sc", "input", 32770),
    ],
)
async def test_disabled_entity_stops_its_modbus_reads(hass, entity_id, register_type, address) -> None:
    """A real, renamed registry entry must control polling by its stable identity."""
    client, entry, coordinator = await setup_recorded_anlage(hass)
    registry = er.async_get(hass)
    entity = registry.async_update_entity(
        entity_id,
        new_entity_id=f"{entity_id.split('.')[0]}.mein_solvis_wert",
        disabled_by=er.RegistryEntryDisabler.USER,
    )
    await hass.async_block_till_done()
    reads_before = client.request_count(register_type, address)
    healthy_reads_before = client.request_count("input", 33549)

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert registry.entities[entity.entity_id].disabled
    assert client.request_count(register_type, address) == reads_before
    assert client.request_count("input", 33549) == healthy_reads_before + 1

    with patch("custom_components.solvis_leo.create_modbus_client", return_value=client):
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    assert client.request_count(register_type, address) == reads_before

    registry.async_update_entity(entity.entity_id, disabled_by=None)
    await coordinator.async_refresh()

    assert client.request_count(register_type, address) == reads_before + 1


@pytest.mark.asyncio
async def test_default_disabled_entities_are_not_polled_during_first_setup(hass) -> None:
    """The first refresh has no registry yet and must respect entity defaults."""
    client, _, coordinator = await setup_recorded_anlage(hass)

    for _ in range(2):
        assert client.request_count("input", 34313) == 0  # Mischer diagnostic
        assert client.request_count("input", 32768) == 0  # Controller clock
        assert client.request_count("holding", 34048) == 0  # Both Wochenplan entities disabled
        assert client.request_count("input", 33025) > 0  # Enabled source/derived sensor
        await coordinator.async_refresh()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("derived_unique_id", "sources", "expected"),
    [
        (
            "33025_warm_water_power_calculated",
            [(33025, "warm_water_temp_s2", 497), (33038, "cold_water_temp_s15", 135), (33041, "warm_water_volume_flow_s18", 66)],
            "16.67",
        ),
        (
            "33024_stored_energy_12",
            [(33024, "warm_water_buffer_temp_s1", 500), (33027, "heating_buffer_upper_temp_s4", 400), (33032, "heating_buffer_lower_temp_s9", 300)],
            "6.0",
        ),
    ],
)
async def test_enabled_derived_sensor_keeps_disabled_source_registers_polling(hass, derived_unique_id, sources, expected) -> None:
    """Only disabling the final consumer releases the underlying source reads."""
    client, entry, coordinator = await setup_recorded_anlage(hass)
    registry = er.async_get(hass)
    derived_id = registry.async_get_entity_id("sensor", DOMAIN, derived_unique_id)
    derived = registry.async_update_entity(derived_id, new_entity_id="sensor.meine_berechnung")
    for address, name, value in sources:
        source_id = registry.async_get_entity_id("sensor", DOMAIN, f"{address}_{name}")
        registry.async_update_entity(source_id, disabled_by=er.RegistryEntryDisabler.USER)
        client.set_registers("input", address, [value])
    await hass.async_block_till_done()
    previous_reads = {address: client.request_count("input", address) for address, _, _ in sources}

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(derived.entity_id).state == expected
    for address, name, _ in sources:
        assert client.request_count("input", address) == previous_reads[address] + 1
        assert coordinator.data[name] is not None

    registry.async_update_entity(derived.entity_id, disabled_by=er.RegistryEntryDisabler.USER)
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    for address, name, _ in sources:
        assert client.request_count("input", address) == previous_reads[address] + 1
        assert name not in coordinator.data

    registry.async_update_entity(derived.entity_id, disabled_by=None)
    with patch("custom_components.solvis_leo.create_modbus_client", return_value=client):
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    assert hass.states.get(derived.entity_id).state == expected
    for address, _, _ in sources:
        assert client.request_count("input", address) == previous_reads[address] + 2


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled_domain", ["sensor", "binary_sensor"])
async def test_weekly_schedule_is_polled_while_either_entity_is_enabled(hass, enabled_domain) -> None:
    """The next-switch sensor and active binary sensor share one block read."""
    client, entry, coordinator = await setup_recorded_anlage(hass, poll_rate_slow=300)
    registry = er.async_get(hass)
    sensor_id = "sensor.solvisleo_180_hkr1_schedule"
    binary_id = "binary_sensor.solvisleo_180_hkr1_schedule_active"
    enabled_id, sibling_id = (sensor_id, binary_id) if enabled_domain == "sensor" else (binary_id, sensor_id)
    assert client.request_count("holding", 34048) == 0
    client.set_registers("holding", 34048, [24, 32, 0, 0, 0, 0] * 7)
    enabled = registry.async_update_entity(enabled_id, new_entity_id=f"{enabled_domain}.mein_wochenplan", disabled_by=None)

    with patch("custom_components.solvis_leo.create_modbus_client", return_value=client):
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    assert client.request_count("holding", 34048) == 1
    assert hass.states.get(enabled.entity_id).state not in ("unknown", "unavailable")

    registry.async_update_entity(sibling_id, disabled_by=None)
    registry.async_update_entity(enabled.entity_id, disabled_by=er.RegistryEntryDisabler.USER)
    # The shared read remains needed, retaining its slow cadence.
    await coordinator.async_refresh()
    assert client.request_count("holding", 34048) == 1
    assert "hkr1_schedule" in coordinator.data

    registry.async_update_entity(sibling_id, disabled_by=er.RegistryEntryDisabler.USER)
    await coordinator.async_refresh()
    assert client.request_count("holding", 34048) == 1
    assert "hkr1_schedule" not in coordinator.data

    registry.async_update_entity(sibling_id, disabled_by=None)
    await coordinator.async_refresh()
    assert client.request_count("holding", 34048) == 2


@pytest.mark.asyncio
async def test_reenabled_slow_sensor_reads_fresh_data_on_next_update(hass) -> None:
    """Reactivation must not wait five minutes or republish the old cached value."""
    client, _, coordinator = await setup_recorded_anlage(hass, poll_rate_slow=300)
    registry = er.async_get(hass)
    entity_id = "sensor.solvisleo_180_heizstab_thermal_energy"
    assert client.request_count("input", 33538) == 1
    registry.async_update_entity(entity_id, disabled_by=er.RegistryEntryDisabler.USER)
    await coordinator.async_refresh()
    assert "heizstab_energy_thermal" not in coordinator.data
    assert client.request_count("input", 33538) == 1
    client.set_registers("input", 33538, [12])

    registry.async_update_entity(entity_id, disabled_by=None)
    await coordinator.async_refresh()
    assert client.request_count("input", 33538) == 2
    assert coordinator.data["heizstab_energy_thermal"] == 120


@pytest.mark.asyncio
async def test_disabling_every_consumer_stops_all_register_reads(hass) -> None:
    client, entry, coordinator = await setup_recorded_anlage(hass)
    registry = er.async_get(hass)
    for entity in list(registry.entities.values()):
        if entity.config_entry_id == entry.entry_id:
            registry.async_update_entity(entity.entity_id, disabled_by=er.RegistryEntryDisabler.USER)
    with (
        patch.object(client, "read_input_registers", wraps=client.read_input_registers) as input_reads,
        patch.object(client, "read_holding_registers", wraps=client.read_holding_registers) as holding_reads,
    ):
        await coordinator.async_refresh()

    assert coordinator.data == {}
    input_reads.assert_not_awaited()
    holding_reads.assert_not_awaited()
