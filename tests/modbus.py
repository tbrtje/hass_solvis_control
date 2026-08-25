"""Addressable Modbus test double backed by recorded controller responses."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Self

from pymodbus.exceptions import ConnectionException, ModbusIOException


class FakeModbusResponse:
    """Small response object matching the part of pymodbus the integration uses."""

    def __init__(self, registers: list[int], exception_code: int | None = None) -> None:
        self.registers = registers
        self.exception_code = exception_code

    def isError(self) -> bool:
        return self.exception_code is not None


class MalformedModbusResponse:
    """A non-error response which omits the required register payload."""

    def isError(self) -> bool:
        return False


class AddressableModbusClient:
    """Return recorded Modbus responses by function code and base address."""

    def __init__(self, responses: dict[tuple[str, int], dict]) -> None:
        self._responses = responses
        self._illegal_addresses: set[tuple[str, int]] = set()
        self._communication_errors: set[tuple[str, int]] = set()
        self._connection_losses: set[tuple[str, int]] = set()
        self._malformed_responses: set[tuple[str, int]] = set()
        self._timeouts: set[tuple[str, int]] = set()
        self._request_counts: dict[tuple[str, int], int] = {}
        self.connected = False
        self.DATATYPE = type("DATATYPE", (), {"INT16": "int16"})

    @classmethod
    def from_inventory(cls, *paths: Path) -> Self:
        responses = {}
        for path in paths:
            document = json.loads(path.read_text(encoding="utf-8"))
            responses.update({(register_type, register["address"]): register[register_type] for register in document["registers"] for register_type in ("holding", "input")})
        return cls(responses)

    async def read_input_registers(self, address: int, count: int):
        return self._read("input", address, count)

    async def read_holding_registers(self, address: int, count: int):
        return self._read("holding", address, count)

    async def connect(self) -> bool:
        self.connected = True
        return True

    def close(self) -> None:
        self.connected = False

    def convert_from_registers(self, registers: list[int], data_type: str, word_order: str) -> int:
        value = registers[0]
        return value - 0x10000 if value >= 0x8000 else value

    def fail(self, register_type: str, address: int) -> None:
        """Make one function-code/address pair raise a communication error."""
        self._communication_errors.add((register_type, address))

    def restore(self, register_type: str, address: int) -> None:
        """Restore the recorded response for one function-code/address pair."""
        key = (register_type, address)
        self._communication_errors.discard(key)
        self._connection_losses.discard(key)
        self._illegal_addresses.discard(key)
        self._malformed_responses.discard(key)
        self._timeouts.discard(key)

    def lose_connection(self, register_type: str, address: int) -> None:
        """Drop the connection while reading one function-code/address pair."""
        self._connection_losses.add((register_type, address))

    def request_count(self, register_type: str, address: int) -> int:
        """Return how often one function-code/address pair was requested."""
        return self._request_counts.get((register_type, address), 0)

    def reject(self, register_type: str, address: int) -> None:
        """Make one function-code/address pair return ILLEGAL DATA ADDRESS."""
        self._illegal_addresses.add((register_type, address))

    def malform(self, register_type: str, address: int) -> None:
        """Make one function-code/address pair return a malformed response."""
        self._malformed_responses.add((register_type, address))

    def timeout(self, register_type: str, address: int) -> None:
        """Make one function-code/address pair exceed its response timeout."""
        self._timeouts.add((register_type, address))

    def _read(self, register_type: str, address: int, count: int) -> FakeModbusResponse | MalformedModbusResponse:
        key = (register_type, address)
        self._request_counts[key] = self._request_counts.get(key, 0) + 1
        if key in self._connection_losses:
            self.connected = False
            raise ConnectionException(f"Connection lost at {register_type} register {address}")
        if (register_type, address) in self._communication_errors:
            raise ModbusIOException(f"Communication error at {register_type} register {address}")
        if key in self._timeouts:
            raise TimeoutError(f"Timeout at {register_type} register {address}")
        if (register_type, address) in self._malformed_responses:
            return MalformedModbusResponse()
        if (register_type, address) in self._illegal_addresses:
            return FakeModbusResponse([], exception_code=2)
        recorded = self._responses[(register_type, address)]
        if recorded["status"] == "illegal_address":
            return FakeModbusResponse([], exception_code=recorded["exception_code"])
        return FakeModbusResponse(recorded["values"][:count])
