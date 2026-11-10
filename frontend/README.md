# SolvisLeo 180 Anlagenschema

A self-contained Home Assistant dashboard card with three schematics: **Heizung**,
**Warmwasser** and **Wärmepumpe**. The drawings follow the Solvis Portal's white
background, black hydraulic lines, appliance silhouettes and coloured Fühler dots.
They are independently drawn SVGs, not an export of Solvis artwork. No portal login,
cloud requests, third-party cards, backend changes or Home Assistant restart are
needed.

The installed dashboard is available as **Solvis** in the HA sidebar, starting at
[Heizung](http://homeassistant.local:8123/solvis-schema/heizung), with additional
[Warmwasser](http://homeassistant.local:8123/solvis-schema/warmwasser) and
[Wärmepumpe](http://homeassistant.local:8123/solvis-schema/waermepumpe) views.

The card reads existing entities from `hass.states`. Tapping a configured value or
pump opens Home Assistant's entity details/history; the card never calls a service
or changes a controller setting. Pump symbols rotate only when their binary sensor
is `on` and respect reduced-motion preferences. Small screens scroll the diagram
horizontally while keeping its labels readable.

## Installation

1. Copy `solvis-schema-card.js` to `/config/www/solvis-schema-card.js` on Home
   Assistant (create `www` if necessary).
2. Under **Settings → Dashboards → Resources**, add
   `/local/solvis-schema-card.js?v=1` as a **JavaScript module**. Enable advanced mode
   in your profile if Resources is hidden. Reload the browser after adding it.
3. Create a new dashboard and paste the contents of `solvis-dashboard.json` into
   its raw configuration editor. It contains three panel views with their own URLs.
   The entity IDs in the example were verified on this Anlage; adjust the mappings
   if entities have been renamed.

When the connected HA MCP server supports inline dashboard resources, the entire
JavaScript file can instead be registered as `resource_type: module` using its
`ha_config_set_dashboard_resource(content=...)` API. This is how the initial
`solvis-schema` dashboard was installed; it stores a self-contained data URL and
needs no file copy. Use the returned resource ID for subsequent updates instead of
creating duplicates. Inline and filesystem resources are alternatives: install one.

For a filesystem update, replace the file **and change the resource URL's version
query**, e.g. `?v=2`, to invalidate Home Assistant's long-lived frontend cache.
No resource is registered automatically by the Python integration or HACS.

## Card configuration

```yaml
type: custom:solvis-schema-card
view: heating
navigation: true
entities:
  s1: sensor.solvisleo_180_warmwasserpuffer_temperatur_s1
  s4: sensor.solvisleo_180_heizungspuffer_oben_temperatur_s4
  s9: sensor.solvisleo_180_heizungspuffer_unten_temperatur_s9
  s10: sensor.solvisleo_180_aussentemperatur_s10
  s12: sensor.solvisleo_180_hkr1_vorlauftemperatur_s12
  heating_pump: binary_sensor.solvisleo_180_hkr1_pumpe_a3
```

`view` is initially `heating` (default), `water` or `heatpump`. `navigation` defaults
to `true` and shows buttons for switching views. Set it to `false` for separate
Home Assistant views, as in the full example. `entities` explicitly maps diagram
roles to entity IDs; the card does not guess IDs from translated names. There is
no graphical configuration editor; use the card's YAML editor.

| Entity role | Meaning |
| --- | --- |
| `s1`, `s4`, `s9` | Speicher oben, Heizungspuffer oben/unten |
| `s2`, `s11`, `s15` | Warmwasser, Zirkulation, Kaltwasser |
| `s10`, `s12` | Außentemperatur, Vorlauf HKR1 |
| `heating_flow`, `heating_return` | Heizkreis WMZ temperatures |
| `heating_volume_flow`, `heating_power` | Heizkreis WMZ volume flow and thermal power |
| `heating_pump`, `mixer_open`, `mixer_close` | HKR1 binary sensors A3, A8, A9 |
| `water_pump_modulation`, `water_flow`, `water_power` | O5, S18, warm water thermal power |
| `circulation_pump` | Binary sensor A1 |
| `charging_pump`, `charging_modulation` | Wärmepumpe charging pump A2, O4 |
| `heatpump_power_thermal`, `heatpump_power_electric` | Wärmepumpe thermal output and electrical input |
| `heizstab_status` | Heizstab binary sensor A12; no stage inferred |
| `heatpump_flow_temp`, `heatpump_return_temp`, `heatpump_volume_flow` | Optional Wärmepumpe measurements; not interchangeable with Heizkreis WMZ |
| `pressure`, `smart_grid` | Optional Anlagendruck and human-readable Smart Grid state |

For `water_power`, the integration also provides **Warmwasser Leistung berechnet**
from S2, S15 and S18. After installing the updated integration, select its actual
entity ID in the card mapping. See [calculation and register 33549 findings](../docs/warm-water-power.md).

## Data availability and limits

Missing, `unknown`, `unavailable`, empty and non-finite numeric readings display as
`—`. Binary sensors other than `on`/`off` display **Nicht verfügbar**. A disconnected
HA frontend clears the displayed readings rather than retaining stale values.
Numeric zero remains a valid measurement. The card cannot detect incorrect but
available controller readings; inspect the entity's history if a value disagrees
with the portal.

Temperatures display in °C (converting °F); power in kW (converting W). The Heizung
summary converts the integration's l/min to l/h to match the portal. Volume flow
also supports m³/h; pressure supports bar, kPa and Pa. An unexpected unit is kept
with its value rather than silently relabelled. Numbers use HA's UI language.

The initial mapping deliberately leaves Wärmepumpe flow/return temperatures and
volume flow, Anlagendruck and Smart Grid unconfigured: this integration does not
currently provide independently verified entities for them. They remain visibly
unavailable. In particular, the Heizkreis WMZ readings are not reused as
Wärmepumpe readings, and a running charging pump does not prove the compressor is
running. The two available Wärmepumpe power entities currently report 0 kW even
when the portal shows output; this card displays the HA readings without replacing
them with portal values or calculations. Resolving that discrepancy requires a
separate register investigation.

These are simplified status schematics, not hydraulic installation drawings. The
Wärmepumpe view follows the portal's upright louvred housing, two horizontal
connections, Umschaltventil, charging pump and separate Smart Grid display. The
thermal output and electrical input are shown beside the housing rather than in
a duplicate summary row above the diagram. The
symbols inside the housing are static pictograms; only the charging pump's
animation indicates a measured run state. There is no guaranteed pixel-identical
copy of the portal and no imported Solvis logo or artwork.

To remove the installed dashboard, delete **Solvis** in dashboard settings, then
remove its `solvis-schema-card` resource. Existing dashboards and entities do not
depend on it.
