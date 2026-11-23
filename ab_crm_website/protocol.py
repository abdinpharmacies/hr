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


def validate_chat(event):
    if isinstance(event, dict) and type(event.get('version')) is int and event.get('version') == 4:
        from .media_protocol import validate_attachments
        validate_attachments(event.get('attachments'))
        if not event['attachments']:
            raise ValueError('Invalid website media')
        legacy = {key: value for key, value in event.items() if key != 'attachments'}
        legacy.update(version=2, body=event.get('body').strip() or 'Attachment' if isinstance(event.get('body'), str) else 'Attachment')
        legacy['fingerprint'] = fingerprint(legacy)
        validate_chat(legacy)
        if not isinstance(event.get('body'), str) or len(event['body']) > 4096 or event.get('fingerprint') != fingerprint(event):
            raise ValueError('Invalid website media')
        return event
    if not isinstance(event, dict) or set(event) != {
        'version', 'source', 'event_uuid', 'destination', 'identity', 'body', 'fingerprint'
    } or type(event['version']) is not int or event['version'] != 2:
        raise ValueError('Invalid website chat')
    for key in ('source', 'event_uuid'):
        if not isinstance(event[key], str) or str(UUID(event[key])) != event[key]:
            raise ValueError('Invalid website identity')
    destination, identity = event['destination'], event['identity']
    if not isinstance(destination, dict) or set(destination) != {'kind', 'uuid'}:
        raise ValueError('Invalid website destination')
    if destination['kind'] not in ('order', 'livechat'):
        raise ValueError('Invalid website destination')
    if not isinstance(identity, dict) or not {'kind', 'uuid'} <= identity.keys() or set(identity) - {'kind', 'uuid', 'name', 'phone'}:
        raise ValueError('Invalid website identity')
    if identity['kind'] not in ('customer', 'visitor'):
        raise ValueError('Invalid website identity')
    if 'name' in identity and (identity['kind'] != 'customer' or not isinstance(identity['name'], str)
                               or not identity['name'].strip() or len(identity['name']) > 256):
        raise ValueError('Invalid website identity')
    if 'phone' in identity and (identity['kind'] != 'customer' or not isinstance(identity['phone'], str) or len(identity['phone']) > 64):
        raise ValueError('Invalid website identity')
    for value in (destination['uuid'], identity['uuid']):
        if not isinstance(value, str) or str(UUID(value)) != value:
            raise ValueError('Invalid website identity')
    if (not isinstance(event['body'], str) or not 1 <= len(event['body'].strip()) <= 4096
            or event['fingerprint'] != fingerprint(event)):
        raise ValueError('Invalid website message')
    return event


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
    if 'origin_kind' in payload and (event['kind'] != 'order' or payload['origin_kind'] not in ('guest', 'account')):
        raise ValueError('Invalid website origin')
    if 'visitor_identity' in payload:
        value = payload['visitor_identity']
        if event['kind'] != 'order' or not isinstance(value, str) or str(UUID(value)) != value or payload.get('origin_kind') != 'guest':
            raise ValueError('Invalid website identity')
    if 'account_identity' in payload:
        value = payload['account_identity']
        if event['kind'] != 'order' or not isinstance(value, str) or str(UUID(value)) != value:
            raise ValueError('Invalid website identity')
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


def validate_lifecycle(event):
    if not isinstance(event, dict) or set(event) != {
        'version', 'source', 'event_uuid', 'kind', 'destination', 'identity', 'fingerprint'
    } or type(event['version']) is not int or event['version'] != 3:
        raise ValueError('Invalid website lifecycle')
    if event['kind'] not in ('identity_bound', 'session_ended', 'order_dispatched'):
        raise ValueError('Invalid website lifecycle')
    sample = {key: value for key, value in event.items() if key != 'kind'}
    sample.update(version=2, body='lifecycle')
    sample['fingerprint'] = fingerprint(sample)
    validate_chat(sample)
    if event['fingerprint'] != fingerprint(event):
        raise ValueError('Invalid website lifecycle')
    if event['kind'] == 'session_ended' and event['destination']['kind'] != 'livechat':
        raise ValueError('Invalid website lifecycle')
    if event['kind'] == 'order_dispatched' and event['destination']['kind'] != 'order':
        raise ValueError('Invalid website lifecycle')
    if event['kind'] == 'identity_bound' and event['identity']['kind'] != 'customer':
        raise ValueError('Invalid website identity')
    return event
