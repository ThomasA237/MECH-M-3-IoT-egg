# IIoT-Umgebungsüberwachung – Gruppe 6

Temperatur- und Luftfeuchteüberwachung für die Produktionsstandorte von yourmuesli.at: Ein Raspberry Pi Pico W mit DHT11 sendet Messwerte per MQTT an den Kurs-Broker. Eine Containerlösung aus Telegraf, InfluxDB und Grafana speichert die Daten aller Gruppen und zeigt sie in einem Dashboard.

Details zu einzelnen Punkten stehen in der [ausführlichen Dokumentation](docs/Dokumentation.qmd), in der [Container-Anleitung](src/cloud/README.md) und in der [Test-Anleitung](tests/README.md).

## Gruppe

| | |
|---|---|
| **Mitglieder** | `<TODO: Vorname Nachname>`, `<TODO: Vorname Nachname>` |
| **MQTT-Gruppenname** | `iiot/group/<TODO: nachname1-nachname2>` |
| **Repository** | <https://github.com/ThomasA237/MECH-M-3-IoT-egg> |

## Video

`<TODO: Link zur Bildschirmaufnahme (z.B. nicht gelistet auf YouTube)>`

## Erreichter Stand

| Teil | Beanspruchte Stufe | Begründung |
|---|---|---|
| Termin 3 – Cloud | **sehr gut + Bonus** | Speicherung in InfluxDB, neue Gruppen werden über `iiot/group/+/...` automatisch aufgenommen, Geräteübersicht mit Anzahl, letzter Verbindung und Status, Kennzahlen Mittelwert/Minimum/Maximum/Anzahl |
| Termin 2 – Tests | **sehr gut** | OpenAPI-basierte Tests mit Schemathesis, zusätzlich eigene Smoke-Tests |

Zusätzlich umgesetzt:
- **Luftfeuchte über MQTT:** eigenes Topic `.../sensor/humidity/state`, in [`asyncapi.yaml`](docs/iot-specs/asyncapi.yaml) dokumentiert. Die Storyline nennt Luftfeuchte als kritischen Einflussfaktor.
- **Sensor-Simulation:** Container mit 5 Sensoren zum Testen ohne echte Geräte.

Bekannte Einschränkungen:
- `POST /config` ändert das Intervall nur im RAM. Nach einem Neustart gilt wieder der Wert aus der `settings.toml`, weil `CIRCUITPY` für das Programm schreibgeschützt ist.
- Der Pico W braucht beim Start Internetzugang für NTP (Zeitstempel in UTC). Ohne NTP startet die Firmware nicht.
- `<TODO: weitere Punkte, die nicht funktionieren>`

## Überblick

### Architektur

```
 Pico W + DHT11                Kurs-Broker                  Laptop / Server (Docker)
┌──────────────┐   MQTT     ┌──────────────────┐  MQTT   ┌──────────┐   ┌──────────┐   ┌─────────┐
│ code.py      │ ─────────▶ │ 158.180.44.197   │ ──────▶ │ Telegraf │──▶│ InfluxDB │──▶│ Grafana │──▶ Browser / iPhone
│ HTTP-API :80 │  TCP 1883  │ iiot/group/#     │         └──────────┘   └──────────┘   └─────────┘    http://<host>:3000
└──────────────┘            └──────────────────┘
       ▲ curl / Tests (lokales Netz)
```

- **Sensor:** Der Pico W misst Temperatur und Luftfeuchte und sendet sie als JSON auf `iiot/group/<gruppe>/sensor/temperature/state` und `.../humidity/state`. Den Gerätestatus (`ok`/`error`) sendet er retained auf `iiot/group/<gruppe>/status`, `offline` meldet der Broker per Last Will. Über eine HTTP-API im lokalen Netz lassen sich Status und Sendeintervall abfragen bzw. ändern.
- **Broker:** Der Kurs-Broker verteilt die Nachrichten aller Gruppen.
- **Speicher:** Telegraf abonniert die Topics aller Gruppen (`+`-Wildcard) und schreibt sie in InfluxDB 2 (Bucket `iiot`, 30 Tage Aufbewahrung).
- **Dashboard:** Grafana zeigt Zeitreihen, Kennzahlen und eine Geräteübersicht.

### Struktur des Repositories

