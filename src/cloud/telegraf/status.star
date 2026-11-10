# Normalisiert Statusnachrichten aus iiot/group/+/status.
# Akzeptiert {"status": "ok"}, "ok" (JSON-String) und ok (Rohtext).
# Alles andere wird als "unknown" gespeichert statt verworfen.

load("json.star", "json")

KNOWN = {"ok": 2, "error": 1, "offline": 0}
MAX_RAW = 200


def apply(metric):
    raw = str(metric.fields.pop("value", "")).strip()

    data = json.decode(raw, None)
    if type(data) == "dict":
        status = data.get("status")
    elif type(data) == "string":
        status = data
    elif data == None:
        status = raw
    else:
        status = None

    status = str(status).strip().lower() if status != None else ""
    if status not in KNOWN:
        status = "unknown"

    metric.fields["status"] = status
    metric.fields["status_code"] = KNOWN.get(status, -1)
    metric.fields["raw"] = raw[:MAX_RAW]
    return metric
