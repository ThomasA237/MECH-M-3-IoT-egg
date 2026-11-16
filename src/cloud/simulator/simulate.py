# Simuliert 5 Sensoren auf dem Kurs-Broker, damit das Dashboard auch ohne
# echte Geraete Daten zeigt. Sensor 1-3 senden Temperatur und Luftfeuchte,
# Sensor 4-5 nur Temperatur. Jeder Sensor hat eine eigene MQTT-Verbindung mit
# Status "ok" und Last Will "offline" wie ein echtes Geraet.
#
# Beenden mit Strg+C bzw. "docker compose stop simulator": Die Sensoren melden
# "offline" und loeschen danach ihren retained Status, damit auf dem geteilten
# Broker nichts liegen bleibt.

import json
import math
import os
import random
import signal
import sys
import threading
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

HOST = os.environ["MQTT_HOST"]
PORT = int(os.environ.get("MQTT_PORT") or 1883)
USERNAME = os.environ["MQTT_USERNAME"]
PASSWORD = os.environ["MQTT_PASSWORD"]
PREFIX = os.environ.get("SIM_PREFIX") or "test-group6-sim"
INTERVAL = float(os.environ.get("SIM_INTERVAL") or 10)

# (Nummer, sendet Luftfeuchte, Basistemperatur, Basisluftfeuchte)
SENSORS = [
    (1, True, 21.0, 45.0),
    (2, True, 23.5, 55.0),
    (3, True, 19.0, 65.0),
    (4, False, 22.0, None),
    (5, False, 25.0, None),
]


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class SimSensor:
    def __init__(self, number, with_humidity, base_temp, base_hum):
        self.group = f"{PREFIX}-{number}"
        self.sensor_id = f"sim-{number}"
        self.with_humidity = with_humidity
        self.base_temp = base_temp
        self.base_hum = base_hum
        self.temp_offset = 0.0
        self.hum_offset = 0.0
        self.phase = random.uniform(0, 2 * math.pi)

        topic = f"iiot/group/{self.group}"
        self.status_topic = f"{topic}/status"
        self.temperature_topic = f"{topic}/sensor/temperature/state"
        self.humidity_topic = f"{topic}/sensor/humidity/state"

        self.client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"{self.group}-{random.randint(0, 0xFFFF):04x}",
            protocol=mqtt.MQTTv5,
        )
        self.client.username_pw_set(USERNAME, PASSWORD)
        self.client.will_set(self.status_topic, json.dumps({"status": "offline"}), qos=1, retain=True)
        self.client.on_connect = self.on_connect

    def on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            print(f"{self.group}: Verbindung abgelehnt ({reason_code})", flush=True)
            return
        # Auch nach einem automatischen Reconnect wieder "ok" melden
        self.publish_status("ok")
        print(f"{self.group}: verbunden, Status ok", flush=True)

    def start(self):
        self.client.connect_async(HOST, PORT, keepalive=30)
        self.client.loop_start()

    def publish_status(self, status):
        payload = json.dumps({"status": status, "timestamp": utc_now(), "sensor_id": self.sensor_id})
        return self.client.publish(self.status_topic, payload, qos=1, retain=True)

    def next_values(self):
        # Langsame Schwingung (Periode 1 h) plus kleiner Zufallsdrift
        wave = math.sin(time.time() / 3600 * 2 * math.pi + self.phase)
        self.temp_offset = max(-2.0, min(2.0, self.temp_offset + random.uniform(-0.15, 0.15)))
        temperature = round(self.base_temp + 1.5 * wave + self.temp_offset, 1)
        if not self.with_humidity:
            return temperature, None
        self.hum_offset = max(-8.0, min(8.0, self.hum_offset + random.uniform(-1.0, 1.0)))
        humidity = round(min(100.0, max(0.0, self.base_hum - 4 * wave + self.hum_offset)), 1)
        return temperature, humidity

    def publish_measurement(self):
        if not self.client.is_connected():
            return
        timestamp = utc_now()
        temperature, humidity = self.next_values()
        base = {"timestamp": timestamp, "sensor_id": self.sensor_id}
        self.client.publish(self.temperature_topic, json.dumps({**base, "value": temperature, "unit": "°C"}, ensure_ascii=False))
        line = f"{self.group}: {temperature} °C"
        if humidity is not None:
            self.client.publish(self.humidity_topic, json.dumps({**base, "value": humidity, "unit": "%"}))
            line += f", {humidity} %"
        print(line, flush=True)

    def shutdown(self):
        if self.client.is_connected():
            self.publish_status("offline").wait_for_publish(timeout=5)
            # Leere retained Nachricht loescht den Status auf dem Broker
            self.client.publish(self.status_topic, b"", qos=1, retain=True).wait_for_publish(timeout=5)
        self.client.disconnect()
        self.client.loop_stop()


def main():
    stop = threading.Event()
    # docker stop sendet SIGTERM, Strg+C sendet SIGINT
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())

    sensors = [SimSensor(*spec) for spec in SENSORS]
    print(f"Simulation: {len(sensors)} Sensoren auf {HOST}:{PORT}, Intervall {INTERVAL:g} s", flush=True)
    for sensor in sensors:
        sensor.start()

    while not stop.wait(INTERVAL):
        for sensor in sensors:
            sensor.publish_measurement()

    print("Simulation wird beendet ...", flush=True)
    for sensor in sensors:
        sensor.shutdown()
    print("Simulation beendet.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