| Pfad | Inhalt |
|---|---|
| [`src/raspi_firmware/`](src/raspi_firmware/) | Firmware für den Pico W (`code.py`, `lib/toml.py`) |
| [`src/cloud/`](src/cloud/) | Containerlösung: [`docker-compose.yml`](src/cloud/docker-compose.yml), Telegraf, Grafana, Sensor-Simulation |
| [`tests/`](tests/) | Testfälle für die HTTP-API (Smoke-Tests, Schemathesis) |
| [`docs/iot-specs/`](docs/iot-specs/) | Spezifikationen: [`asyncapi.yaml`](docs/iot-specs/asyncapi.yaml) (MQTT), [`openapi.yaml`](docs/iot-specs/openapi.yaml) (HTTP), [`conventions.md`](docs/iot-specs/conventions.md) |
| [`docs/`](docs/) | Aufgabenstellung (Quarto) und [ausführliche Dokumentation](docs/Dokumentation.qmd) |
| `src/esp32_firmware/` | ESP32-Vorlage des Kurses, von uns nicht verwendet |

## Mikrocontroller einrichten

### Hardware und Verkabelung

Benötigt werden ein Raspberry Pi Pico W, ein DHT11, ein 10 kΩ-Widerstand, ein Steckbrett, Jumper-Kabel und ein USB-Kabel.

| Pico W | | DHT11 |
|---|---|---|
| Pin 36 – 3V3(OUT) | → | Pin 1 – VCC |
| Pin 29 – GP22 | → | Pin 2 – DATA |
| – | | Pin 3 – nicht verbunden |
| Pin 28 – GND | → | Pin 4 – GND |

Der 10 kΩ-Widerstand kommt zwischen VCC und DATA des DHT11. Bei einem DHT11-Modul mit 3 Pins ist er schon eingebaut. Schaltplan: [Materialien](docs/Materialien.qmd).

### Firmware aufspielen

