# Telegram message edits — 19.0.1.7.0

Current changes before commit:
- Accept authenticated Telegram edit events for existing incoming messages in the same account, conversation and company. Update their displayed text/caption in place while preserving earlier content and provider evidence.
- Preserve duplicate-event identity, ignore older revisions, retain unmatched edit evidence without creating conversations, and prevent outgoing messages or staff ORM calls from changing edit history.
- Preserve original location snapshots and historical attachment bytes. Resolve current attachment revisions and receive downloads against their exact event receipts.
- Add an authenticated capability response so upgraded gateways retain edit events while older Odoo consumers await upgrade.
- Cover edit ordering, replay conflicts, malformed events, scope, direct mutation denial, attachments, locations and capability endpoint access. Translate new fields in both Arabic catalogs.

Files changed:
- `__manifest__.py`
- `controllers/gateway.py`
- `models/__init__.py`
- `models/messaging.py`
- `models/media.py`
- `models/location.py`
- `models/edits.py`
- `tests/test_messaging.py`
- `tests/test_controller.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `changelog.d/2026-11-08-telegram-message-edits.md`
