# Reconcile historical WhatsApp delivery evidence

## Committed baseline

- Commit: `f88ef6f0b16ecb072e4ecf187d8e048a3cd9a3d7`
- Author: `Alhassan Hossny`
- Date: `2026-11-09T14:05:37+02:00`
- Original subject: `ab_crm_whatsapp_workspace/docs: document guarded pilot and template updates`

## Changes included in implementation commit `fc6257ab`

- Retain the operation-based delivery path and add a unique historical outgoing match with account, destination, reference, branch and company checks.
- Apply monotonic delivery updates without operations, sends, unread changes or reply-window reopening; expose an authorized read-only preview.
- Cover historical receipts, isolation and archive fixtures in tests; translate receipt diagnostics in both Arabic catalogs.
- Preserve preceding CRM, contact and POS-handoff work included in this update.

Files changed:
- `__manifest__.py`
- `models/gateway.py`
- `tests/test_bridge.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
