# Modbus-Abfragen und deaktivierte Entitäten

Die Integration liest ein Register regelmäßig, solange mindestens eine aktivierte
Entität seinen Wert benötigt. Die Zuordnung verwendet Entitätsdomäne, Integration
und Unique-ID in der Home-Assistant-Registry. Übersetzte Namen und selbst gewählte
Entity-IDs beeinflussen sie nicht.

## Deaktivieren und Wiederaktivieren

- Eine deaktivierte Entität löst keine eigenen regelmäßigen Registerabfragen aus.
  Das gilt sowohl für standardmäßig deaktivierte Entitäten als auch für später
  vom Benutzer deaktivierte Sensoren, Binärsensoren, Zahlen, Auswahllisten,
  Schalter und Firmware-Entitäten.
- **Ausblenden** ist etwas anderes: Eine ausgeblendete, weiterhin aktivierte
  Entität wird weiterhin versorgt.
- Der Coordinator prüft den Bedarf zu Beginn jedes Pollzyklus. Änderungen gelten
  ab dem nächsten Zyklus; eine bereits laufende Abfrage kann noch abgeschlossen
  werden. Die tatsächlichen Leseintervalle bleiben die konfigurierten Gruppen
  `high`, `default` und `slow`.
- Sobald ein Register keinen aktiven Nutzer mehr hat, werden sein zwischengespeicherter
  Wert und seine Abfragefrist verworfen. Ein Lesefehler-Zähler bleibt nur erhalten,
  solange die Registeradresse noch benötigt wird. Nach einer solchen Pause wird
  beim Wiederaktivieren im nächsten Zyklus frisch gelesen, auch bei `slow`.
- Sind sämtliche Entitäten deaktiviert und gibt es keine benötigten Quellen mehr,
  führt der regelmäßige Coordinator keine Modbus-Lesezugriffe aus.

Beim ersten Start findet die erste Abfrage vor dem Anlegen der Entitäten statt.
Solange noch kein Registry-Eintrag vorhanden ist, gelten die jeweiligen
Aktivierungs-Vorgaben der Integration. Bereits gespeicherte Deaktivierungen werden
auch bei dieser ersten Abfrage und nach einem Neustart berücksichtigt.

## Gemeinsam benötigte Werte

Eine deaktivierte Quellen-Entität kann weiterhin Modbus-Abfragen benötigen, wenn
ihr Wert von einer anderen aktivierten Entität verwendet wird:

| Aktive Entität | Benötigte Quellen |
| --- | --- |
| Warmwasser Leistung berechnet | S2 (33025), S15 (33038), S18 (33041) |
| Speicherenergie mit Referenz 12 °C | S1 (33024), S4 (33027), S9 (33032) |
| Wochenplan: nächster Schaltzeitpunkt | Zugehöriger Wochenplan-Block |
| Wochenplan: aktuell aktiv | Derselbe Wochenplan-Block |

Bei einem Wochenplan reicht eine der beiden aktivierten Entitäten, um den Block
weiter zu lesen. Sind beide deaktiviert, entfällt die Abfrage. Die beiden
Entitäten teilen sich einen Block-Lesezugriff pro fälligem Intervall.

Das Deaktivieren einer berechneten Entität stoppt umgekehrt keine Abfrage einer
weiterhin aktivierten Quellen-Entität. Die regelmäßigen Zugriffe entfallen erst,
wenn kein aktiver Nutzer des Wertes mehr vorhanden ist.

## Lesefehler und ausdrückliche Scans

Bei benötigten Registern bleiben die [Regeln für Lesefehler](adr/0002-runtime-fault-tolerance-instead-of-register-gating.md)
erhalten: Ab drei aufeinanderfolgenden Lesefehlern wird die betroffene Entität nicht
verfügbar; ein erfolgreicher Zugriff hebt den Fehlerzustand auf. Auch ein derzeit
nicht lesbares Register wird zu seinem nächsten fälligen Termin erneut versucht.

Ein ausdrücklich gestarteter [Modbus-Scan](modbus-scan.md) oder das
[Inventurwerkzeug](../tools/README.md) liest die angeforderten Register unabhängig
vom Aktivierungszustand der Entitäten. Diese Werkzeuge dienen gerade dazu, Werte
außerhalb der regelmäßigen Abfragen zu untersuchen.
