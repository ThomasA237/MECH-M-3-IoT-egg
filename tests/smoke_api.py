"""Reproduzierbare HTTP-Smoke-Tests fuer den Pico W (Python-Standardbibliothek).

Aufruf aus dem Repository-Hauptverzeichnis:
    python tests/smoke_api.py --url http://192.168.0.79

Fuer das PowerShell-Skript (globale Sicherung/Wiederherstellung):
    python tests/smoke_api.py --url http://192.168.0.79 --get-interval
    python tests/smoke_api.py --url http://192.168.0.79 --set-interval 60

POST /config aendert die Konfiguration im RAM. Der Smoke-Test selbst stellt
sie im finally-Block wieder her. Schemathesis-Aenderungen werden zusaetzlich
vom PowerShell-Runner wiederhergestellt.
"""

import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def request(base_url, method, path, json_body=None, raw_body=None,
            content_type="application/json"):
    if json_body is not None and raw_body is not None:
        raise ValueError("json_body und raw_body schliessen sich aus")
    if json_body is not None:
        data = json.dumps(json_body).encode("utf-8")
    elif raw_body is not None:
        data = raw_body.encode("utf-8") if isinstance(raw_body, str) else raw_body
    else:
        data = None
    headers = {"Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = content_type
    req = Request(base_url.rstrip("/") + path, data=data,
                  headers=headers, method=method)
    try:
        with urlopen(req, timeout=15) as response:
            return response.status, dict(response.headers), response.read().decode("utf-8")
    except HTTPError as error:
        return error.code, dict(error.headers), error.read().decode("utf-8")


def check(label, condition, explanation=""):
    if not condition:
        raise AssertionError("{}: {}".format(label, explanation or "unerwartete Antwort"))
    print("[OK] " + label)


def json_object(body):
    obj = json.loads(body)
    check("Antwort ist JSON-Objekt", isinstance(obj, dict))
    return obj


def has_json_content_type(headers):
    return headers.get("Content-Type", "").split(";", 1)[0].strip().lower() == "application/json"


def get_interval(base_url):
    code, headers, body = request(base_url, "GET", "/config")
    if code != 200 or not has_json_content_type(headers):
        raise AssertionError("GET /config lieferte keinen gueltigen JSON-Response (HTTP {})".format(code))
    config = json.loads(body)
    value = config.get("reading_interval_seconds")
    if type(value) is not int or value < 2:
        raise AssertionError("reading_interval_seconds ist keine Ganzzahl >= 2")
    return value


def set_interval(base_url, value):
    code, headers, body = request(base_url, "POST", "/config",
                                  json_body={"reading_interval_seconds": value})
    if code != 200 or not has_json_content_type(headers):
        raise AssertionError("POST /config fehlgeschlagen: HTTP {}: {}".format(code, body))
    returned = json.loads(body)
    if returned.get("reading_interval_seconds") != value:
        raise AssertionError("POST /config bestaetigt nicht den angeforderten Wert")
    actual = get_interval(base_url)
    if actual != value:
        raise AssertionError("GET /config liefert {}, erwartet {}".format(actual, value))


def run(base_url):
    # 1. HTTP-Grundfunktion
    code, headers, body = request(base_url, "GET", "/")
    check("GET / -> 200 mit Text", code == 200 and bool(body))

    # 2. Ausgangszustand + JSON-Schema-nahe Pruefungen
    code, headers, body = request(base_url, "GET", "/config")
    check("GET /config -> 200", code == 200)
    check("GET /config: Content-Type JSON", has_json_content_type(headers))
    config = json_object(body)
    original = config.get("reading_interval_seconds")
    check("Intervall ist Ganzzahl >= 2", type(original) is int and original >= 2)
    check("config.device_id ist String", isinstance(config.get("device_id"), str)
          and bool(config["device_id"]))

    code, headers, body = request(base_url, "GET", "/status")
    check("GET /status -> 200", code == 200)
    check("GET /status: Content-Type JSON", has_json_content_type(headers))
    status = json_object(body)
    expected = {"device_id", "uptime_seconds", "wifi_connected", "mqtt_connected",
                "last_telemetry", "last_humidity_percent"}
    check("Statusfelder vorhanden", expected.issubset(status))
    check("device_id ist String", isinstance(status["device_id"], str)
          and bool(status["device_id"]))
    check("device_id konsistent", status["device_id"] == config["device_id"])
    check("Uptime ist nichtnegative Ganzzahl", type(status["uptime_seconds"]) is int
          and status["uptime_seconds"] >= 0)
    check("WLAN/MQTT-Status sind Boolean", type(status["wifi_connected"]) is bool
          and type(status["mqtt_connected"]) is bool)
    humidity = status["last_humidity_percent"]
    check("Luftfeuchtigkeit Zahl oder null", humidity is None or
          (type(humidity) in (int, float) and 0 <= humidity <= 100))
    telemetry = status["last_telemetry"]
    check("Telemetrie Objekt oder null", telemetry is None or
          (isinstance(telemetry, dict) and
           {"timestamp", "value", "unit"}.issubset(telemetry)))

    # 3. Negativtests (ohne Zustandsaenderung)
    code, _, _ = request(base_url, "GET", "/does-not-exist")
    check("Unbekannter Pfad -> 404", code == 404)
    code, _, _ = request(base_url, "GET", "/favicon.ico")
    check("Browser-Favicon -> 404, kein Absturz", code == 404)
    code, headers, _ = request(base_url, "DELETE", "/config")
    allow = next((str(value) for key, value in headers.items() if key.lower() == "allow"), "")
    check("DELETE /config -> 405 mit Allow", code == 405 and
          "GET" in allow and "POST" in allow)
    code, _, _ = request(base_url, "POST", "/status", json_body={})
    check("POST /status -> 405", code == 405)
    code, _, _ = request(base_url, "POST", "/config", raw_body="{invalid json")
    check("Ungueltiges JSON -> 400", code == 400)
    code, _, _ = request(base_url, "POST", "/config", json_body={
        "reading_interval_seconds": 10, "device_id": "should-not-change"})
    check("Schreibgeschuetzte/unbekannte Felder -> 400", code == 400)

    invalid_configs = [
        ("Intervall unter 2", {"reading_interval_seconds": 1}),
        ("Intervall String", {"reading_interval_seconds": "10"}),
        ("Intervall Float", {"reading_interval_seconds": 2.5}),
        ("Intervall Boolean", {"reading_interval_seconds": True}),
        ("Intervall null", {"reading_interval_seconds": None}),
        ("Leeres Config-Objekt", {}),
    ]
    for label, payload in invalid_configs:
        code, _, _ = request(base_url, "POST", "/config", json_body=payload)
        check(label + " -> 400", code == 400)
    code, _, _ = request(base_url, "POST", "/config",
                         raw_body='{"reading_interval_seconds": 10}',
                         content_type="text/plain")
    check("Falscher Content-Type -> 400", code == 400)
    check("Ungueltige Requests veraendern Intervall nicht",
          get_interval(base_url) == original)

    # 4. Zulaessige Konfigurationen; immer wiederherstellen
    try:
        for value in (2, 10):
            code, headers, body = request(base_url, "POST", "/config",
                                          json_body={"reading_interval_seconds": value})
            check("POST /config {} -> 200".format(value), code == 200)
            check("POST /config: Content-Type JSON", has_json_content_type(headers))
            check("POST bestaetigt Intervall {}".format(value),
                  json_object(body).get("reading_interval_seconds") == value)
            check("GET /config bestaetigt Intervall {}".format(value),
                  get_interval(base_url) == value)
    finally:
        set_interval(base_url, original)
        check("Urspruengliches Intervall wiederhergestellt", True)

    code, _, _ = request(base_url, "GET", "/status")
    check("Server laeuft nach Fehlerfaellen weiter", code == 200)
    print("\nALLE SMOKE-TESTS BESTANDEN")


def main():
    parser = argparse.ArgumentParser(description="Pico W HTTP-Smoke-Tests")
    parser.add_argument("--url", required=True, help="z.B. http://192.168.0.79")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--get-interval", action="store_true",
                      help="Nur Intervall fuer Runner ausgeben")
    mode.add_argument("--set-interval", type=int, metavar="SECONDS",
                      help="Intervall setzen und Ruecklesung pruefen")
    args = parser.parse_args()
    try:
        if args.get_interval:
            print(get_interval(args.url))
        elif args.set_interval is not None:
            set_interval(args.url, args.set_interval)
            print("Intervall wiederhergestellt: {}".format(args.set_interval))
        else:
            run(args.url)
    except (AssertionError, URLError, TimeoutError, OSError, ValueError,
            UnicodeError, KeyError) as error:
        print("\nTEST FEHLGESCHLAGEN: {}".format(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
