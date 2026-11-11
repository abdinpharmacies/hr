# WhatsApp reception, contacts and templates

## Committed baseline

- Commit: `200e8767caf0d3919b0f19e4a35e602ca42f0f07`
- Author: Alhassan Hossny
- Date: 2026-11-09T14:05:37+02:00
- Original subject: crm_messaging_gateway/docs: document dual-channel controls and queue recovery

## Changes included in implementation commit `a89212d7`

- Normalize WhatsApp media, captions/replies, profile metadata, reactions and contact cards.
- Retrieve media through authenticated, account-bound Meta requests with bounded size/duration, content/digest validation and existing queue retries.
- Preserve Telegram polling/configuration/provider-send behavior and extend mocked gateway coverage.

Validation and rollout evidence: `docs/whatsapp-reception-rollout.md`. Runtime rollout and live provider acceptance remain pending the user-managed maintenance window.

Files changed:
- `README.md`
- `app/__init__.py`
- `app/media.py`
- `app/providers.py`
- `changelog.d/2026-11-09-whatsapp-reception-contacts.md`
- `tests/test_whatsapp_reception.py`
