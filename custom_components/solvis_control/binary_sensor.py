"""
Solvis Binary Sensor Entity.
"""

import logging

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.util import dt as dt_util

from .const import CONF_HOST, CONF_NAME, DATA_COORDINATOR, DOMAIN, REGISTER_ADDRESSES_BY_NAME, SCHEDULES
from .coordinator import SolvisModbusCoordinator
from .utils.helpers import async_setup_solvis_entities, conf_options_map, generate_device_info
from .utils.schedule import decode_schedule, is_active, next_switch
from .entity import SolvisEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up Solvis binary sensors entities."""

    await async_setup_solvis_entities(
        hass,
        entry,
        async_add_entities,
        entity_cls=SolvisBinarySensor,
        input_type=4,  # binary sensor
    )

    host = entry.data.get(CONF_HOST)
    if host is None:
        # async_setup_solvis_entities already reported this and bailed out
        return

    coordinator: SolvisModbusCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    device_info = generate_device_info(entry, host, entry.data.get(CONF_NAME))

    schedule_entities: list[SolvisScheduleBinarySensor] = []
    for key, cfg in SCHEDULES.items():
        option = cfg.get("conf_option", 0)
        if option and not entry.data.get(conf_options_map.get(option)):
            _LOGGER.debug(f"[{key}] Skipping schedule binary sensor: conf_option {option} not enabled.")
            continue
        schedule_entities.append(
            SolvisScheduleBinarySensor(
                coordinator=coordinator,
                device_info=device_info,
                host=host,
                name=f"{key}_active",
                source_key=key,
                modbus_address=REGISTER_ADDRESSES_BY_NAME[key],
            )
        )

    async_add_entities(schedule_entities)


class SolvisScheduleBinarySensor(SolvisEntity, BinarySensorEntity):
    """Whether a weekly schedule is inside one of its windows right now.

    The state flips on the slot boundary via a timer rather than on the poll tick,
    so the history timeline has clean edges instead of being smeared by up to one
    polling interval.
    """

    def __init__(
        self,
        coordinator: SolvisModbusCoordinator,
        device_info: DeviceInfo,
        host: str,
        name: str,
        source_key: str,
        modbus_address: int,
    ) -> None:
        super().__init__(
            coordinator,
            device_info,
            host,
            name,
            modbus_address=modbus_address,
            supported_version=coordinator.supported_version,
            enabled_by_default=False,
            data_processing=0,
            poll_rate=False,
        )

        self._attr_unique_id = f"{host}_{name}"
        self._attr_device_class = BinarySensorDeviceClass.RUNNING
        self._attr_is_on = None
        self.source_key = source_key
        self.coordinator = coordinator
        self._unsub_boundary = None

        self.coordinator.async_add_listener(self._async_refresh)

    @callback
    def _async_refresh(self, _now=None) -> None:
        """Recompute the state and arm a timer for the next slot boundary."""
        self._cancel_boundary_timer()

        words = (self.coordinator.data or {}).get(self.source_key)
        if words is None:
            self._attr_is_on = None
        else:
            schedule = decode_schedule(words)
            now = dt_util.now()
            self._attr_is_on = is_active(schedule, now)

            upcoming = next_switch(schedule, now)
            if upcoming is not None and self.hass is not None:
                self._unsub_boundary = async_track_point_in_time(self.hass, self._async_refresh, upcoming)

        if self.hass is not None:
            self.async_write_ha_state()

    def _cancel_boundary_timer(self) -> None:
        if self._unsub_boundary is not None:
            self._unsub_boundary()
            self._unsub_boundary = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._async_refresh()

    async def async_will_remove_from_hass(self) -> None:
        self._cancel_boundary_timer()
        await super().async_will_remove_from_hass()

    @callback
    def _handle_coordinator_update(self) -> None:
        return


class SolvisBinarySensor(SolvisEntity, BinarySensorEntity):
    """Representation of a Solvis sensor."""

    def __init__(
        self,
        coordinator: SolvisModbusCoordinator,
        device_info: DeviceInfo,
        host: str,
        name: str,
        hkr1_name: str | None = None,
        hkr2_name: str | None = None,
        hkr3_name: str | None = None,
        device_class: str | None = None,
        state_class: str | None = None,
        entity_category: str | None = None,
        enabled_by_default: bool = True,
        data_processing: int = 0,
        poll_rate: bool = False,
        supported_version: int = 1,
        modbus_address: int | None = None,
    ) -> None:
        """Initialize the Solvis sensor."""
        super().__init__(
            coordinator,
            device_info,
            host,
            name,
            modbus_address,
            supported_version,
            enabled_by_default,
            data_processing,
            poll_rate,
            hkr1_name=hkr1_name,
            hkr2_name=hkr2_name,
            hkr3_name=hkr3_name,
        )

        self.device_class = device_class
        self.state_class = state_class
        self._attr_is_on = False
        self._attr_entity_category = EntityCategory.DIAGNOSTIC if entity_category == "diagnostic" else None

    def _update_value(self, value, extra_attrs) -> None:
        """Update the entity's state when data is available."""
        self._attr_is_on = bool(value)
        self._attr_extra_state_attributes = {"unprocessed_value": value}
        _LOGGER.debug(f"[{self._response_key}] Successfully updated value: {self._attr_is_on} (Raw: {value})")

    def _reset_value(self) -> None:
        """Reset the entity's state when data is not available."""
        self._attr_extra_state_attributes = {}
