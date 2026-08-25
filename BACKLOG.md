# Backlog

Known issues and follow-ups that are understood but deliberately not fixed yet.
Each entry records what was verified, so the analysis does not have to be redone.

---

## 1. The "skip disabled entities" check never fires

**Status:** confirmed, not fixed
**Files:** `custom_components/solvis_leo/coordinator.py:146-153`

The coordinator builds the registry key as `f"{DOMAIN}.{register.name}"`, i.e.
`solvis_leo.warm_water_power`. Home Assistant assigns `<platform>.<object_id>`,
so the real id is `sensor.warm_water_power`. The lookup therefore always returns
`None` and the check is dead code — every register is polled regardless of whether
its entity is disabled.

This is structural, not incidental: `PLATFORMS` contains only `sensor`, `number`,
`select`, `switch`, `binary_sensor` and `update`. No platform ever produces an
entity id prefixed with the integration domain.

Verified against a real (not mocked) entity registry:

```
actual entity_id       : sensor.warm_water_power
disabled               : True
key used by coordinator: solvis_leo.warm_water_power
lookup result          : None
lookup by real id      : found, disabled=True
```

The existing tests cannot catch this because `tests/conftest.py` injects a
`dummy_entity_registry` rather than the real one.

**Impact:** on a SolvisLeo 180 with no extra options, 24 of 67 polled registers are
`enabled_by_default=False` — roughly a third of the Modbus traffic per cycle is
spent on entities nobody sees. Devices with more options enabled poll proportionally
more.

**Suggested fix:** resolve via `unique_id` instead of guessing the entity id, since
the integration already generates it deterministically:

```python
platform = PLATFORM_BY_INPUT_TYPE[register.input_type]
unique_id = generate_unique_id(register.address, register.supported_version, register.name)
entity_id = entity_registry.async_get_entity_id(platform, DOMAIN, unique_id)
```

**Caveat that must be handled:** this changes poll behaviour for *all* users, not
just the Leo. Registers whose entity is disabled would no longer appear in
`coordinator.data`. Harmless for ordinary entities (`process_coordinator_data`
reports "no update"), but `SolvisDerivativeSensor` computes from `coordinator.data`
and would silently stop working if a source register dropped out. All four current
sources (`warm_water_buffer_temp_s1`, `storage_reference_temp_s3`,
`heating_buffer_upper_temp_s4`, `heating_buffer_lower_temp_s9`) are
`enabled_by_default=True`, so this only bites if a user disables a storage sensor by
hand — but the fix should exempt derivative source registers from the skip.

---

## 2. Multipliers disagree with the SC3 GLT documentation

**Status:** discrepancy confirmed, intentionally not changed
**Files:** `custom_components/solvis_leo/const.py:679-806`

The SC3 GLT register map gives factor `0.1` for the whole `Q_*` / `P*_*` block. The
integration uses:

| Register | Address | Code | Doc | Deviation |
| --- | --- | --- | --- | --- |
| `Q_solar` … `Q_hk` | 33536-33541 | `multiplier=10` | `0.1` | 100× |
| `Pth_ww` (`warm_water_power`) | 33549 | `multiplier=1` | `0.1` | 10× |
| all other `P*_*` | — | `0.1` (default) | `0.1` | none |

Not changed on purpose: these definitions reference issues #115, #173 and #314,
which suggests they were corrected empirically against real SolvisMax hardware, and
`unit="kWh"` may already reconcile a different documented scale. Rescaling them would
silently rewrite every existing user's energy history.

**To resolve this, we need a device that returns non-zero values for the block** so
the true scale can be measured. It may also turn out to be model-dependent, in which
case it belongs in a per-model configuration rather than a global multiplier.

---

## 3. Four registers declared as holding inside an input-register block

**Status:** cosmetic inconsistency, harmless on tested hardware
**Files:** `custom_components/solvis_leo/const.py`

`solar_power` (33543), `heatpump_power_output_thermal` (33544),
`heatpump_power_input_electric` (33545) and `pv2heat_power_electric` (33548) use
`register=2` (holding, FC3), while every other register in the same GLT block uses
`register=1` (input, FC4).

Confirmed harmless on a SolvisLeo: the device answers both function codes with a
valid response. Worth aligning anyway, but only alongside a device test — some
controllers may only serve one of the two.

---

