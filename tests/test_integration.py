"""Integration-level seam for the SolvisLeo 180 installation."""

from pathlib import Path
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.helpers import entity_registry as er

from custom_components.solvis_control.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_OPTION_1,
    CONF_OPTION_2,
    CONF_OPTION_3,
    CONF_OPTION_4,
    CONF_OPTION_5,
    CONF_OPTION_6,
    CONF_OPTION_7,
    CONF_OPTION_8,
    CONF_OPTION_9,
    CONF_OPTION_10,
    CONF_OPTION_11,
    CONF_OPTION_12,
    CONF_OPTION_13,
    CONF_PORT,
    DATA_COORDINATOR,
    DEVICE_VERSION,
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
    "number.solvisleo_180_warm_water_target_temp",
    "select.solvisleo_180_hkr_1_operating_mode",
    "sensor.solvisleo_180_analog_in_1",
    "sensor.solvisleo_180_analog_in_2",
    "sensor.solvisleo_180_analog_in_3",
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
    "sensor.solvisleo_180_smart_energy_consumer_1_status",
    "sensor.solvisleo_180_smart_energy_grid_power",
    "sensor.solvisleo_180_smart_energy_usable_power",
    "sensor.solvisleo_180_storage_tank_reference_temperature_s3",
    "sensor.solvisleo_180_stored_energy_of_stratified_storage_reference_12_degc",
    "sensor.solvisleo_180_temperature_sensor_s14",
    "sensor.solvisleo_180_temperature_sensor_s16",
    "switch.solvisleo_180_hkr1_warm_water_priority",
    "switch.solvisleo_180_warm_water_reheat_start",
    "update.solvisleo_180_firmware_nbg",
    "update.solvisleo_180_firmware_sc",
}


@pytest.mark.asyncio
async def test_setup_exposes_the_recorded_anlage(hass) -> None:
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
            DEVICE_VERSION: 1,
            POLL_RATE_HIGH: 10,
            POLL_RATE_DEFAULT: 10,
            POLL_RATE_SLOW: 10,
            CONF_OPTION_1: False,
            CONF_OPTION_2: False,
            CONF_OPTION_3: False,
            CONF_OPTION_4: True,
            CONF_OPTION_5: False,
            CONF_OPTION_6: True,
            CONF_OPTION_7: False,
            CONF_OPTION_8: False,
            CONF_OPTION_9: False,
            CONF_OPTION_10: False,
            CONF_OPTION_11: False,
            CONF_OPTION_12: False,
            CONF_OPTION_13: "SolvisLeo 180",
        },
    )
    entry.add_to_hass(hass)

    with patch("custom_components.solvis_control.create_modbus_client", return_value=client):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
        await coordinator.async_refresh()
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    registry = er.async_get(hass)
    actual_entity_ids = {
        entity.entity_id
        for entity in registry.entities.values()
        if entity.config_entry_id == entry.entry_id
    }

    assert actual_entity_ids == EXPECTED_ENTITY_IDS
    assert hass.states.get("sensor.solvisleo_180_hot_water_buffer_temperature_s1").state == "49.5"
    assert hass.states.get("number.solvisleo_180_warm_water_target_temp").state == "47"
    assert hass.states.get("select.solvisleo_180_hkr_1_operating_mode").state == "5"
    assert hass.states.get("switch.solvisleo_180_warm_water_reheat_start").state == "off"
    assert hass.states.get("binary_sensor.solvisleo_180_heat_pump_charging_pump_a2").state == "on"
    assert hass.states.get("update.solvisleo_180_firmware_sc").state == "unknown"
