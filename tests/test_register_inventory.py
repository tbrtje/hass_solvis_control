import json
from pathlib import Path
from typing import Any

import pytest
from pymodbus.exceptions import ModbusIOException

from tools.register_inventory import async_main

REPOSITORY_ROOT = Path(__file__).parents[1]


class SuccessfulResponse:
    def __init__(self, registers):
        self.registers = registers

    def isError(self):
        return False


class SuccessfulClient:
    def __init__(self, host, **kwargs):
        self.connected = False

    async def connect(self) -> bool:
        self.connected = True
        return True

    async def read_holding_registers(self, address, *, count, device_id) -> Any:
        return SuccessfulResponse([11] * count)

    async def read_input_registers(self, address, *, count, device_id) -> Any:
        return SuccessfulResponse([22] * count)

    def close(self):
        self.connected = False


class IllegalAddressResponse:
    exception_code = 2

    def isError(self):
        return True


class IllegalHoldingClient(SuccessfulClient):
    async def read_holding_registers(self, address, *, count, device_id):
        return IllegalAddressResponse()


class CommunicationErrorHoldingClient(SuccessfulClient):
    async def read_holding_registers(self, address, *, count, device_id):
        raise ModbusIOException("controller timed out")


class MissingRegistersResponse:
    def isError(self):
        return False


class MalformedHoldingClient(SuccessfulClient):
    async def read_holding_registers(self, address, *, count, device_id):
        return MissingRegistersResponse()


class UnexpectedEncodingHoldingClient(SuccessfulClient):
    async def read_holding_registers(self, address, *, count, device_id):
        return SuccessfulResponse(["not-a-word"])


class SurplusWordsHoldingClient(SuccessfulClient):
    async def read_holding_registers(self, address, *, count, device_id):
        return SuccessfulResponse([11] * (count + 1))


class FailedConnectionClient(SuccessfulClient):
    async def connect(self) -> bool:
        return False


@pytest.mark.asyncio
async def test_cli_records_both_read_function_codes(tmp_path):
    register_map = tmp_path / "register-map.json"
    register_map.write_text(
        json.dumps([{"address": 32768, "count": 2, "name": "controller_unix_time"}]),
        encoding="utf-8",
    )
    output = tmp_path / "inventory.json"

    exit_code = await async_main(
        ["--host", "controller.test", "--map", str(register_map), "--output", str(output)],
        client_factory=SuccessfulClient,
    )

    assert exit_code == 0
    assert json.loads(output.read_text(encoding="utf-8"))["registers"] == [
        {
            "address": 32768,
            "count": 2,
            "name": "controller_unix_time",
            "holding": {"nonzero": True, "status": "answer", "values": [11, 11]},
            "input": {"nonzero": True, "status": "answer", "values": [22, 22]},
        }
    ]


@pytest.mark.asyncio
async def test_cli_distinguishes_illegal_address_rejections(tmp_path):
    register_map = tmp_path / "register-map.json"
    register_map.write_text(
        json.dumps([{"address": 33045, "count": 1, "name": "digin_error"}]),
        encoding="utf-8",
    )
    output = tmp_path / "inventory.json"

    await async_main(
        ["--host", "controller.test", "--map", str(register_map), "--output", str(output)],
        client_factory=IllegalHoldingClient,
    )

    result = json.loads(output.read_text(encoding="utf-8"))["registers"][0]
    assert result["holding"] == {"exception_code": 2, "status": "illegal_address"}


@pytest.mark.asyncio
async def test_cli_records_communication_errors_and_continues(tmp_path):
    register_map = tmp_path / "register-map.json"
    register_map.write_text(
        json.dumps([{"address": 33024, "count": 1, "name": "warm_water_buffer_temp_s1"}]),
        encoding="utf-8",
    )
    output = tmp_path / "inventory.json"

    await async_main(
        ["--host", "controller.test", "--map", str(register_map), "--output", str(output)],
        client_factory=CommunicationErrorHoldingClient,
    )

    result = json.loads(output.read_text(encoding="utf-8"))["registers"][0]
    assert result["holding"] == {
        "error": "ModbusIOException",
        "message": "Modbus Error: [Input/Output] controller timed out",
        "status": "communication_error",
    }
    assert result["input"]["status"] == "answer"


