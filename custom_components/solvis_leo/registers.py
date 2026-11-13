"""Typed, immutable descriptions of the SC3 register surface."""

from dataclasses import dataclass
from enum import IntEnum, StrEnum

from homeassistant.const import Platform


class EntityType(IntEnum):
    SENSOR = 0
    SELECT = 1
    NUMBER = 2
    SWITCH = 3
    BINARY_SENSOR = 4
    UPDATE = 5
    BLOCK = 6

    @property
    def domain(self) -> Platform | None:
        """Raw blocks have dedicated consumers instead of a generic entity."""
        return None if self is EntityType.BLOCK else Platform(self.name.lower())


class RegisterType(IntEnum):
    INPUT = 1
    HOLDING = 2


class PollingGroup(IntEnum):
    DEFAULT = 0
    SLOW = 1
    HIGH = 2


class DataType(StrEnum):
    INT16 = "INT16"
    UINT32 = "UINT32"


@dataclass(frozen=True)
class ModbusFieldConfig:
    """Metadata shared by entity setup, polling, read-back and documentation."""

    name: str
    address: int
    unit: str | None
    device_class: str | None
    state_class: str | None
    multiplier: float = 0.1
    absolute_value: bool = False
    register: RegisterType = RegisterType.INPUT
    entity_category: str | None = None
    enabled_by_default: bool = True
    range_data: tuple[float, float] | None = None
    step_size: float | None = None
    options: tuple[str, ...] | None = None
    input_type: EntityType = EntityType.SENSOR
    poll_rate: PollingGroup = PollingGroup.DEFAULT
    byte_swap: bool = False
    suggested_precision: int | None = 1
    count: int = 1
    datatype: DataType = DataType.INT16

    def __post_init__(self) -> None:
        """Reject unknown roles/encodings, including callers outside const.py."""
        for field, enum in (("register", RegisterType), ("input_type", EntityType), ("poll_rate", PollingGroup), ("datatype", DataType)):
            object.__setattr__(self, field, enum(getattr(self, field)))
