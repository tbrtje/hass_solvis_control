"""
Solvis Sensor Entity.
"""

from collections.abc import Sequence
import logging
import math

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.util import dt as dt_util
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_HOST,
    DATA_COORDINATOR,
    DERIVATIVE_SENSORS,
    REGISTER_ADDRESSES_BY_NAME,
    SCHEDULES,
    STORAGE_REFERENCE_TEMPERATURE,
    STORAGE_ZONE_SENSOR_KEYS,
    STORAGE_ZONE_VOLUMES,
)
from .coordinator import SolvisModbusCoordinator
from .utils.helpers import async_setup_solvis_entities, generate_device_info
from .utils.schedule import decode_schedule, next_switch, schedule_as_attributes
from .entity import SolvisEntity

_LOGGER = logging.getLogger(__name__)


class SolvisDerivativeSensor(SolvisEntity, SensorEntity):
    """Compute a sensor from the coordinator's scaled source values."""

    def __init__(
        self,
        coordinator: SolvisModbusCoordinator,
        device_info: DeviceInfo,
        host: str,
        name: str,
        source_keys: Sequence[str],
        *,
        unit: str,
        device_class: str | None,
        state_class: SensorStateClass | None,
        entity_category: str | None = None,
        suggested_display_precision: int = 2,
        compute_mode: str | None,
        modbus_address: int | None = None,
    ) -> None:
        super().__init__(
            coordinator,
            device_info,
            host,
            name,
            modbus_address=modbus_address,
            enabled_by_default=True,
            data_processing=0,
            poll_rate=False,
        )

        self.source_keys = source_keys

        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_entity_category = entity_category
        self._attr_suggested_display_precision = suggested_display_precision
        self.compute_mode = compute_mode

        self._attr_native_value = None
        self._attr_extra_state_attributes = {}

    @property
    def available(self) -> bool:
        """Require a valid result and every source register to be available."""
        return (
            super().available
            and self.native_value is not None
            and all(self.coordinator.is_register_available(REGISTER_ADDRESSES_BY_NAME[key]) for key in self.source_keys if key in REGISTER_ADDRESSES_BY_NAME)
        )

    def _compute_combined(self) -> float | None:
        data = self.coordinator.data or {}
        values = [data.get(key) for key in self.source_keys]
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in values):
            return None

        match self.compute_mode:
            case "stored_energy_12":
                result = self._compute_stored_energy_12(values)
            case "warm_water_power":
                result = self._compute_warm_water_power(values)
            case _:
                result = sum(values)

        return result if result is not None and math.isfinite(result) else None

    @staticmethod
    def _compute_warm_water_power(values: list[float]) -> float | None:
        """Estimate thermal draw-off power from S2, S15 (°C) and S18 (l/min)."""
        if len(values) != 3:
            return None
        warm_temperature, cold_temperature, volume_flow = values
        # Restrict temperatures to the liquid domestic-water range. This also
        # excludes out-of-range Fühler values such as -300 or 250 °C.
        if not 0 <= warm_temperature <= 100 or not 0 <= cold_temperature <= 100 or volume_flow < 0:
            return None

        # Water: density ≈ 1 kg/l, specific heat capacity ≈ 4.186 kJ/(kg K).
        return volume_flow * 4.186 * max(warm_temperature - cold_temperature, 0) / 60

    def _compute_stored_energy_12(self, values: list[float]) -> float:
        # Each Speicherzone is delimited by two Fühler, so two zones need three
        # temperatures: S1, S4 and S9.
        if len(values) != len(STORAGE_ZONE_SENSOR_KEYS):
            _LOGGER.debug("invalid Fühler count: returning 0")
            return 0.0

        rho = 1.0
        c = 4.186

        total_energy = 0.0
        for zone, volume in enumerate(STORAGE_ZONE_VOLUMES):
            t_zone = (values[zone] + values[zone + 1]) / 2
            total_energy += volume * rho * c * (t_zone - STORAGE_REFERENCE_TEMPERATURE)

        return total_energy / 3600

    def _async_update_from_coordinator(self) -> None:
        combined = self._compute_combined()
        if combined is None:
            self._attr_native_value = None
            self._attr_extra_state_attributes = {}
        else:
            self._attr_native_value = round(combined, self.suggested_display_precision)
            raw_attrs = {key: self.coordinator.data.get(key) for key in self.source_keys}
            self._attr_extra_state_attributes = {"raw_values": raw_attrs}

        if self.hass is not None:
            self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Use CoordinatorEntity's managed subscription for updates and unload."""
        self._async_update_from_coordinator()