## 4. Weekly schedules: writing, and the day-1 assumption

**Status:** reading implemented; writing deliberately out of scope

The six schedules (34048, 34090, 34132, 34174, 34216, 34258) are read as one
42-register block each and exposed per plan as `sensor.<plan>_schedule` (next
switching time, full week in attributes) plus `binary_sensor.<plan>_active` for the
history timeline. Decoding lives in `custom_components/solvis_leo/utils/schedule.py`.

**Open:**

- **Writing.** Would need FC16 (`write_registers`), which the integration does not
  use, plus read-back verification — a bad write overwrites the user's heating
  programme.
- **"Tag 1" is assumed to be Monday** (`SCHEDULE_DAY_KEYS`). Not verified against
  hardware. If Solvis counts from Sunday, every day label is off by one; the fix is
  a one-line rotation of that tuple.
- **"Unused slot" encoding is assumed to be `start == stop`.** Slots with equal
  start and stop, and values outside 0..95, are dropped. If the controller marks
  unused slots differently, empty windows may appear.
- ~~42-register block reads are unverified on hardware.~~ **Confirmed working** on a
  SolvisLeo 180: `read_holding_registers(34174, count=42)` was answered with a
  well-formed 84-byte response, no exception code. One request instead of 42.
- **The SolvisLeo 180 does not export schedules at all.** All six plans read as 42
  zeros over *both* function codes, while the controller has time programmes stored
  and `hkr1_operating_mode` is 2 ("Automatik"), so they are actively in use. Same
  pattern as the `0x83xx` energy block: structurally readable, semantically empty.
  The code is correct; there is simply nothing to decode on this model.
  A wrong register type was ruled out with a control read: S1 (33024) returns the
  same value via FC3 and FC4, so the controller serves both identically.
- **Therefore the day-1 and unused-slot assumptions above remain unverifiable** until
  a device shows up that populates the block.
- DST: window edges use `ZoneInfo` wall-clock arithmetic, which is correct except in
  the repeated hour of the autumn switch, where `fold=0` is chosen.

Also still unimplemented, lower value: the per-message sub-registers (`UnixZeit H/L`,
`Par 1/2`) behind each `Meldung_N`. Only the message codes are read today.

---

## 5. SolvisLeo 180: energy/power block reports zero

**Status:** device-side, cause not yet established

On a SolvisLeo 180 the entire `0x83xx` block (`Q_*`, `P*_*`) returns a clean `0`
while the Solvis portal shows live values. Verified from the PDUs that this is not
an integration bug: the device answers `registers=[0]` with a valid, non-error
response on **both** function codes (FC4 for 33537/33549/33550, FC3 for
33544/33545). Temperatures and pump outputs on the same device read correctly, and
the heat pump was demonstrably running (charging pump A2 at 100%).

Two open leads:

1. The controller may only populate the block once its heat-metering function is
   enabled in the SC3 menu — a device setting, no code change needed.
2. The values may live in the `0x86xx` block instead. `HK_Pact` (34320, 0.1 kW) is
   the direct candidate; those registers were added but are gated behind
   `conf_option=5` (heat meter) and are still unverified on hardware.

A throwaway probe that reads every documented address on both function codes and
prints the non-zero ones was used for this analysis and can be recreated as needed.

---

## 6. Addressing model: only CSV base addresses are valid in the 0x8xxx block

**Status:** confirmed on hardware, no action required — but constrains future work

The controller does not expose a flat register space above `0x8000`. Only addresses
listed in the SC3 GLT map are valid *start* addresses; the length may vary. Probed
on a SolvisLeo 180:

```
FC4 34046 count=8 -> ILLEGAL DATA ADDRESS   (not a CSV address)
FC4 34048 count=8 -> ok                     (Wochenplan_HK_1 base)
FC4 34050 count=8 -> ILLEGAL DATA ADDRESS   (inside the block, but not a base)
```

34050 sits well inside the 34048..34089 plan and is still rejected, so this is about
the start address, not the range.

This retroactively explains why `digin_error` (33045) and `analog_out_o6` (33299)
answer with exception code 2: neither appears in the CSV.

**Consequence for the message sub-registers** (backlog item 4): `Meldung_N UnixZeit H/L`
and `Par 1/2` cannot be read individually — only as a block starting at the documented
`Meldung_N` base with `count=5`.