1. **CircuitPython installieren:** Die `.uf2` für den [Pico W](https://circuitpython.org/board/raspberry_pi_pico_w/) herunterladen. Mit gedrückter `BOOTSEL`-Taste das USB-Kabel einstecken und die `.uf2` auf das Laufwerk `RPI-RP2` kopieren. Der Pico startet neu als Laufwerk `CIRCUITPY`.
2. **Bibliotheken kopieren:** Aus dem [Adafruit CircuitPython Bundle](https://circuitpython.org/libraries) (gleiche Hauptversion wie CircuitPython) nach `CIRCUITPY/lib/` kopieren: `adafruit_dht.mpy`, `adafruit_minimqtt/`, `adafruit_connection_manager.mpy`, `adafruit_ticks.mpy`, `adafruit_ntp.mpy`. Dazu [`src/raspi_firmware/lib/toml.py`](src/raspi_firmware/lib/toml.py) aus diesem Repository.
3. **Programm kopieren:** [`src/raspi_firmware/code.py`](src/raspi_firmware/code.py) in das Hauptverzeichnis von `CIRCUITPY` kopieren.

### `settings.toml` ausfüllen und ins WLAN einbinden

Im Hauptverzeichnis von `CIRCUITPY` eine `settings.toml` anlegen (`<TODO: Pfad zur Vorlage mit Platzhaltern>`) und ausfüllen:

| Schlüssel | Bedeutung |
|---|---|
| `device_id` | eindeutiger Gerätename, z.B. `yourmuesli-innsbruck-01` |
| `wifi_ssid`, `wifi_password` | Zugangsdaten des bestehenden WLANs am Standort |
| `broker_address`, `broker_port`, `mqtt_username`, `mqtt_password` | Kurs-Broker, Passwort aus der Vorlesung |
| `telemetry_topic` | `iiot/group/<gruppe>/sensor` (ohne Messgröße) |
| `status_topic` | `iiot/group/<gruppe>/status` |
| `reading_interval_seconds` | Sendeintervall in Sekunden, mindestens 2 |
| `sensor_pin` | GPIO des Datenpins, `22` bei der Verkabelung oben |

Das WLAN muss **2,4 GHz** und **WPA2-Personal** (Passwort) verwenden. 5 GHz, WPA2-Enterprise und WLANs mit Anmeldeseite (Captive Portal) unterstützt der Pico W nicht. Die Firewall des Standorts muss die unter [Hinweise für die IT-Abteilung](#hinweise-für-die-it-abteilung) genannten Verbindungen erlauben.

### Prüfen, ob es funktioniert

1. **Serielle Konsole öffnen**, z.B. mit dem [Mu Editor](https://codewith.mu/) oder dem VS-Code-Serial-Monitor (115200 Baud). Nach dem Speichern einer Datei startet `code.py` automatisch. Erwartete Ausgabe:
   ```
   Konfiguration geladen.
   WLAN verbunden. IP: 192.168.0.79
   Uhrzeit synchronisiert: 2026-11-22T10:00:00Z
   MQTT verbunden. Status: ok
   HTTP-Server gestartet: http://192.168.0.79/
   Temperatur: 22 °C
   Luftfeuchtigkeit: 45 %
   ```
2. **Onboard-LED:** leuchtet, solange MQTT verbunden ist und der Sensor gültige Werte liefert.
3. **MQTT Explorer** mit dem Broker verbinden und `iiot/group/<gruppe>/#` beobachten: Messwerte erscheinen im eingestellten Intervall, der Status steht auf `{"status": "ok"}`. Nach dem Abstecken des Pico wechselt er nach kurzer Zeit auf `{"status": "offline"}`.
4. **HTTP-API:** `curl http://<ip-des-pico>/status` liefert den aktuellen Status (siehe [HTTP-API](#http-api)).

## Container starten

**Voraussetzungen:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) bzw. Docker Engine mit Compose-Plugin, Git, freie Ports 3000 und 8086, ausgehender Zugriff auf den Broker (TCP 1883).

```bash
git clone https://github.com/ThomasA237/MECH-M-3-IoT-egg.git
cd MECH-M-3-IoT-egg/src/cloud
cp .env.example .env        # Windows: copy .env.example .env
```

In der `.env` setzen:

| Variable | Wert |
|---|---|
| `MQTT_HOST`, `MQTT_PORT`, `MQTT_USERNAME`, `MQTT_PASSWORD` | Kurs-Broker: `158.180.44.197`, `1883`, `bobm`, Passwort aus der Vorlesung |
| `INFLUX_PASSWORD` | frei wählbar, mindestens 8 Zeichen |
| `INFLUX_TOKEN` | lange Zufallszeichenkette, z.B. `openssl rand -hex 32` |
| `GRAFANA_ADMIN_PASSWORD` | frei wählbar |

Die übrigen Werte haben sinnvolle Vorgaben. Die `.env` steht in `.gitignore` und wird nicht committet.

```bash
docker compose up -d        # starten
docker compose ps           # influxdb (healthy), telegraf, grafana laufen
docker compose logs telegraf   # "Connected [tcp://158.180.44.197:1883]"
docker compose down         # stoppen, Daten bleiben erhalten
```

`docker compose down -v` löscht zusätzlich alle gespeicherten Daten. Das ist nötig, wenn Zugangsdaten für InfluxDB in der `.env` nachträglich geändert werden, da InfluxDB diese nur beim ersten Start übernimmt.

**Sensor-Simulation (optional):** Wenn gerade kein Gerät sendet, simuliert ein zusätzlicher Container 5 Sensoren auf dem Kurs-Broker (`test-…`-Gruppen, 3 mit Luftfeuchte, 2 nur Temperatur). Er startet nur manuell:

```bash
docker compose up -d --build simulator   # starten
docker compose stop simulator            # beenden
```

Details: [Container-Anleitung](src/cloud/README.md#sensor-simulation).

## Dashboard nutzen

| Dienst | URL | Login |
|---|---|---|
| Grafana | <http://localhost:3000>, von anderen Geräten (z.B. iPhone im selben Netz) `http://<ip-des-docker-hosts>:3000` | Ansehen ohne Login, Bearbeiten mit `GRAFANA_ADMIN_USER`/`GRAFANA_ADMIN_PASSWORD` |
| InfluxDB | <http://localhost:8086> | `INFLUX_USERNAME`/`INFLUX_PASSWORD`, Data Explorer für eigene Abfragen |

Das Dashboard *IIoT Sensoren* öffnet sich als Startseite und aktualisiert sich alle 10 Sekunden:

- **Kennzahlen oben:** bekannte Geräte, Geräte mit Status `ok`, aktive Geräte (Messwert < 10 min), Ø Temperatur und Ø Luftfeuchte der Auswahl
- **Temperatur** und **Luftfeuchte:** Zeitreihen je Gruppe mit letztem Wert, Mittelwert, Minimum und Maximum in der Legende
- **Geräteübersicht:** je Gruppe letzter Status, Zeitpunkt der letzten Statusmeldung, letzte Temperatur und Luftfeuchte, Zeitpunkt des letzten Messwerts
- **Kennzahlen Temperatur / Luftfeuchte:** Mittelwert, Minimum, Maximum und Anzahl der Messwerte je Gruppe im gewählten Zeitraum
- **Statusverlauf:** `ok`, `error`, `offline` je Gruppe über die Zeit

Über *Gruppe* oben links lassen sich einzelne Gruppen filtern, der Zeitraum wird oben rechts gewählt.

## HTTP-API

Die API ist nur im lokalen Netz des Pico erreichbar (HTTP, Port 80) und folgt [`openapi.yaml`](docs/iot-specs/openapi.yaml) (Version 1.2.0).

| Endpunkt | Methode | Funktion |
|---|---|---|
| `/` | GET | Begrüßungstext |
| `/config` | GET | `device_id` und `reading_interval_seconds` |
| `/config` | POST | Sendeintervall ändern (`reading_interval_seconds`, ganzzahlig, ≥ 2) |
| `/status` | GET | Geräte-ID, Laufzeit, WLAN- und MQTT-Verbindung, letzte Messwerte |

```bash
curl http://<ip-des-pico>/status
curl http://<ip-des-pico>/config
curl -X POST http://<ip-des-pico>/config \
     -H "Content-Type: application/json" \
     -d '{"reading_interval_seconds": 10}'
```

Unbekannte Pfade liefern `404`, falsche Methoden `405` mit `Allow`-Header und ungültige Eingaben `400`.

**Testfälle ausführen** (im Hauptverzeichnis, Laptop im selben Netz wie der Pico):

```powershell
pdm install -G test
pdm run powershell -ExecutionPolicy Bypass -File .\tests\run_api_tests.ps1 -PicoIP <ip-des-pico>
```

Das Skript führt Smoke-Tests und Schemathesis (Examples und Coverage) aus und stellt danach das ursprüngliche Intervall wieder her. Varianten (kurzer Lauf, Fuzzing, nur Smoke-Tests) und der Testumfang: [Test-Anleitung](tests/README.md).

## Hinweise für die IT-Abteilung

**Pico W (WLAN des Standorts):**

| Richtung | Ziel | Protokoll / Port | Zweck |
|---|---|---|---|
| ausgehend | `158.180.44.197` | TCP 1883 | MQTT-Broker (Messwerte, Status) |
| ausgehend | `0.adafruit.pool.ntp.org` | UDP 123 | Uhrzeit beim Start (wechselnde IP-Adressen, Freigabe per Hostname) |
| ausgehend | DNS-Server des Netzes | UDP/TCP 53 | Namensauflösung für NTP |
| lokal | DHCP-Server | UDP 67/68 | IP-Adresse; eine feste DHCP-Reservierung erleichtert den Zugriff auf die HTTP-API |
| eingehend | nur aus dem Verwaltungsnetz | TCP 80 | HTTP-API für Status und Konfiguration |

**Docker-Host:** ausgehend TCP 1883 zum Broker sowie HTTPS (443) zu Docker Hub und PyPI für die Installation. Eingehend TCP 3000 (Grafana) nur aus den Netzen, in denen das Dashboard angesehen wird. InfluxDB (8086) muss von außen nicht erreichbar sein.

**Fernzugriff auf die HTTP-API:** Die API ist bewusst nur lokal erreichbar. Eine Portweiterleitung ins Internet wäre gefährlich: Die API ist unverschlüsselt und hat keine Anmeldung, jeder könnte das Intervall ändern. Der Pico hat zudem kaum Ressourcen für TLS. Außerdem verhindern NAT, wechselnde IP-Adressen, Client-Isolation im WLAN und die Firewall-Richtlinien den direkten Zugriff. Empfehlenswert ist ein **VPN** in das Standortnetz oder ein Gateway im Standortnetz, das die API mit TLS und Anmeldung weiterreicht. Alternativ kann die Konfiguration über MQTT kommen (Gerät abonniert ein Config-Topic). Dann braucht es nur die ohnehin offene ausgehende Verbindung. Ausführliche Diskussion: [Dokumentation](docs/Dokumentation.qmd), Abschnitt „Empfehlungen für die IT-Abteilung“.

## Sicherheit

Die Lösung ist ein Prototyp. Für den Produktivbetrieb bräuchte es zusätzlich:
- **MQTT absichern:** TLS (Port 8883) und eigene Zugangsdaten je Gerät mit ACLs. Derzeit teilen alle Gruppen einen Benutzer und könnten gegenseitig ihre Topics beschreiben.
- **HTTP-API absichern:** Authentifizierung und Verschlüsselung, oder die API durch Konfiguration über MQTT ersetzen.
- **Gerät schützen:** Die Zugangsdaten liegen im Klartext auf dem USB-Laufwerk des Pico. USB-Massenspeicher im Betrieb deaktivieren (`boot.py`) und das Gerät physisch sichern.
- **Dashboard absichern:** Anonymen Zugriff auf Grafana abschalten, HTTPS über einen Reverse Proxy, Port 8086 nicht veröffentlichen, Tokens und Passwörter regelmäßig erneuern.
- **Betrieb:** Firmware-Updates aus der Ferne, Überwachung und Alarmierung bei `offline`- oder Grenzwerten, Backups der InfluxDB.
