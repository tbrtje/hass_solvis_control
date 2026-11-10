# Warmwasser Leistung berechnet

Die Integration ergänzt die thermische Warmwasserleistung als eigenen Sensor
**Warmwasser Leistung berechnet** (`warm_water_power_calculated`, kW). Der bisherige
Sensor **Warmwasser Leistung** (`warm_water_power`, Register 33549) bleibt mit seiner
bisherigen Identität und dem unveränderten Registerwert zur Diagnose erhalten.

## Befund an dieser Anlage am 10. November 2026

In der Home-Assistant-Historie vom 9. November, 12:20 Uhr, bis zum 10. November,
12:20 Uhr (MEZ) hatte Register 33549 ausschließlich den numerischen Wert 0;
zusätzlich gab es Abschnitte mit `unavailable`. Auch während einer Zapfung am
10. November zwischen 07:05 und 07:20 Uhr blieb der Sensor durchgehend bei 0 kW,
obwohl S18 einen positiven Volumenstrom und S2/S15 eine deutliche
Temperaturdifferenz meldeten.

Ein Beispiel aus dieser Zapfung, anhand der zuletzt aufgezeichneten Zustände um
07:16:13 Uhr MEZ:

| Quelle | Register | Wert | Letzte aufgezeichnete Zustandsänderung (MEZ) |
| --- | ---: | ---: | --- |
| Warmwassertemperatur S2 | 33025 | 49,7 °C | 07:16:13 |
| Kaltwassertemperatur S15 | 33038 | 13,5 °C | 07:15:52 |
| Warmwasser-Volumenstrom S18 | 33041 | 6,6 l/min | 07:15:32 |
| Warmwasser Leistung | 33549 | 0 kW | Während der gesamten Zapfung unverändert |

Daraus ergibt sich eine geschätzte thermische Leistung von **16,67 kW**. Die
Historie enthält Zustandsänderungen; diese Zeitstempel belegen nicht den Zeitpunkt
der letzten Abfrage eines unveränderten Wertes. Das Beispiel kombiniert zuletzt
bekannte, zeitversetzte Werte und ist keine synchrone Referenzmessung.

Auch das Attribut `unprocessed_value` des ursprünglichen Leistungssensors war 0.
Die Integration liest 33549 als Input-Register (FC04), ohne Byte-Swap und mit
Multiplikator 1. Es handelt sich damit nicht bloß um eine auf 0 gerundete Anzeige.
Die vorhandene [Register-Inventur](../inventory/solvisleo_180_sc3.json) enthält
ebenfalls 0 für FC03 und FC04 an Adresse 33549; sie wurde jedoch nicht während der
oben untersuchten Zapfung aufgenommen.

Die Ursache bleibt offen: Ob der SC3 dieses Register bei dieser SolvisLeo 180
nicht befüllt oder die Zuordnung abweicht, ist damit nicht nachgewiesen. Der Befund
belegt weder einen allgemeinen Firmwarefehler noch ein grundsätzlich fehlendes
Register.

## Berechnung

```text
ΔT = max(S2 − S15, 0)                         [K]
P  = S18 × 1,0 × 4,186 × ΔT / 60             [kW]
```

S18 wird in l/min eingelesen, S2 und S15 in °C. Die Näherung setzt für Wasser eine
Dichte von 1 kg/l und eine spezifische Wärmekapazität von 4,186 kJ/(kg·K) an.
Die Idee entspricht [Upstream-PR #390](https://github.com/LarsK1/hass_solvis_control/pull/390);
hier wird dafür eine zusätzliche Entität angelegt.

Der Sensor beschreibt die geschätzte **thermische Leistung der Warmwasserentnahme**.
Er misst weder die elektrische Leistungsaufnahme noch die thermische Erzeugung
der Wärmepumpe und ist kein kumulierter Energiezähler.

## Abfrage und Verfügbarkeit

- Alle drei Quellen werden in der konfigurierten schnellen Abfragegruppe (`high`)
  gelesen, standardmäßig alle 10 Sekunden. Die Abfragen erfolgen nacheinander;
  ein neuer Berechnungswert wird aus dem abgeschlossenen Coordinator-Datenstand
  veröffentlicht.
- Fehlende, nicht numerische oder nicht endliche Werte führen zu `unavailable`.
  Für S2/S15 gilt der Plausibilitätsbereich 0 bis 100 °C, für S18 ein
  nicht negativer Volumenstrom. Damit werden auch Werte wie −300 oder 250 °C
  ausgeschlossen. Ungültige Eingänge werden nicht als 0 kW ausgegeben.
- Ein gültiger Volumenstrom von 0 ergibt 0 kW. Eine negative Temperaturdifferenz,
  etwa bei Stillstand oder einem Übergang, wird auf 0 K begrenzt.
- Bei Lesefehlern gelten die bestehenden Regeln: Zwei aufeinanderfolgende Fehler
  behalten den letzten Quellenwert bei; ab dem dritten Fehler einer Quelle wird
  der berechnete Sensor nicht verfügbar. Ein erfolgreicher Lesezugriff hebt den
  Fehlerzustand auf. Ein Verbindungsausfall macht den Sensor sofort nicht verfügbar.
- Ein Ausfall von Register 33549 beeinflusst die Berechnung nicht.
- Das Attribut `raw_values` enthält die verwendeten Quellenwerte bereits in °C
  und l/min, keine unskalierten Modbus-Wörter. Die Anzeige nutzt zwei Nachkommastellen;
  daraus folgt keine entsprechende Messgenauigkeit.

Kurze Zapfungen können zwischen zwei Abfragen liegen. Anlauf, Fühlerträgheit und
zeitversetzte Quellenwerte können vorübergehende Spitzen oder Abweichungen erzeugen.
Die Berechnung ersetzt keinen geeichten Wärmemengenzähler.

## Verwendung in Home Assistant

Nach Installation der aktualisierten Integration und einem Neustart von Home
Assistant erscheint die zusätzliche Entität am bestehenden Gerät. Ihre Unique-ID
ist `33025_warm_water_power_calculated`; die Entity-ID hängt von Sprache und
eventuellen Umbenennungen ab.

Im [Anlagenschema](../frontend/README.md) kann `entities.water_power` auf diese neue
Entität gesetzt werden. Die Zuordnung erfolgt ausdrücklich in der Karte; die
bestehende Dashboard-Konfiguration wird durch die Integration nicht geändert.
