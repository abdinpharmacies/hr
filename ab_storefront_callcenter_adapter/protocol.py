import hashlib
import json
import math
from uuid import UUID


def fingerprint(event):
    return hashlib.sha256(
        json.dumps(
            {k: v for k, v in event.items() if k != "fingerprint"},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode()
    ).hexdigest()


def validate(event):
    if not isinstance(event, dict) or set(event) != {
        "version",
        "source",
        "order_uuid",
        "event_uuid",
        "revision",
        "kind",
        "payload",
        "fingerprint",
    }:
        raise ValueError("Invalid website event")
    if (
        type(event["version"]) is not int
        or event["version"] != 1
        or type(event["revision"]) is not int
        or event["revision"] < 1
    ):
        raise ValueError("Invalid website version")
    for key in ("source", "order_uuid", "event_uuid"):
        if not isinstance(event[key], str) or str(UUID(event[key])) != event[key]:
            raise ValueError("Invalid website identity")
    if event["kind"] not in ("order", "message") or not isinstance(
        event["payload"], dict
    ):
        raise ValueError("Invalid website content")
    if len(json.dumps(event, allow_nan=False)) > 524288 or event[
        "fingerprint"
    ] != fingerprint(event):
        raise ValueError("Invalid website fingerprint")
    payload = event["payload"]
    if event["kind"] == "message":
        if (
            set(payload) != {"body"}
            or not isinstance(payload["body"], str)
            or not 1 <= len(payload["body"].strip()) <= 4096
        ):
            raise ValueError("Invalid website message")
        return event
    if (
        not {
            "customer",
            "lines",
            "currency",
            "total",
            "payments",
            "fulfillment",
            "notes",
            "reference",
        }
        <= payload.keys()
    ):
        raise ValueError("Incomplete website order")
    if "public_reference" in payload and (
        not isinstance(payload["public_reference"], str)
        or len(payload["public_reference"]) > 128
    ):
        raise ValueError("Invalid website public reference")
    if not isinstance(payload["customer"], dict) or any(
        not isinstance(payload["customer"].get(k), str)
        or len(payload["customer"][k]) > 10000
        for k in ("name", "phone", "address")
    ):
        raise ValueError("Invalid website customer")
    if (
        any(
            not isinstance(payload.get(key), str)
            for key in ("reference", "currency", "notes")
        )
        or not isinstance(payload["payments"], list)
        or not isinstance(payload["fulfillment"], dict)
    ):
        raise ValueError("Invalid website evidence")
    if type(payload["total"]) not in (int, float) or not math.isfinite(
        payload["total"]
    ):
        raise ValueError("Invalid website total")
    if not isinstance(payload["lines"], list) or not 1 <= len(payload["lines"]) <= 500:
        raise ValueError("Invalid website lines")
    for line in payload["lines"]:
        if not isinstance(line, dict) or any(
            not isinstance(line.get(k), str) for k in ("serial", "unit", "name")
        ):
            raise ValueError("Invalid website mapping")
        if "unit_name" in line and (
            not isinstance(line["unit_name"], str) or len(line["unit_name"]) > 10000
        ):
            raise ValueError("Invalid website unit name")
        if "is_delivery" in line and type(line["is_delivery"]) is not bool:
            raise ValueError("Invalid website delivery flag")
        for key in ("quantity", "price", "discount", "subtotal", "total"):
            value = line.get(key)
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError("Invalid website value")
        if line["quantity"] <= 0 or not 0 <= line["discount"] <= 100:
            raise ValueError("Invalid website quantity")
    return event
