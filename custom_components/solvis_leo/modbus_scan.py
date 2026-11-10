"""Read-only discovery of SC3 input and holding registers."""

from asyncio import sleep
from collections import deque
from inspect import signature
from typing import Any

from pymodbus.exceptions import ConnectionException, ModbusException

from .utils.helpers import create_modbus_client


def _register_values(response: Any, count: int) -> tuple[list[int] | None, dict]:
    """Accept only complete UInt16 responses; return errors for single reads."""
    if response is None:
        return None, {"error": "Empty response"}
    if response.isError():
        code = getattr(response, "exception_code", None)
        return None, {"error": "Modbus exception response", "exception_code": code}

    values = getattr(response, "registers", None)
    if not isinstance(values, (list, tuple)) or len(values) != count:
        return None, {"error": f"Expected {count} register(s) in the response"}
    if any(type(value) is not int or not 0 <= value <= 65535 for value in values):
        return None, {"error": "Response contains values outside UInt16"}
    return list(values), {}


def _format_value(address: int, register_type: str, raw: int) -> dict:
    """Keep raw values alongside possible signed and scaled interpretations."""
    signed = raw if raw < 32768 else raw - 65536
    return {
        "register": address,
        "type": register_type,
        "raw_uint16": raw,
        "int16": signed,
        "factor10": signed / 10,
        "hex": f"0x{raw:04X}",
        "binary": f"{raw:016b}",
    }


async def scan_modbus_range(
    host: str,
    port: int,
    start_address: int,
    end_address: int,
    register_type: str = "both",
    slave_id: int = 1,
    delay: float = 0.05,
    batch_size: int = 20,
) -> dict[str, Any]:
    """Scan validated inclusive bounds, falling back to individual SC3 reads.

    A scan owns a separate client and never changes the polling coordinator.
    Protocol rejections are local to a register. A transport failure aborts the
    remaining scan and returns the readings already collected.
    """
    register_types = ("input", "holding") if register_type == "both" else (register_type,)
    result = {
        "host": host,
        "port": port,
        "slave_id": slave_id,
        "start_address": start_address,
        "end_address": end_address,
        "register_type": register_type,
        "batch_size": batch_size,
        "delay": delay,
        "results": [],
        "errors": [],
        "aborted": False,
    }
    client = create_modbus_client(host=host, port=port, retries=0)
    try:
        if not await client.connect():
            raise ConnectionException("Could not connect to the SC3 controller")

        # pymodbus 3.10 renamed slave to device_id; both versions are supported
        # by this integration's pymodbus>=3.8 requirement.
        unit_key = "device_id" if "device_id" in signature(client.read_input_registers).parameters else "slave"
        for current_type in register_types:
            read = client.read_input_registers if current_type == "input" else client.read_holding_registers
            pending = deque(
                (address, min(batch_size, end_address - address + 1))
                for address in range(start_address, end_address + 1, batch_size)
            )
            while pending:
                address, count = pending.popleft()
                try:
                    response = await read(address=address, count=count, **{unit_key: slave_id})
                except (ModbusException, OSError, TimeoutError) as error:
                    result["errors"].append({
                        "register": address, "type": current_type,
                        "count": count, "error": str(error),
                    })
                    result["aborted"] = True
                    return result

                if delay:
                    await sleep(delay)

                values, error = _register_values(response, count)
                if values is not None:
                    result["results"].extend(
                        _format_value(address + offset, current_type, raw)
                        for offset, raw in enumerate(values)
                    )
                elif count > 1:
                    # SC3 rejects many reads that do not start at a GLT block's
                    # base address, even when some addresses in a batch exist.
                    pending.extendleft((single, 1) for single in reversed(range(address, address + count)))
                else:
                    result["errors"].append({
                        "register": address, "type": current_type, "count": 1, **error,
                    })
        return result
    finally:
        client.close()
