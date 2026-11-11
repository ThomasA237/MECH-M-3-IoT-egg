# HTTP-API-Tests – Raspberry Pi Pico W

Dieser Ordner enthält unsere automatisierten Tests für die HTTP-Schnittstelle des Raspberry Pi Pico W mit DHT11-Sensor (Gruppe 6). Wir prüfen damit die grundlegenden API-Funktionen, die Verarbeitung fehlerhafter Anfragen und die Übereinstimmung mit der vorgegebenen [OpenAPI-Spezifikation](../docs/iot-specs/openapi.yaml) (Version 1.2.0 laut Aufgabenstellung).

## Testverfahren

Wir nutzen zwei Testverfahren, die sich ergänzen:

| Datei / Werkzeug | Zweck |
| --- | --- |
| `smoke_api.py` | Gezielte Funktionstests für HTTP-Endpunkte, JSON-Antworten, Statuscodes, Eingabevalidierung und Konfigurationsänderungen (nur Python-Standardbibliothek). |
| **Schemathesis** | Tests auf Basis der `openapi.yaml` mit den Phasen `examples` und `coverage`; optional `fuzzing`. |
| `run_api_tests.ps1` | Startet die Tests nacheinander und stellt anschließend das ursprüngliche Messintervall wieder her. |

Mit dem OpenAPI-basierten Testverfahren streben wir für **Termin 2 die Teststufe „sehr gut“** an.

## Voraussetzungen und Installation

- Der Pico W läuft mit unserer Firmware und ist über WLAN erreichbar.
- Der Laptop kann den Pico W über **HTTP (Port 80)** erreichen.
- Auf dem Laptop sind **Python 3.12**, **PDM** und **Windows PowerShell** verfügbar.
- Schemathesis ist in der `pyproject.toml` im Repository-Hauptverzeichnis als optionale Test-Abhängigkeit eingetragen:

```toml
[project.optional-dependencies]
test = ["schemathesis>=4,<5"]
```

Falls PDM noch nicht installiert ist, kann es mit `python -m pip install pdm` installiert werden. Anschließend im **Repository-Hauptverzeichnis**:

```powershell
pdm install -G test
```

Die Abhängigkeiten werden auf dem Laptop installiert, **nicht auf dem Pico W**. `smoke_api.py` selbst benötigt keine zusätzlichen Pakete.

## Tests ausführen

Alle Befehle werden im **Repository-Hauptverzeichnis** ausgeführt. Die IP-Adresse `172.20.10.2` ist ein Beispiel; die tatsächliche Adresse steht in der seriellen Konsole des Pico W.

**Vollständiger Testlauf (Smoke-Tests, Schemathesis Examples und Coverage):**

```powershell
pdm run powershell -ExecutionPolicy Bypass -File .\tests\run_api_tests.ps1 -PicoIP 172.20.10.2
```

**Kurzer Testlauf ohne Coverage:**

```powershell
pdm run powershell -ExecutionPolicy Bypass -File .\tests\run_api_tests.ps1 -PicoIP 172.20.10.2 -SkipCoverage
```

**Zusätzlich mit Fuzzing:**

```powershell
pdm run powershell -ExecutionPolicy Bypass -File .\tests\run_api_tests.ps1 -PicoIP 172.20.10.2 -IncludeFuzzing
```

**Nur die Python-Smoke-Tests:**

```powershell
python tests/smoke_api.py --url http://172.20.10.2
```

## Abgedeckte Testfälle

| Bereich | Geprüftes Verhalten |
| --- | --- |
| `GET /` | HTTP 200 und nichtleere Textantwort |
| `GET /config` | HTTP 200, JSON, `device_id` und gültiges Messintervall |
| `GET /status` | HTTP 200, JSON und erwartete Statusfelder mit passenden Datentypen |
| `POST /config` | Gültige Intervalle werden übernommen und anschließend mit `GET /config` bestätigt |
| HTTP-Fehler | Unbekannte Pfade → 404, nicht erlaubte Methoden → 405, ungültige Anfragen → 400 |
| Eingabevalidierung | Fehlende oder unbekannte Felder, falsche Datentypen und Intervalle unter 2 Sekunden |
| Robustheit | Der Server ist nach fehlerhaften Anfragen weiterhin erreichbar |
| OpenAPI | Beispiele und weitere generierte Testfälle werden mit Schemathesis geprüft |

Bei JSON-Antworten kontrollieren die Smoke-Tests auch den `Content-Type`. Bei `405 Method Not Allowed` wird der `Allow`-Header geprüft.

## Änderungen am Messintervall

Die Tests verwenden `POST /config` und ändern das Messintervall damit vorübergehend. Das PowerShell-Skript liest den ursprünglichen Wert **vor dem gesamten Testlauf** aus und versucht, ihn auch nach einem fehlgeschlagenen Test wiederherzustellen.

Falls der Pico W dabei nicht erreichbar ist, wird ein Fehler angezeigt. Das aktuelle Intervall lässt sich manuell prüfen:

```powershell
python tests/smoke_api.py --url http://172.20.10.2 --get-interval
```

Die aktuelle Firmware übernimmt Änderungen im **RAM** und speichert sie nicht dauerhaft in `settings.toml`.

## Testergebnis und Abgrenzung

Bei erfolgreichem Abschluss zeigt der Runner:

```text
Alle ausgefuehrten Tests erfolgreich. Intervall wiederhergestellt.
```

Bei einem fehlgeschlagenen Test oder einer fehlgeschlagenen Wiederherstellung gibt das Skript eine Fehlermeldung aus und endet mit Exit-Code `1`.

Diese Tests decken die **HTTP-API** ab. Das tatsächliche MQTT-Sendeintervall und die `offline`-Nachricht des MQTT-Last-Will werden separat im MQTT Explorer bzw. im Abgabevideo kontrolliert. Ob alle Testfälle erfolgreich sind, wird durch die Ausführung am realen Pico W nachgewiesen.