@pytest.mark.asyncio
async def test_cli_records_malformed_responses(tmp_path):
    register_map = tmp_path / "register-map.json"
    register_map.write_text(
        json.dumps([{"address": 33024, "count": 1, "name": "warm_water_buffer_temp_s1"}]),
        encoding="utf-8",
    )
    output = tmp_path / "inventory.json"

    await async_main(
        ["--host", "controller.test", "--map", str(register_map), "--output", str(output)],
        client_factory=MalformedHoldingClient,
    )

    result = json.loads(output.read_text(encoding="utf-8"))["registers"][0]
    assert result["holding"] == {"detail": "response has no registers", "status": "malformed_response"}


@pytest.mark.asyncio
async def test_cli_reports_unexpected_word_encodings(tmp_path):
    register_map = tmp_path / "register-map.json"
    register_map.write_text(
        json.dumps([{"address": 33024, "count": 1, "name": "warm_water_buffer_temp_s1"}]),
        encoding="utf-8",
    )
    output = tmp_path / "inventory.json"

    await async_main(
        ["--host", "controller.test", "--map", str(register_map), "--output", str(output)],
        client_factory=UnexpectedEncodingHoldingClient,
    )

    result = json.loads(output.read_text(encoding="utf-8"))["registers"][0]
    assert result["holding"] == {
        "status": "unexpected_encoding",
        "values": [{"representation": "'not-a-word'", "type": "str"}],
    }


@pytest.mark.asyncio
async def test_cli_reports_surplus_response_words(tmp_path):
    register_map = tmp_path / "register-map.json"
    register_map.write_text(json.dumps([{"address": 33024, "count": 1}]), encoding="utf-8")
    output = tmp_path / "inventory.json"

    await async_main(
        ["--host", "controller.test", "--map", str(register_map), "--output", str(output)],
        client_factory=SurplusWordsHoldingClient,
    )

    result = json.loads(output.read_text(encoding="utf-8"))["registers"][0]
    assert result["holding"] == {
        "detail": "expected 1 registers, got 2",
        "status": "unexpected_encoding",
        "values": [11, 11],
    }


@pytest.mark.asyncio
async def test_cli_records_failed_initial_connection_for_every_read(tmp_path):
    register_map = tmp_path / "register-map.json"
    register_map.write_text(json.dumps([{"address": 33024, "count": 1}]), encoding="utf-8")
    output = tmp_path / "inventory.json"

    exit_code = await async_main(
        ["--host", "controller.test", "--map", str(register_map), "--output", str(output)],
        client_factory=FailedConnectionClient,
    )

    assert exit_code == 1
    result = json.loads(output.read_text(encoding="utf-8"))["registers"][0]
    expected = {"message": "initial connection failed", "status": "communication_error"}
    assert result["holding"] == expected
    assert result["input"] == expected


@pytest.mark.asyncio
async def test_cli_default_map_covers_every_sc3_glt_base_address(tmp_path):
    output = tmp_path / "inventory.json"

    await async_main(
        ["--host", "controller.test", "--output", str(output)],
        client_factory=SuccessfulClient,
    )

    registers = json.loads(output.read_text(encoding="utf-8"))["registers"]
    documented_addresses = {register["address"] for register in registers if register["documented"]}
    expected_documented_addresses = {
        32768,
        32770,
        32771,
        *range(33024, 33045),
        *range(33280, 33299),
        *range(33536, 33557),
        33792,
        33793,
        *range(33798, 33839, 5),
        *range(34048, 34259, 42),
        *range(34304, 34321),
        *range(34560, 34563),
    }
    assert documented_addresses == expected_documented_addresses
    assert {register["address"] for register in registers if not register["documented"]} == {33045, 33299}
    message_addresses = {33793, *range(33798, 33839, 5)}
    assert {register["address"]: register["count"] for register in registers if register["address"] in message_addresses} == {address: 5 for address in message_addresses}


def test_committed_inventory_matches_default_register_map():
    register_map = json.loads((REPOSITORY_ROOT / "tools/sc3_glt_register_map.json").read_text(encoding="utf-8"))
    inventory = json.loads((REPOSITORY_ROOT / "inventory/solvisleo_180_sc3.json").read_text(encoding="utf-8"))

    assert inventory["register_map"] == {key: register_map[key] for key in ("schema_version", "source")}
    assert [{key: register[key] for key in ("address", "count", "documented")} for register in inventory["registers"]] == [
        {key: register[key] for key in ("address", "count", "documented")} for register in register_map["registers"]
    ]
