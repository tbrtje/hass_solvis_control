# Solvis Leo Control

A Home Assistant integration for one specific installation: a SolvisLeo 180 heat pump
on an SC3 controller, reached over Modbus TCP. It is a hard fork of a general-purpose
Solvis integration, deliberately narrowed to this one appliance.

## Language

### The installation

**Anlage**:
The physical heating installation as a whole — heat pump, stratified tank, heating
circuit and controller.
_Avoid_: system, plant, device (too vague; "device" means the HA device entry)

**SolvisLeo 180**:
The appliance this integration supports: an air-source heat pump with an integrated
180-litre stratified tank. Has no burner and no solar circuit.
_Avoid_: Leo (only in prose, never as an identifier), boiler

**SC3**:
The controller running the Anlage, and the Modbus endpoint. Its predecessor SC2 is
not supported.
_Avoid_: NBG (that is only the network board inside it)

### Modbus surface

**GLT block**:
The register region from address 32768 (`0x8000`) upward that the SC3 exports for
building-management use. Only addresses listed in the manufacturer's register map are
valid *start* addresses; a read beginning anywhere else is rejected, even inside a
block.
_Avoid_: high registers, GLT range

**Parameter space**:
The register region below 32768, holding configuration values such as heating curves
and setpoints. Not covered by the manufacturer's register map, but readable.
_Avoid_: low registers, config registers

**Block register**:
A GLT entry that spans several consecutive registers read in one request, such as a
Wochenplan or the controller clock. Its value is a sequence of words, not a number.
_Avoid_: multi-register, array register

**Fühler**:
A temperature sensor on the Anlage, identified by its Solvis label — `S1` (tank top),
`S4` (buffer top), `S9` (buffer bottom).
_Avoid_: probe, thermometer

### Heating

**Heizkreis**:
A circuit distributing heat into the building. This Anlage has exactly one, `HKR1`.
_Avoid_: heating loop, zone (a "zone" here is a tank zone)

**Speicherzone**:
A volume of the stratified tank between two Fühler, used to compute stored energy.
The Leo has two: 80 l between S1 and S4, 100 l between S4 and S9.
_Avoid_: layer, stratum, tank section

**Heizstab**:
The electric immersion heater — the Anlage's second heat generator alongside the heat
pump. In the manufacturer's register map it appears as `eheiz`.
_Avoid_: **burner** (this Anlage has none — the name is inherited from oil/gas models
and is factually wrong here), heat generator 2, heating rod

**Wärmemengenzähler**:
The heat-metering function of the controller, reporting flow and return temperature,
volume flow and thermal power for the Heizkreis. Abbreviated WMZ.
_Avoid_: heat meter, energy meter (ambiguous with the energy counters)

**Betriebsart**:
The mode a Heizkreis runs in — Automatik, Tagbetrieb, Absenkbetrieb, Standby, Eco or
Urlaub. Only Automatik follows the Wochenplan.
_Avoid_: mode, operating state, preset

### Scheduling

**Wochenplan**:
A weekly time programme held by the controller: seven days, three Slots per day. The
Anlage keeps six of them — one per Heizkreis, plus hot water, circulation and Eco.
_Avoid_: schedule, timer, time programme

**Slot**:
One start/stop pair within a Wochenplan day. A Slot whose start equals its stop is
unused.
_Avoid_: window, period, interval

**Viertelstundenindex**:
How a Slot boundary is encoded: 0 means 00:00, 95 means 23:45, one step is 15 minutes.
_Avoid_: quarter index, time code

### Measurements

**Thermal power** / **electrical power**:
Always distinguish these. A heat pump reports both — thermal output (`Pth`) and
electrical input (`Pel`) — and they differ by the coefficient of performance.
_Avoid_: power, output, consumption (each ambiguous on its own)

**Energy counter**:
A cumulative kWh total held by the controller, as opposed to an instantaneous power
reading.
_Avoid_: meter, total, Wärmemenge (used for both in the manufacturer's naming)
