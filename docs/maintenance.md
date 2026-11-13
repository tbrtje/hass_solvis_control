# Wartung, Diagnose und Schreibbestätigung

## Laufzeit und Abhängigkeiten

Integration und Testumgebung verwenden fest **PyModbus 3.15.0**. Der verwendete
Parameter für die Modbus-Geräteadresse ist einheitlich `device_id`; zusätzliche
Kompatibilitätspfade für PyModbus 3.8/3.9 entfallen. Die Python-Version wird durch
Home Assistant vorgegeben. Die lokale Prüfung dieser Änderungen erfolgte mit
Python 3.14.3.

Die frühere ARP-/MAC-Suche und die separate Hilfsfunktion zum Lesen einzelner
Register hatten keine produktiven Aufrufer mehr. Sie sind mitsamt der nur dafür
benötigten Scapy-Abhängigkeit entfernt.

## Lebenszyklus der Verbindung

Ein angelegter Modbus-Client wird geschlossen, wenn Verbindungsaufbau, erste
Datenabfrage oder anschließendes Plattform-Setup fehlschlagen. Das gilt auch für
einen abgebrochenen Start. Unvollständige Laufzeitdaten werden dabei entfernt.

Beim Entladen werden zuerst die HA-Plattformen entladen. Schlägt das fehl, bleiben
Verbindung und Laufzeitdaten für die weiterhin geladenen Entitäten erhalten. Nach
erfolgreichem Entladen werden Client und Daten bereinigt; ein Fehler beim Schließen
wird protokolliert und verhindert die übrige Bereinigung nicht.

## Diagnose ohne zusätzliche Registerabfragen

Der Diagnose-Download verwendet ausschließlich den vorhandenen Coordinator-Datenstand.
Er öffnet keine Verbindung und liest keine Register erneut. Er enthält:

- Verbindungszustand und Ergebnis der letzten Coordinator-Aktualisierung,
- den letzten Coordinator-Fehler, falls vorhanden,
- Registeradresse, Registertyp, Wortanzahl, Einheit, Skalierung und Abfragegruppe,
- die zuletzt vorhandenen dekodierten Werte und Fehlerzähler je Register,
- die Information, ob ein Register derzeit von aktiven Entitäten benötigt wird.

Mehrwort-Werte bleiben vollständig erhalten: die Controllerzeit als dekodierter
32-Bit-Wert, Wochenplan-Blöcke als Liste aller Wörter. Host und Anlagenname aus den
Konfigurationsdaten werden im Export geschwärzt. Ohne geladenen Coordinator meldet
der Export `loaded: false`.

Die Werte sind ein **zwischengespeicherter Datenstand**, keine neue Messung beim
Download. Für gezielte frische Rohdaten gibt es weiterhin die ausdrückliche
[Modbus-Scan-Aktion](modbus-scan.md).

## Bestätigung von Schreibzugriffen

Zahlen, Auswahllisten und Schalter nutzen denselben Schreibpfad:

1. Den skalierten Wert als ein Registerwort an den SC3 senden.
2. Eine fehlende oder ablehnende Antwort als Fehler an Home Assistant weitergeben.
3. Nach erfolgreicher Antwort ausschließlich das betroffene Register zurücklesen.
4. Den tatsächlich gelesenen Wert an alle aktiven Entitäten veröffentlichen, die
   dieselbe Registeradresse und denselben Registertyp verwenden.

Die Anzeige wartet damit nicht bis zur nächsten regulären Abfrage einer langsamen
Gruppe. Ein Wert wird nicht allein aufgrund des gesendeten Befehls als übernommen
angezeigt. Wenn der SC3 einen anderen Wert zurückliefert, erscheint dieser Wert.

Scheitert die Bestätigung nach erfolgreichem Senden, erhält Home Assistant einen
entsprechenden Fehler. Der Schreibbefehl wird nicht durch die Integration erneut
gesendet. Die nächste reguläre Abfrage versucht das Rücklesen dieses Registers
erneut, ohne auf das langsame Intervall zu warten. Fehlerzählung und Verfügbarkeit
folgen weiter den [bestehenden Regeln](polling.md).

Ein gemeinsamer Zugriffsschutz hält einen regulären Pollzyklus und die Sequenz aus
Schreiben und Rücklesen auseinander. Dadurch kann ein älterer Poll-Datenstand die
gerade bestätigte Änderung nicht überschreiben. Eine einzelne Bestätigung setzt
auch keinen noch bestehenden Coordinator-Fehler für die gesamte Anlage zurück.

## Gemeinsame Registerdefinitionen

`registers.py` definiert unveränderliche `ModbusFieldConfig`-Datensätze sowie
`EntityType`, `RegisterType`, `PollingGroup` und `DataType`. Registerkatalog,
Entitätserstellung, Coordinator und Dokumentationsgenerator verwenden diese Typen.
Die Entitätserstellung hängt nicht mehr vom Klassennamen als Text ab.

Der Katalog bleibt in `const.py`. Namen, Adressen, Skalierungen und vorhandene
Unique-IDs bleiben erhalten; das gilt auch für historische interne Namen wie S6.
Unbenutzte Entitätsparameter für eine zweite Datenverarbeitung oder eigene
Abfragesteuerung sind entfernt. Beides gehört zum Coordinator.
