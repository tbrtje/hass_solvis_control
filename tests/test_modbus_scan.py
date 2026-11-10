"""SC3 range discovery handles rejected blocks without inventing readings."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from pymodbus.exceptions import ConnectionException, ModbusException

from custom_components.solvis_leo import modbus_scan


class Response:
    def __init__(self, registers=None, exception_code=None):
        self.registers = registers
        self.exception_code = exception_code

    def isError(self):
        return self.exception_code is not None


class ScanClient:
    """Only expose read functions; any write would fail the test."""

    def __init__(self, handler=None, connect_result=True):
        self.handler = handler or (lambda kind, address, count: Response(list(range(address, address + count))))
        self.connect_result = connect_result
        self.calls = []
        self.closed = False

    async def connect(self):
        if isinstance(self.connect_result, Exception):
            raise self.connect_result
        return self.connect_result

    async def _read(self, kind, address, count, unit):
        self.calls.append((kind, address, count, unit))
        answer = self.handler(kind, address, count)
        if isinstance(answer, Exception):
            raise answer
        return answer

    async def read_input_registers(self, address, *, count, device_id=1):
        return await self._read("input", address, count, device_id)

    async def read_holding_registers(self, address, *, count, device_id=1):
        return await self._read("holding", address, count, device_id)

    def close(self):
        self.closed = True


def install_client(monkeypatch, client):
    monkeypatch.setattr(modbus_scan, "create_modbus_client", lambda **kwargs: client)


async def test_range_scan_preserves_unsigned_and_signed_formats(monkeypatch):
    client = ScanClient(lambda *args: Response([0, 32767, 32768, 65535]))
    install_client(monkeypatch, client)

    result = await modbus_scan.scan_modbus_range("sc3", 502, 10, 13, "input", delay=0, batch_size=4)

    assert [row["raw_uint16"] for row in result["results"]] == [0, 32767, 32768, 65535]
    assert [row["int16"] for row in result["results"]] == [0, 32767, -32768, -1]
    assert result["results"][-1] == {
        "register": 13, "type": "input", "raw_uint16": 65535, "int16": -1,
        "factor10": -0.1, "hex": "0xFFFF", "binary": "1111111111111111",
    }
    assert result["errors"] == []
    assert result["aborted"] is False
    assert client.closed


async def test_scan_covers_both_types_and_inclusive_tail_without_overread(monkeypatch):
    client = ScanClient()
    install_client(monkeypatch, client)

    result = await modbus_scan.scan_modbus_range("sc3", 502, 10, 14, slave_id=7, batch_size=3, delay=0)

    assert client.calls == [
        ("input", 10, 3, 7), ("input", 13, 2, 7),
        ("holding", 10, 3, 7), ("holding", 13, 2, 7),
    ]
    assert [(r["type"], r["register"]) for r in result["results"]] == [
        (kind, address) for kind in ("input", "holding") for address in range(10, 15)
    ]


async def test_sc3_batch_rejection_falls_back_and_records_only_unreadable_addresses(monkeypatch):
    def answer(kind, address, count):
        if count > 1 or address == 101:
            return Response(exception_code=2)
        return Response([address])

    client = ScanClient(answer)
    install_client(monkeypatch, client)
    sleep = AsyncMock()
    monkeypatch.setattr(modbus_scan, "sleep", sleep)

    result = await modbus_scan.scan_modbus_range("sc3", 502, 100, 102, "holding", batch_size=3, delay=0.05)

    assert client.calls == [
        ("holding", 100, 3, 1), ("holding", 100, 1, 1),
        ("holding", 101, 1, 1), ("holding", 102, 1, 1),
    ]
    assert [row["register"] for row in result["results"]] == [100, 102]
    assert result["errors"] == [{
        "register": 101, "type": "holding", "count": 1,
        "error": "Modbus exception response", "exception_code": 2,
    }]
    assert sleep.await_count == 4
    assert all(call.args == (0.05,) for call in sleep.await_args_list)


@pytest.mark.parametrize("response", [
    None, Response([]), Response([1]), Response([1, 2, 3]), Response(None),
    Response([-1, 2]), Response([65536, 2]), Response([True, 2]), Response([1.5, 2]),
])
async def test_malformed_batches_are_never_reported_as_measurements(monkeypatch, response):
    client = ScanClient(lambda kind, address, count: response if count > 1 else Response([address]))
    install_client(monkeypatch, client)

    result = await modbus_scan.scan_modbus_range("sc3", 502, 20, 21, "input", delay=0, batch_size=2)

    assert [row["raw_uint16"] for row in result["results"]] == [20, 21]
    assert result["errors"] == []


async def test_empty_single_response_is_reported_once(monkeypatch):
    client = ScanClient(lambda *args: None)
    install_client(monkeypatch, client)

    result = await modbus_scan.scan_modbus_range("sc3", 502, 20, 20, "input", delay=0)

    assert result["results"] == []
    assert result["errors"] == [{"register": 20, "type": "input", "count": 1, "error": "Empty response"}]
    assert len(client.calls) == 1


@pytest.mark.parametrize("error", [ConnectionException("lost"), ModbusException("lost"), TimeoutError("lost"), OSError("lost")])
async def test_transport_failure_returns_partial_results_and_stops(monkeypatch, error):
    client = ScanClient(lambda kind, address, count: Response([10]) if address == 10 else error)
    install_client(monkeypatch, client)

    result = await modbus_scan.scan_modbus_range("sc3", 502, 10, 12, batch_size=1, delay=0)

    assert [row["register"] for row in result["results"]] == [10]
    assert result["errors"][0]["register"] == 11
    assert result["errors"][0]["type"] == "input"
    assert result["aborted"] is True
    assert len(client.calls) == 2
    assert client.closed


@pytest.mark.parametrize("connect_result", [False, ConnectionException("offline")])
async def test_failed_connection_closes_the_client(monkeypatch, connect_result):
    client = ScanClient(connect_result=connect_result)
    install_client(monkeypatch, client)

    with pytest.raises(ConnectionException):
        await modbus_scan.scan_modbus_range("sc3", 502, 10, 10)

    assert client.calls == []
    assert client.closed


async def test_cancellation_closes_the_scan_connection(monkeypatch):
    client = ScanClient()
    install_client(monkeypatch, client)
    monkeypatch.setattr(modbus_scan, "sleep", AsyncMock(side_effect=asyncio.CancelledError))

    with pytest.raises(asyncio.CancelledError):
        await modbus_scan.scan_modbus_range("sc3", 502, 10, 20)

    assert client.closed


async def test_pymodbus_38_slave_keyword_is_supported(monkeypatch):
    class LegacyClient(ScanClient):
        async def read_input_registers(self, address, *, count, slave=1):
            return await self._read("input", address, count, slave)

        async def read_holding_registers(self, address, *, count, slave=1):
            return await self._read("holding", address, count, slave)

    client = LegacyClient()
    install_client(monkeypatch, client)

    await modbus_scan.scan_modbus_range("sc3", 502, 65535, 65535, slave_id=7, delay=0)

    assert client.calls == [("input", 65535, 1, 7), ("holding", 65535, 1, 7)]
