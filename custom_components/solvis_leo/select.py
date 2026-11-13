"""
Solvis Select Entity.
"""

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .coordinator import SolvisModbusCoordinator
from .registers import EntityType
from .utils.helpers import async_setup_solvis_entities
from .entity import SolvisEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up Solvis select entities."""

    await async_setup_solvis_entities(
        hass,
        entry,
        async_add_entities,
        entity_cls=SolvisSelect,
        input_type=EntityType.SELECT,
    )


class SolvisSelect(SolvisEntity, SelectEntity):
    """Representation of a Solvis select entity."""

    def __init__(
        self,
        coordinator: SolvisModbusCoordinator,
        device_info: DeviceInfo,
        host: str,
        name: str,
        enabled_by_default: bool = True,
        options: tuple = None,
        modbus_address: int = None,
    ) -> None:
        """Initialize the Solvis select entity."""
        super().__init__(
            coordinator,
            device_info,
            host,
            name,
            modbus_address,
            enabled_by_default,
        )

        self._attr_current_option = None
        self._attr_options = options if options is not None else []  # Set the options for the select entity

    def _update_value(self, value, extra_attrs):
        self._attr_current_option = str(value)
        self._attr_extra_state_attributes = extra_attrs
        _LOGGER.debug(f"[{self._response_key}] Successfully updated current option: {self._attr_current_option} (Raw: {value})")

    def _reset_value(self):
        self._attr_extra_state_attributes = {}

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        try:
            option_value = int(option)
        except ValueError as e:
            raise ServiceValidationError(f"Invalid option: {option}") from e
        await self.coordinator.async_write_register(self._response_key, option_value)
