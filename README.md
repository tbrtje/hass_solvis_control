# SolvisLeo 180 Control

Home Assistant custom integration for one Anlage: a SolvisLeo 180 with an SC3
controller over Modbus TCP. It is a hard fork of the general Solvis integration;
other controllers and appliances are deliberately out of scope.

## Setup

Enable the SmartHome/GLT Modbus interface on the SC3, then add **SolvisLeo 180 Control**
in Home Assistant. Setup asks for the controller address, port, and the high,
default, and slow polling intervals. They can be changed later in the integration
options.

## Reference

- [Register table](supported-entities.md) — generated from `REGISTERS`.
- [Polling groups](polling-groups.md) — generated from `REGISTERS`.
- [Developer tools](tools/README.md) — the read-only SC3 register inventory tool.

After changing `REGISTERS`, refresh the generated reference:

```sh
python -m tools.generate_docs --write
```

Use `python -m tools.generate_docs --check` to verify that the committed tables
are current.
