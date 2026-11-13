"""
Solvis Number Entity.
"""

import logging
import math

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SolvisModbusCoordinator
from .registers import EntityType
from .utils.helpers import async_setup_solvis_entities
from .entity import SolvisEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up Solvis number entities."""

    await async_setup_solvis_entities(
        hass,
        entry,
        async_add_entities,
        entity_cls=SolvisNumber,
        input_type=EntityType.NUMBER,
    )


class SolvisNumber(SolvisEntity, NumberEntity):
    """Representation of a Solvis number entity."""

    def __init__(
        self,
        coordinator: SolvisModbusCoordinator,
        device_info: DeviceInfo,
        host: str,
        name: str,
        unit_of_measurement: str | None = None,
        device_class: str | None = None,
        state_class: str | None = None,
        enabled_by_default: bool = True,
        range_data: tuple = None,
        step_size: int | None = None,
        modbus_address: int = None,
        multiplier: float = 1,
    ) -> None:
        """Initialize the Solvis number entity."""
        super().__init__(
            coordinator,
            device_info,
            host,
            name,
            modbus_address,
            enabled_by_default,
        )

        self.multiplier = multiplier
        self.device_class = device_class
        self.state_class = state_class
        self.native_unit_of_measurement = unit_of_measurement

        if step_size is not None:
            self.native_step = step_size
        else:
            self.native_step = 1.0

        # Set min/max values if provided in range_data
        if range_data:
            self.native_min_value = range_data[0]
            self.native_max_value = range_data[1]

    def _update_value(self, value, extra_attrs) -> None:
        """Update the entity's value when data is available."""
        self._attr_native_value = value
        self._attr_extra_state_attributes = extra_attrs
        _LOGGER.debug(f"[{self._response_key}] Successfully updated native value: {self._attr_native_value} (Raw: {value})")

    def _reset_value(self) -> None:
        """Reset the entity's state when data is not available."""
        self._attr_extra_state_attributes = {}

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        if not math.isfinite(value):
            raise ServiceValidationError("The value must be finite")
        await self.coordinator.async_write_register(self._response_key, round(value / self.multiplier))
