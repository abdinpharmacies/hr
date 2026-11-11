# Unified contacts and open reception

## Committed baseline

- Commit: `200e8767caf0d3919b0f19e4a35e602ca42f0f07`
- Author: `Alhassan Hossny`
- Date: `2026-11-09T14:05:37+02:00`
- Original subject: `crm_messaging_gateway/docs: document dual-channel controls and queue recovery`

## Changes included in implementation commit `a89212d7`

- Order statuses per provider message reference so unmatched historical updates do not block valid updates for other messages.
- Separate incoming-message ordering from delivery-status ordering to prevent reviewed statuses blocking reception.
- Accept bounded opaque sender identifiers without quarantining normal reception.
- Permit reviewed retries of legacy identifier quarantines without losing source content or deduplication.
- Preserve existing signature checks, account routing, outgoing uncertainty controls and attachment normalization.

Validation and rollout: `docs/unified-contacts-rollout.md`. Live rollout completed during the user-managed maintenance window; verification and remaining unmatched historical status evidence are recorded in the rollout document.

Files changed:
- `README.md`
- `app/__init__.py`
- `app/media.py`
- `app/ops.py`
- `app/providers.py`
- `app/sqlite_storage.py`
- `app/storage.py`
- `changelog.d/2026-11-09-whatsapp-reception-contacts.md`
- `changelog.d/2026-11-10-unified-contacts.md`
- `tests/test_dual_channel.py`
- `tests/test_sqlite_storage.py`
- `tests/test_storage.py`
- `tests/test_whatsapp_reception.py`
