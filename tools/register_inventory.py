"""Read the SC3 register map over both Modbus read function codes."""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ModbusException

DEFAULT_REGISTER_MAP = Path(__file__).with_name("sc3_glt_register_map.json")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="SC3 controller hostname or IP address")
    parser.add_argument("--port", type=int, default=502, help="Modbus TCP port (default: 502)")
    parser.add_argument("--device-id", type=int, default=1, help="Modbus device id (default: 1)")
    parser.add_argument("--timeout", type=float, default=3, help="Per-request timeout in seconds (default: 3)")
    parser.add_argument("--map", type=Path, default=DEFAULT_REGISTER_MAP, help="JSON register map to probe")
    parser.add_argument("--output", type=Path, required=True, help="Inventory JSON destination")
    return parser.parse_args(argv)


def answer(response: Any, count: int) -> dict[str, Any]:
    if response is None:
        return {"detail": "empty response", "status": "malformed_response"}

    if response.isError():
        exception_code = getattr(response, "exception_code", None)
        if exception_code == 2:
            return {"exception_code": exception_code, "status": "illegal_address"}
        return {"exception_code": exception_code, "status": "modbus_error"}

    registers = getattr(response, "registers", None)
    if registers is None:
        return {"detail": "response has no registers", "status": "malformed_response"}
    if len(registers) != count:
        status = "malformed_response" if len(registers) < count else "unexpected_encoding"
        return {
            "detail": f"expected {count} registers, got {len(registers)}",
            "status": status,
            "values": list(registers),
        }

    values = list(registers)
    if any(isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 0xFFFF for value in values):
        return {
            "status": "unexpected_encoding",
            "values": [{"representation": repr(value), "type": type(value).__name__} for value in values],
        }
    return {
        "nonzero": any(value != 0 for value in values),
        "status": "answer",
        "values": values,
    }


async def read_result(read: Callable[..., Any], address: int, count: int, device_id: int) -> dict[str, Any]:
    try:
        response = await read(address, count=count, device_id=device_id)
    except (ModbusException, OSError, TimeoutError) as error:
        return {
            "error": type(error).__name__,
            "message": str(error),
            "status": "communication_error",
        }
    return answer(response, count)


async def async_main(
    argv: Sequence[str] | None = None,
    *,
    client_factory: Callable[..., Any] = AsyncModbusTcpClient,
) -> int:
    args = parse_args(argv)
    register_map_document = json.loads(args.map.read_text(encoding="utf-8"))
    register_map = register_map_document.get("registers", []) if isinstance(register_map_document, dict) else register_map_document
    client = client_factory(args.host, port=args.port, timeout=args.timeout, retries=0)
    connection_error: dict[str, Any] | None = None

    try:
        try:
            connected = await client.connect()
        except (ModbusException, OSError, TimeoutError) as error:
            connected = False
            connection_error = {
                "error": type(error).__name__,
                "message": str(error),
                "status": "communication_error",
            }
        if not connected and connection_error is None:
            connection_error = {"message": "initial connection failed", "status": "communication_error"}

        registers = []
        for register in register_map:
            address = register["address"]
            count = register.get("count", 1)
            if connection_error is None:
                holding = await read_result(client.read_holding_registers, address, count, args.device_id)
                input_register = await read_result(client.read_input_registers, address, count, args.device_id)
            else:
                holding = dict(connection_error)
                input_register = dict(connection_error)
            inventory_register = {
                "address": address,
                "count": count,
                "holding": holding,
                "input": input_register,
            }
            if "name" in register:
                inventory_register["name"] = register["name"]
            if "documented" in register:
                inventory_register["documented"] = register["documented"]
            registers.append(inventory_register)

        inventory = {
            "schema_version": 1,
            "controller": {"host": args.host, "port": args.port, "device_id": args.device_id},
            "registers": registers,
        }
        if isinstance(register_map_document, dict):
            inventory["register_map"] = {
                "schema_version": register_map_document.get("schema_version"),
                "source": register_map_document.get("source"),
            }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        statuses = Counter(result["status"] for register in registers for result in (register["holding"], register["input"]))
        print(f"Wrote {len(registers)} registers to {args.output}: {dict(sorted(statuses.items()))}")
        return 1 if connection_error is not None else 0
    finally:
        client.close()


def main() -> int:
    return asyncio.run(async_main())


if __name__ == "__main__":
    raise SystemExit(main())
