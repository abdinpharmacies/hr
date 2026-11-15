# Recover voice attachments and diagnose contact callbacks

## Committed baseline

- Commit: `c37c7bf213785126738c3d3bf5880c7cf2640721`
- Author: `Alhassan Hossny`
- Date: `2026-11-11T11:52:34+02:00`
- Original subject: `crm_messaging_gateway/docs: record reception recovery and reconciliation controls`

## Current changes before commit:

- Recognize supported audio sent as a document, distinguish missing codec tools from invalid media, retry without sending when dependencies are unavailable, and emit bounded content-free contact rejection categories.
- Normalize native contact cards to supported fields before validation, ignoring extra provider metadata while preserving the original source digest. Keep strict known-field types, size limits and sender/contact separation.
- Preserve the preceding notification and branch-location updates.

Files changed:

- `README.md`
- `app/__init__.py`
- `app/media.py`
- `app/providers.py`
- `app/worker.py`
- `app/main.py`
- `tests/test_whatsapp_reception.py`
