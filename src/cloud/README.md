# Containerlösung: Telegraf, InfluxDB und Grafana

```
Sensoren ──MQTT──▶ Kurs-Broker ──▶ Telegraf ──▶ InfluxDB ──▶ Grafana
                  158.180.44.197     (Docker)      (Docker)     (Docker)
```

- **Telegraf** abonniert `iiot/group/+/sensor/temperature/state`, `iiot/group/+/sensor/humidity/state` und `iiot/group/+/status`. Neue Gruppen werden über die Wildcard automatisch aufgenommen. Der Gruppenname aus dem Topic wird als Tag `group` gespeichert.
- **InfluxDB 2** speichert die Zeitreihen im Bucket `iiot` (Standard: 30 Tage Aufbewahrung).
- **Grafana** zeigt das vorkonfigurierte Dashboard *IIoT Sensoren*.

## Start

Voraussetzung: [Docker Desktop](https://www.docker.com/products/docker-desktop/) bzw. Docker Engine mit Compose-Plugin.

```bash
git clone <url-des-forks>
cd MECH-M-3-IIoT/src/cloud
cp .env.example .env      # Windows: copy .env.example .env
# .env öffnen: MQTT_PASSWORD, INFLUX_PASSWORD, INFLUX_TOKEN, GRAFANA_ADMIN_PASSWORD setzen
docker compose up -d
```

Stoppen mit `docker compose down`. Mit `docker compose down -v` werden zusätzlich alle gespeicherten Daten gelöscht.

Hinweis: InfluxDB übernimmt Benutzer, Organisation, Bucket und Token nur beim **ersten** Start. Wer diese Werte in der `.env` später ändert, muss die Volumes mit `docker compose down -v` zurücksetzen.

## Nutzung

| Dienst   | URL                     | Login                                                     |
|----------|-------------------------|-----------------------------------------------------------|
| Grafana  | <http://localhost:3000> | ohne Login lesbar; Bearbeiten mit `GRAFANA_ADMIN_USER`/`GRAFANA_ADMIN_PASSWORD` |
| InfluxDB | <http://localhost:8086> | `INFLUX_USERNAME`/`INFLUX_PASSWORD` (Data Explorer für eigene Abfragen) |

Das Dashboard *IIoT Sensoren* zeigt:

- **Kennzahlen oben:** Anzahl bekannter Geräte, Geräte mit Status `ok`, Geräte mit Messwert in den letzten 10 Minuten, Durchschnittstemperatur und durchschnittliche Luftfeuchte der Auswahl
- **Temperatur** und **Luftfeuchte:** je eine Zeitreihe pro Gruppe, Legende mit letztem Wert, Mittelwert, Minimum und Maximum
- **Geräteübersicht:** je Gruppe der letzte Status, Zeitpunkt der letzten Statusmeldung, letzte Temperatur, letzte Luftfeuchte und Zeitpunkt des letzten Temperaturmesswerts
- **Kennzahlen Temperatur / Luftfeuchte (Zeitraum):** Mittelwert, Minimum, Maximum und Anzahl der Messwerte je Gruppe
- **Statusverlauf:** zeitlicher Verlauf von `ok`, `error`, `offline` je Gruppe

Über die Auswahl *Gruppe* oben links lassen sich einzelne Gruppen filtern.

## Umgang mit fehlerhaften Nachrichten

- **Temperatur und Luftfeuchte:** Payloads, die kein JSON sind oder kein numerisches `value` enthalten, verwirft Telegraf mit einer Meldung im Log (`docker compose logs telegraf`). Der Zeitstempel ist die Empfangszeit, da Geräte ohne NTP-Synchronisation falsche Zeiten senden.
- **Status:** [`telegraf/status.star`](telegraf/status.star) akzeptiert `{"status": "ok"}`, `"ok"` und reinen Text `ok`, unabhängig von Groß- und Kleinschreibung. Alles andere wird als `unknown` gespeichert. Die Originalnachricht bleibt im Feld `raw` erhalten.

## Datenmodell in InfluxDB

Die Luftfeuchte ist eine eigene Erweiterung der Kursspezifikation (Topic `iiot/group/{group}/sensor/humidity/state`, Payload wie bei der Temperatur mit `"unit": "%"`, siehe `docs/iot-specs/asyncapi.yaml`). Das Measurement `humidity` legt InfluxDB beim ersten Messwert automatisch an.

| Measurement     | Tags    | Felder                                                   |
|-----------------|---------|----------------------------------------------------------|
| `temperature`   | `group` | `value` (float), `unit`, `sensor_id` (optional, string)  |
| `humidity`      | `group` | `value` (float, % r. F.), `unit`, `sensor_id` (optional, string) |
| `device_status` | `group` | `status` (`ok`/`error`/`offline`/`unknown`), `status_code` (2/1/0/-1), `raw` |

## Dateien

- [`docker-compose.yml`](docker-compose.yml): Dienste, Ports, Volumes
- [`.env.example`](.env.example): Vorlage für Zugangsdaten
- [`telegraf/telegraf.conf`](telegraf/telegraf.conf): MQTT-Abonnements und InfluxDB-Ausgabe
- [`grafana/provisioning/`](grafana/provisioning/): Datenquelle und Dashboard-Provider
- [`grafana/dashboards/iiot.json`](grafana/dashboards/iiot.json): Dashboard
