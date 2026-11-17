# Receive-only Website conversations

Current changes before commit:

- Remove the Website order-reply selector and composer while keeping grouped incoming orders, invoice cards and messages.
- Reject Website reply RPCs and message approvals server-side, and prevent gateway leasing/authorization of old queued Website replies.
- Retain historical messages, order associations, destinations and audits. Preserve Telegram/WhatsApp sending.
- Validate receive-only behavior and unchanged invoice/POS flows in English and Arabic.

Files changed:

- `__manifest__.py`
- `models/adapter.py`
- `static/src/order.xml`
- `tests/test_contact_groups.py`
- `tests/test_pos.py`
- `README.md`
- `changelog.d/2026-11-16-receive-only.md`
