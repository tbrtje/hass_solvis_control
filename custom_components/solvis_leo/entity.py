"""
Solvis Base Entity.

Version v2.1.0
"""

from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .utils.helpers import generate_unique_id, process_coordinator_data


class SolvisEntity(CoordinatorEntity):
    """Base class for all Solvis entities."""

    @property
    def available(self) -> bool:
        """Report both coordinator-wide and register-specific availability."""
        register_available = self.modbus_address is None or self.coordinator.is_register_available(self.modbus_address)
        return self.coordinator.last_update_success and register_available

    def __init__(
        self,
        coordinator,
        device_info,
        host: str,
        name: str,
        modbus_address: int = None,
        enabled_by_default: bool = True,
        data_processing: int = 0,
        poll_rate: bool = False,
    ) -> None:
        """Initialize the Solvis entity."""
        super().__init__(coordinator)
        self._host = host
        self.modbus_address = modbus_address
        self._response_key = name
        self.entity_registry_enabled_default = enabled_by_default
        self.device_info = device_info
        self._attr_has_entity_name = True
        self._attr_unique_id = generate_unique_id(modbus_address, name)
        self._attr_translation_key = name
        self.data_processing = data_processing
        self.poll_rate = poll_rate
        self._attr_available = False

    async def async_added_to_hass(self) -> None:
        """Publish the coordinator's first snapshot as soon as the entity is added."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        available, value, extra_attrs = process_coordinator_data(self.coordinator.data, self._response_key)
        if available is None:
            return
        self._attr_available = available
        if available:
            self._update_value(value, extra_attrs)
        else:
            self._reset_value()
        self.schedule_update_ha_state()

    def _update_value(self, value, extra_attrs):
        """Implement entity-specific value processing in subclasses."""
        raise NotImplementedError

    def _reset_value(self):
        """Optional: Reset value if data is not available."""
        pass
