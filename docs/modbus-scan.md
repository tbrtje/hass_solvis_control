# Modbus range scan action

`solvis_leo.scan_modbus_range` reads an inclusive address range on the configured
SC3. It is a manual discovery tool for registers that are not yet represented by
entities. It uses Modbus FC04 (input registers), FC03 (holding registers), or both.

After installing this integration version, restart Home Assistant to load the new
action. Open **Tools → Actions** (called **Developer Tools → Actions** before
2026.8), then choose **SolvisLeo 180 Control: Modbus-Adressbereich scannen** in a
German UI, or **Scan Modbus range** in English. The action has a visual form and
can also be called from scripts and automations.

For example, paste this into the Actions tool's YAML editor:

```yaml
action: solvis_leo.scan_modbus_range
data:
  start_address: 33024
  end_address: 33041
  register_type: input
  slave_id: 1
  batch_size: 20
  delay: 0.05
```

The Actions tool displays the returned data. In a script or automation, add
`response_variable: register_scan` next to `action` and `data` to use the response
in later steps.

## Fields

| Field | Default | Meaning |
| --- | --- | --- |
| `config_entry_id` | The sole loaded entry | Explicit target if multiple entries are loaded; the UI selector lists SolvisLeo 180 entries. |
| `start_address` | Required | First zero-based Modbus address, 0–65535. |
| `end_address` | Required | Last address, inclusive, from the start address through 65535. |
| `register_type` | `both` | `input`, `holding`, or `both`. |
| `slave_id` | `1` | Modbus device/unit ID, 0–255. This field keeps the name used by the reference action. |
| `batch_size` | `20` | 1–125 consecutive registers per request. |
| `delay` | `0.05` | Pause in seconds after each response, including rejected batches; 0–5. |

The target must be a loaded entry of this integration. Connection details come
from that entry. The action remains registered when the Anlage is unavailable,
and reports a clear error if no entry is loaded. Only one scan per entry can run
at a time.

## Response

The response includes the connection and scan options, `config_entry_id`,
`results`, `errors`, and `aborted`. Each readable word has the following fields;
this example illustrates the representations for the raw word 65535:

```json
{
  "register": 33024,
  "type": "input",
  "raw_uint16": 65535,
  "int16": -1,
  "factor10": -0.1,
  "hex": "0xFFFF",
  "binary": "1111111111111111"
}
```

`int16` interprets the sign bit, and `factor10` divides that signed value by ten.
These are possible interpretations, not confirmed temperatures, units or scaling.
The scan does not apply entity-specific byte swapping or decode multiword values.

Rejected or malformed batches fall back to individual reads, without treating
the rejected batch itself as an unreadable register. Failed individual reads are
listed in `errors` with the address, register type, count and error description.
Modbus exception responses also include `exception_code`.

A transport error stops the scan: `aborted` becomes `true`, the failed request is
listed in `errors`, and earlier results remain available. An initial connection
failure raises an action error. The scan connection is closed on completion,
failure and cancellation.

## SC3 behaviour

The GLT block accepts only documented block base addresses as read starts.
A successful batch may return words whose addresses cannot be read separately.
Some block registers also require a particular count. For discovery of a known
block, choose its base address and count; use the [register inventory CLI](../tools/README.md)
for a repeatable inventory using the documented block counts.

Large ranges add many controller requests, especially when rejected batches fall
back to individual reads. Start with a small range and increase it as needed;
`both` reads each address over both function codes. The scanner uses a separate
connection and does not modify polling, learned availability, registers or entities.

The action is adapted from the [upstream range-scan commit](https://github.com/tbrtje/hass_solvis_control/commit/509e35cd4863f813f74f8117cdbefefa7f4fd348),
using this fork's `solvis_leo` domain and connection settings. The integration uses
PyModbus 3.15.0 with `device_id`. The action's existing `slave_id` option is mapped
to that parameter, so existing action calls remain valid.
