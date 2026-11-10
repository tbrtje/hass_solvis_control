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

- [Anlagenschema dashboard](frontend/README.md) — local Heizung, Warmwasser and
  Wärmepumpe views in the Solvis Portal style, using existing entities.
- [Register table](supported-entities.md) — generated from `REGISTERS`.
- [Polling groups](polling-groups.md) — generated from `REGISTERS`.
- [Polling behaviour](docs/polling.md) — disabled entities and shared register
  dependencies for calculated sensors and Wochenpläne.
- [Developer tools](tools/README.md) — the read-only SC3 register inventory tool.
- [Modbus scan action](docs/modbus-scan.md) — discover registers directly from
  Home Assistant with `solvis_leo.scan_modbus_range`.
- [Calculated warm water thermal power](docs/warm-water-power.md) — a separate
  S2/S15/S18 estimate and the observed zero readings from register 33549.

After changing `REGISTERS`, refresh the generated reference:

```sh
python -m tools.generate_docs --write
```

Use `python -m tools.generate_docs --check` to verify that the committed tables
are current.
