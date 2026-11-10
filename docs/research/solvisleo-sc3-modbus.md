# SolvisLeo 180 und SC3: öffentliche Modbus-Dokumentation

Recherche und Abruf: **05.11.2026**, Europe/Berlin. Datum anhand der Laufzeitumgebung geprüft (17:57 UTC = 18:57 MEZ bei Beginn). Ausschließlich öffentliche Webquellen und lokale Dateien gelesen; keine Anlage kontaktiert. Vor Repositoryerkundung wurden `CONTEXT.md` und ADR 0001/0002 gelesen. Keine weiteren Agenten eingesetzt.

## Ergebnis und Beweisgrenzen

**Eine eigenständige öffentliche SolvisLeo-GLT-Registerliste wurde in der beschriebenen Suche nicht gefunden.** Der aktuelle Modbus-Download der [SC3-Produktseite](https://www.solvis.de/solviscontrol/) führt weiterhin zu [TNF-SC-3, 31399-2a](https://solvis-files.s3.eu-central-1.amazonaws.com/downloads-fk/regelung/sc-3/SC-3_ModBus_Schnittstellenbeschreibung.pdf). Neuere Leo-Unterlagen belegen andere Hardwareanbindungen und zusätzliche Bedienanzeigen, aber keine entsprechende vollständige TCP-Registerzuordnung. Das ist ein begrenztes Rechercheergebnis, kein Beweis, dass Solvis intern oder über Fachpartner keine neuere Liste besitzt.

Die entscheidende Trennung lautet: **offizielle SC3-Registeradresse**, **offizielle Leo-Komponentenfunktion** und **im Code angenommene Zuordnung** sind unterschiedliche Belege. Aus einem Menüwert oder einer internen Modbus-Verbindung folgt keine öffentliche GLT-Adresse. „Standard SC3“ bezeichnet hier die generische veröffentlichte Schnittstellenbeschreibung, keine nachgewiesene einheitliche Firmware aller Anlagen.

## Quellen und Versionsstände

Alle nachstehenden URLs wurden am **05.11.2026** geprüft. Seitenangaben sind die gedruckten PDF-Seiten; bei diesen Dokumenten stimmen sie mit der PDF-Zählung ab 1 überein. Die S3-Dateien gelten als Herstellerquellen, weil die offiziellen Solvis-Seiten direkt auf sie verlinken.

| Kürzel / Hersteller-PDF | Dokumentstand im PDF | Umfang / Fundstelle | HTTP Last-Modified (UTC), separat vom Dokumentdatum |
| --- | --- | --- | --- |
| [SC3: Modbus Spezifikationen](https://solvis-files.s3.eu-central-1.amazonaws.com/downloads-fk/regelung/sc-3/SC-3_ModBus_Schnittstellenbeschreibung.pdf) | Version 1.0, Deckblatt September 2021; 31399-2a, redaktionell 11.21, technisch 09.21 | 20 S.; Stand auf S. 20 | 20.04.2022 13:06:02 |
| [LEO-I: Bedienung für Installateure](https://solvis-files.s3.eu-central-1.amazonaws.com/downloads-fk/solvisleo/36005_BAL-LEO-I.pdf) | 36005-2, redaktionell und technisch 05.26 | 56 S.; Stand auf S. 56 | 20.05.2026 06:36:06 |
| [LEO-MAL: Montage SolvisLeo 180](https://solvis-files.s3.eu-central-1.amazonaws.com/downloads-fk/solvisleo/35976_MAL-LEO.pdf) | 35976-2a, redaktionell 07.26, technisch 05.26 | 44 S.; Stand auf S. 44 | 29.07.2026 04:59:52 |
| [LEO-ALS: Anschlusspläne und Anlagenschemata](https://solvis-files.s3.eu-central-1.amazonaws.com/downloads-fk/solvisleo/35928_ALS-LEO.pdf) | 35928-2b, redaktionell 07.26, technisch 05.26 | 20 S.; Stand auf S. 20 | 29.07.2026 04:59:53 |
| [RGV: Regelungsversionen SC3](https://solvis-files.s3.eu-central-1.amazonaws.com/downloads-fk/regelung/sc-3/35560_TNF-RGV-SC-3-M.pdf) | 35560-2, redaktionell 10.25, technisch 09.25 | 40 S.; deutscher Teil S. 2–7, Stand S. 40 | 09.10.2025 10:04:58 |
| [Remote: ältere SC2-Modbus-Spezifikation](https://solvis-files.s3.eu-central-1.amazonaws.com/seiten/produkte/solvisremote/Download/SolvisRemote+Modbus+Spezifikationen+201906.pdf) | Version 1.0, Deckblatt Januar 2019; 31054-3, Stand 06.19 | 20 S.; Stand S. 20 | Nicht protokolliert |

**„Aktuell verlinkt“ ist keine Zusicherung „neuester existierender Herstellerstand“.** Die [Leo-Downloadseite](https://www.solvis.de/downloads-fachkunden/solvisleo/) zeigt „Updated on 9. Juni 2026“, obwohl die direkt heruntergeladenen Montage-/Schema-Dateien redaktionell Juli 2026 tragen. Die [Regelungs-Downloadseite](https://www.solvis.de/downloads-fachkunden/regelung/) zeigt 16. Juli 2026 und einen Download MA3-23-09; das verlinkte RGV-PDF endet dagegen bei MA3.22.03, 08/2025 (S. 7). Seitenänderungsdatum, PDF-Stand, HTTP-Datum und Firmwareversion dürfen deshalb nicht gleichgesetzt werden. Eine derzeit neueste Leo-Firmware ist dadurch nicht bestimmt.

## Gesicherter offizieller Registerkern

Die folgenden Angaben stammen aus [SC3, S. 5–7](https://solvis-files.s3.eu-central-1.amazonaws.com/downloads-fk/regelung/sc-3/SC-3_ModBus_Schnittstellenbeschreibung.pdf#page=5), lesend FC04; Adressen werden unverändert aus der Dezimal-/Hex-Tabelle übernommen, ohne zusätzlichen 30001-/40001-Offset.

| Adresse dezimal / hex | Dokumentierte Bedeutung |
| --- | --- |
| 32770 / 0x8002; 32771 / 0x8003 | Version SC3; Version NBG |
| 33024–33039 / 0x8100–0x810F | S1–S16, 0,1 °C |
| 33291 / 0x820B; 33292 / 0x820C | A12; A13, jeweils generisch |
| 33293 / 0x820D; 33294 / 0x820E | A14; O1 (PWM-Prozent bzw. 0,1 V) |
| 33536 / 0x8300 | Brennerstufe-1-Laufzeit |
| 33537 / 0x8301 | Brennerstarts Stufe 1 |
| 33538 / 0x8302 | Brennerstufe-2-Laufzeit |
| 33539 / 0x8303 | aktuelle SX-Leistung, W |
| 33540 / 0x8304 | Ionisationsstrom, mA |

Diese Liste enthält keine Zuordnung von 33544/33545 zu Wärmepumpen-Pth/Pel und keine moderne Energiezählertabelle. Die abweichende Repositorybelegung unten lässt sich daraus nicht offiziell bestätigen. Eine Verfügbarkeit dieser Adressen auf jeder Leo-Firmware ist damit ebenfalls nicht zugesichert.

## Offiziell belegte Leo-Besonderheiten

### Hardwarefunktion gegenüber generischer Registerbenennung

[LEO-ALS, S. 8–11](https://solvis-files.s3.eu-central-1.amazonaws.com/downloads-fk/solvisleo/35928_ALS-LEO.pdf#page=8) ordnet Leo-spezifisch zu:

- A12/A13: keine Funktion in der Belegungstabelle; O1: unbenutzt.
- A14: 3-Wege-Umschaltventil; A2/LP: Ladepumpe PLAS WP.
- S3: Speicherreferenz; S6 und S14: unbenutzt; S9: Heizungspuffer unten.
- Erweiterungsplatine DC1: Versorgung der Modbus-Alsonic-Sensoren; eigene Modbus-Unterverteilung auf S. 11.

Die Verknüpfung dieser Anschlussnamen mit generischen SC3-Adressen ist nur eine **Ableitung aus zwei Dokumenten**, keine Leo-Registerfreigabe. Insbesondere belegen 33291/33292/33294 allein keinen Leo-Heizstabstatus bzw. keine Heizstabmodulation. „Keine Funktion“ in der Anschlusstabelle beweist auch nicht, dass ein Register keine Antwort liefert.

[LEO-MAL, S. 36](https://solvis-files.s3.eu-central-1.amazonaws.com/downloads-fk/solvisleo/35976_MAL-LEO.pdf#page=36) beschreibt die Heizpatrone mit 9 kW Maximum und 0,15–9 kW Modulationsbereich. SC3 steuert sie über Modbus und Anschlussbox; L1 wird moduliert, die anderen Phasen zugeschaltet. [S. 21](https://solvis-files.s3.eu-central-1.amazonaws.com/downloads-fk/solvisleo/35976_MAL-LEO.pdf#page=21) beschreibt die separate geschirmte A/B/GND-Verbindung zur Wärmepumpe. Diese internen Busanbindungen sind keine TCP-Registerliste.

**Herstellerwiderspruch:** LEO-MAL S. 37 nennt den Speicherreferenzsensor S6; LEO-ALS S. 8 und der Kabelbaum auf S. 9 nennen S3. Das bleibt ungeklärt und ist kein belastbarer Nachweis einer Leo-Registerverschiebung.

**Bezeichnung in der Integration, korrigiert am 10.11.2026:** Register 33029 wird
neutral als „Temperatursensor S6“ mit Thermometer-Symbol angezeigt. Die aus der
generischen Integration übernommene Bezeichnung „Solarrücklauf“ ist für diese
SolvisLeo 180 nicht belegt. Wegen des Herstellerwiderspruchs wird auch keine
Speicherreferenzfunktion für dieses Register angenommen. Der historische interne
Schlüssel `solar_return_secondary_temp_s6` bleibt erhalten, damit Unique-ID,
bestehende Entity-ID und Historie stabil bleiben. Neu angelegte Entitäten erhalten
ihre Entity-ID aus dem korrigierten Anzeigenamen; benutzerdefinierte Namen bleiben
in Home Assistant vorrangig.

### Pth/Pel, Heizpatrone und Energieanzeige

[LEO-I, S. 37–38](https://solvis-files.s3.eu-central-1.amazonaws.com/downloads-fk/solvisleo/36005_BAL-LEO-I.pdf#page=37) beschreibt thermische WP-Abgabe und elektrische Aufnahme in kW sowie Heizpatronen-Soll-/Istleistung. S. 37 enthält daneben einen offensichtlichen Einheitenwiderspruch („°C“ bei elektrischer Aufnahmeleistung); daraus darf keine Registerskalierung abgeleitet werden.

[LEO-I, S. 30](https://solvis-files.s3.eu-central-1.amazonaws.com/downloads-fk/solvisleo/36005_BAL-LEO-I.pdf#page=30) beschreibt thermische Tages-/Vortages-/Gesamtwerte in kWh und elektrische Energie/Jahresarbeitszahl; die Energiemengen sind nicht abrechnungsgeeignet. **Registeradressen, Wortbreiten und Überlaufverhalten fehlen dort.** S. 33 beschreibt Alsonic-HK-Wärmemessung als Modbus-Erweiterung.

[LEO-I, S. 27–28](https://solvis-files.s3.eu-central-1.amazonaws.com/downloads-fk/solvisleo/36005_BAL-LEO-I.pdf#page=27) beschreibt SmartEnergy/SunSpec und einen Servermodus mit Anzeige eines SC3-Überschussleistungsregisters; eine feste Adresse wird im Text nicht genannt. Die PV-Überschussverwertung wird für Leo in diesem Dokumentstand erst mit künftigem Update angekündigt. Daraus folgt keine Aussage über ihren tatsächlichen Freigabestand im November 2026.

## Implementierungsbelege, ausdrücklich keine Herstellerregisterliste

Originalquelle: [LarsK1/hass_solvis_control, const.py, Commit 54cf396cbe2d85123d98a3a07ff72c5d451729de](https://github.com/LarsK1/hass_solvis_control/blob/54cf396cbe2d85123d98a3a07ff72c5d451729de/custom_components/solvis_control/const.py). Die WP-Leistungen stehen dort [ab Zeile 1339](https://github.com/LarsK1/hass_solvis_control/blob/54cf396cbe2d85123d98a3a07ff72c5d451729de/custom_components/solvis_control/const.py#L1339), Zähler/WE2 [ab Zeile 695](https://github.com/LarsK1/hass_solvis_control/blob/54cf396cbe2d85123d98a3a07ff72c5d451729de/custom_components/solvis_control/const.py#L695). Code belegt ausschließlich die implementierte Interpretation:

| Adresse | Interpretation im Originalcode | Zugriff / Skalierung im Code |
| --- | --- | --- |
| 33537 / 0x8301 | WP thermische Energie | Input, Rohwert × 10 kWh |
| 33538 / 0x8302 | Wärmeerzeuger 2 / Brenner, thermische Energie | Input, × 10 kWh |
| 33544 / 0x8308 | WP Pth | Holding, × 0,1 kW |
| 33545 / 0x8309 | WP Pel | Holding, × 0,1 kW |
| 33546 / 0x830A | Wärmeerzeuger 2 Pth | Input, × 0,1 kW |
| 33547 / 0x830B | Wärmeerzeuger 2 Pel | Input, × 0,1 kW |

Diese Adressen sind bereits im generischen Originalprojekt vorhanden: Ihr Vorkommen im Leo-Fork beweist keine Leo-Exklusivität. Ein elektrischer WP-Gesamtenergiezähler ist aus dieser Auswahl nicht belegt. Pel ist Momentanleistung, kein kWh-Zähler.

Lokaler Vergleich, nur Bestandsaufnahme: `custom_components/solvis_leo/const.py`, Basis-HEAD `2a4057b02ca562f99c10c7e6188370cbe4317be9`, verwendet dieselben vier Leistungsadressen und nennt WE2 nun Heizstab. Lokal liegen außerdem 33536–33542 als Solar-/WP-/Heizstab-/PV2Heat-/Warmwasser-/Heizkreis-/Kühlenergie mit Faktor 10 vor. Das ist **lokale Implementierung**, insbesondere `eheiz` aus dem Domänenkontext konnte in den geprüften Hersteller-PDFs nicht als offizieller Registername bestätigt werden.

Die alten Herstellerbedeutungen für 33536–33540 widersprechen diesen neueren Codebedeutungen. Gesichert ist der **Dokument-/Codekonflikt**, nicht dessen Ursache oder der Firmwarestand einer Umbelegung. Ebenso ist die lokale Umbenennung von A12/A13/O1 zum Heizstab durch den aktuellen Leo-Anschlussplan nicht gedeckt. Aus dieser Recherche wurden keine Codeänderungen abgeleitet.

## Offene Fragen und benötigte Herstellerbestätigung

1. Welche Leo-Firmware stellt welche GLT-Adressen tatsächlich bereit? Benötigt wird eine versionierte Zuordnung einschließlich FC03/FC04, Wortzahl, Vorzeichen, Wortreihenfolge, Einheit, Skalierung und Fehlerwerten.
2. Gelten 33544/33545 sowie 33546/33547 auf Leo für die im Code angenommenen Größen? Umfasst WP-Pel nur Verdichter oder auch Lüfter/Ladepumpe/weitere Verbraucher? Ist Heizpatronenleistung gemessen oder berechnet?
3. Gibt es getrennte elektrische kWh-Zähler für WP und Heizpatrone? Welche Zähler sind rücksetzbar, wann laufen sie über, und welche Systemgrenzen gelten? Die Menübeschreibung ersetzt diese Definitionen nicht.
4. Gibt es Leo-spezifische Register für Heizpatronenstatus, Ventilstellung, Alsonic-Werte oder Durchfluss/Druck? Interner Modbus und GLT müssen ausdrücklich auseinandergehalten werden.
5. Ab welcher Firmware gelten die jüngeren Energiebelegungen statt der Brennerangaben in 31399-2a? Welche Register sind modell-/initialisierungsabhängig? Keine pauschale Übernahme der alten Liste oder des Codes ist öffentlich abgesichert.
6. Ist für die Speicherreferenz S3 oder S6 maßgeblich? Die beiden aktuellen Leo-Herstellerdokumente widersprechen einander.

## Suchumfang und Reproduzierbarkeit

Geprüft wurden die öffentlichen Produkt-/Downloadbereiche [SC3](https://www.solvis.de/solviscontrol/), [Fachpartner](https://www.solvis.de/downloads-fachkunden/), [Leo](https://www.solvis.de/downloads-fachkunden/solvisleo/), [Regelung](https://www.solvis.de/downloads-fachkunden/regelung/), [Leo-Produktseite](https://solvisleo.solvis.de/) und deren relevante PDF-Verweise. Öffentliche Websuche unter anderem nach `site:solvis.de SolvisLeo Modbus Register PDF`, `SolvisLeo Modbus`, `site:solvis.de Modbus 33545`, `site:solvis.de Leo Registerliste`, `SC-3 Modbus 2025 pdf`, `SolvisControl Modbus 2026 pdf`, `site:solvis.de Modbus eheiz Pth`, `site:solvis.de modbus filetype:xlsx` und `site:solvis.de modbus Spezifikation 31399`. Die Suche ergab keine weitere belastbare offizielle Leo-Adressliste; Suchmaschinenabdeckung und unindexierte/zugangsbeschränkte Dokumente bleiben Grenzen.

PDFs wurden direkt per HTTPS heruntergeladen, mit Poppler `pdftotext -layout` seitenweise geprüft; die entscheidende LEO-ALS-Belegung S. 8 zusätzlich gerendert und visuell kontrolliert. Suchtreffer auf Foren oder Issues wurden nicht als Herstellerbelege verwendet. Der Webparser scheiterte am großen Montage-PDF; der direkte Download gelang. Beim älteren Remote-PDF scheiterte der Webparser an der Pluszeichen-URL, der direkte Download derselben URL gelang. Temporäre Prüfdateien liegen außerhalb des Repositories.

SHA-256 der abgerufenen Dateien, um spätere Ersetzungen unter denselben URLs zu erkennen:

```text
SC3       d96afe30c2928a20630815d0b88c64013fd9d1f4b301a81c90d0f2b3652dbb18
LEO-I     d9af18f31fcf2660c6ab4da15c1e2909f485180b72ac4536102d08fc2f26edd4
LEO-MAL   fb6100919491d5eda600941b1cee297589cdf1eee3862a6f7b1dd181a51e6e1d
LEO-ALS   ee9a9483277fe83e746b7b6c11ebcec4cf7bb63cf0766cf268923e596e828f3e
RGV       36b85fb092b0583868843fc0458062620fd63745337392b0d597485c46096a68
```