class SolvisScheduleSensor(SolvisEntity, SensorEntity):
    """A weekly schedule read as one register block.

    The state is the next switching time; the full week lives in the attributes,
    because Home Assistant graphs states and ignores attributes. The companion
    binary sensor is what produces a usable timeline.
    """

    def __init__(
        self,
        coordinator: SolvisModbusCoordinator,
        device_info: DeviceInfo,
        host: str,
        name: str,
        modbus_address: int,
    ) -> None:
        super().__init__(
            coordinator,
            device_info,
            host,
            name,
            modbus_address=modbus_address,
            enabled_by_default=False,
            data_processing=0,
            poll_rate=False,
        )

        self._attr_device_class = SensorDeviceClass.TIMESTAMP
        self._attr_native_value = None
        self._attr_extra_state_attributes = {}
        self.source_key = name

    def _async_update_from_coordinator(self) -> None:
        words = (self.coordinator.data or {}).get(self.source_key)
        if words is None:
            self._attr_native_value = None
            self._attr_extra_state_attributes = {}
        else:
            schedule = decode_schedule(words)
            self._attr_native_value = next_switch(schedule, dt_util.now())
            self._attr_extra_state_attributes = schedule_as_attributes(schedule)

        if self.hass is not None:
            self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._async_update_from_coordinator()


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up Solvis sensor entities."""
    await async_setup_solvis_entities(
        hass,
        entry,
        async_add_entities,
        entity_cls=SolvisSensor,
        input_type=0,  # sensor
    )

    # Setup SolvisDerivativeSensor
    coordinator: SolvisModbusCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    host = entry.data.get(CONF_HOST)
    name = entry.data.get(CONF_NAME)

    device_info = generate_device_info(entry, host, name)

    sdc_instances: list[SolvisDerivativeSensor] = []
    for key, cfg in DERIVATIVE_SENSORS.items():
        sdc_instances.append(
            SolvisDerivativeSensor(
                coordinator=coordinator,
                device_info=device_info,
                host=host,
                name=key,
                source_keys=cfg["source_keys"],
                unit=cfg["unit"],
                device_class=cfg["device_class"],
                state_class=cfg["state_class"],
                entity_category=cfg.get("entity_category"),
                suggested_display_precision=cfg.get("suggested_display_precision", 2),
                compute_mode=cfg.get("compute_mode", "sum"),
                modbus_address=REGISTER_ADDRESSES_BY_NAME[cfg["source_keys"][0]],
            )
        )

    # Setup one SolvisScheduleSensor for every retained Wochenplan.
    for key in SCHEDULES:
        sdc_instances.append(
            SolvisScheduleSensor(
                coordinator=coordinator,
                device_info=device_info,
                host=host,
                name=key,
                modbus_address=REGISTER_ADDRESSES_BY_NAME[key],
            )
        )

    async_add_entities(sdc_instances)


class SolvisSensor(SolvisEntity, SensorEntity):
    """Representation of a Solvis sensor."""

    def __init__(
        self,
        coordinator: SolvisModbusCoordinator,
        device_info: DeviceInfo,
        host: str,
        name: str,
        unit_of_measurement: str | None = None,
        device_class: str | None = None,
        state_class: str | None = None,
        entity_category: str | None = None,
        enabled_by_default: bool = True,
        data_processing: int = 0,
        poll_rate: bool = False,
        modbus_address: int | None = None,
        suggested_precision: int | None = 1,
    ) -> None:
        """Initialize the Solvis sensor."""
        super().__init__(
            coordinator,
            device_info,
            host,
            name,
            modbus_address,
            enabled_by_default,
            data_processing,
            poll_rate,
        )

        self._attr_native_value = None
        self._attr_entity_category = EntityCategory.DIAGNOSTIC if entity_category == "diagnostic" else None
        self.device_class = device_class
        self.state_class = state_class
        self._attr_native_unit_of_measurement = unit_of_measurement
        self.suggested_display_precision = suggested_precision

    def _update_value(self, value, extra_attrs):
        self._attr_native_value = value
        self._attr_extra_state_attributes = {"unprocessed_value": value}
        _LOGGER.debug(f"[{self._response_key}] Successfully updated native value: {self._attr_native_value} (Raw: {value})")

    def _reset_value(self):
        self._attr_extra_state_attributes = {}
