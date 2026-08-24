"""Integration-level seam for the SolvisLeo 180 installation."""

import logging
from pathlib import Path
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.helpers import entity_registry as er

from custom_components.solvis_control.const import (
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

EXPECTED_ENTITY_IDS = {
    "binary_sensor.solvisleo_180_burner_status_a12",
    "binary_sensor.solvisleo_180_circulation_pump_a1",
    "binary_sensor.solvisleo_180_circulation_schedule_active",
    "binary_sensor.solvisleo_180_eco_schedule_active",
    "binary_sensor.solvisleo_180_heat_pump_changeover_valve_a14",
    "binary_sensor.solvisleo_180_heat_pump_charging_pump_a2",
    "binary_sensor.solvisleo_180_heat_pump_heating_element_stage_2_3_a13",
    "binary_sensor.solvisleo_180_digin_error",
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
    "sensor.solvisleo_180_analog_out_o6",
    "sensor.solvisleo_180_analog_out_o6_mode",
    "sensor.solvisleo_180_burner_modulation_mode",
    "sensor.solvisleo_180_burner_modulation_o1",
    "sensor.solvisleo_180_burner_thermal_heat_output",
    "sensor.solvisleo_180_circulation_mode",
    "sensor.solvisleo_180_circulation_schedule",
    "sensor.solvisleo_180_circulation_temperature_s11",
    "sensor.solvisleo_180_cold_water_temperature_s15",
    "sensor.solvisleo_180_controller_unix_time",
    "sensor.solvisleo_180_cooling_energy",
    "sensor.solvisleo_180_cooling_power",
    "sensor.solvisleo_180_eco_schedule",
    "sensor.solvisleo_180_heat_generator_2_electrical_power",
    "sensor.solvisleo_180_heat_generator_2_runtime",
    "sensor.solvisleo_180_heat_generator_2_thermal_output",
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
    "sensor.solvisleo_180_solar_return_secondary_temperature_s6",
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


async def setup_recorded_anlage(hass):
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
            POLL_RATE_HIGH: 10,
            POLL_RATE_DEFAULT: 10,
            POLL_RATE_SLOW: 10,
        },
    )
    entry.add_to_hass(hass)

    with patch("custom_components.solvis_control.create_modbus_client", return_value=client):
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

    assert actual_entity_ids == EXPECTED_ENTITY_IDS
    assert hass.states.get("sensor.solvisleo_180_hot_water_buffer_temperature_s1").state == "49.5"
    assert hass.states.get("sensor.solvisleo_180_stored_energy_of_stratified_storage_reference_12_degc").state == "5.0"
    assert hass.states.get("number.solvisleo_180_warm_water_target_temp").state == "47"
    assert hass.states.get("select.solvisleo_180_hkr_1_operating_mode").state == "5"
    assert hass.states.get("switch.solvisleo_180_warm_water_reheat_start").state == "off"
    assert hass.states.get("binary_sensor.solvisleo_180_heat_pump_charging_pump_a2").state == "on"
    assert hass.states.get("update.solvisleo_180_firmware_sc").state == "unknown"


@pytest.mark.asyncio
async def test_register_failure_is_isolated_and_recovers(hass, caplog) -> None:
    client, _, coordinator = await setup_recorded_anlage(hass)
    failed_entity_id = "sensor.solvisleo_180_heat_generator_2_thermal_output"
    healthy_entity_id = "sensor.solvisleo_180_hot_water_power"
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(failed_entity_id).state == "0.0"

    caplog.clear()
    healthy_reads_before_failure = client.request_count("input", 33549)
    client.fail("input", 33546)
    with caplog.at_level(logging.DEBUG, logger="custom_components.solvis_control.coordinator"):
        for attempt in range(1, 4):
            await coordinator.async_refresh()
            await hass.async_block_till_done()

            assert coordinator.last_update_success
            assert hass.states.get(healthy_entity_id).state != "unavailable"
            assert client.request_count("input", 33549) == healthy_reads_before_failure + attempt
            expected_state = "unavailable" if attempt == 3 else "0.0"
            assert hass.states.get(failed_entity_id).state == expected_state

    failure_logs = [record for record in caplog.records if "heat_generator_2_power_thermal | 33546" in record.getMessage() and "Exception during read" in record.getMessage()]
    assert [record.levelno for record in failure_logs] == [
        logging.WARNING,
        logging.DEBUG,
        logging.DEBUG,
    ]
    failure_warnings = [record for record in caplog.records if record.levelno >= logging.WARNING and "heat_generator_2_power_thermal" in record.getMessage()]
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
async def test_connection_loss_fails_the_whole_update(hass) -> None:
    client, _, coordinator = await setup_recorded_anlage(hass)
    client.lose_connection("input", 33549)
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert not coordinator.last_update_success
    assert hass.states.get("sensor.solvisleo_180_hot_water_power").state == "unavailable"
    assert hass.states.get("sensor.solvisleo_180_heat_generator_2_thermal_output").state == "unavailable"
