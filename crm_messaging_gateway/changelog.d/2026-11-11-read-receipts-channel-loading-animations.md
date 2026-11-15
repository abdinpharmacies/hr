# Read receipts, channel loading and animation attachments

## Committed baseline

- Commit: `c37c7bf213785126738c3d3bf5880c7cf2640721`
- Author: `Alhassan Hossny`
- Date: `2026-11-11T11:52:34+02:00`
- Original subject: `crm_messaging_gateway/docs: record reception recovery and reconciliation controls`

## Current changes before commit:

- Handle Telegram animation before duplicate document metadata; receive GIF documents and dispatch outgoing GIFs with sendAnimation.
- Convert WhatsApp GIFs to bounded silent H.264 MP4 with caption/reply preservation and a 16 MB output cap.
- Persist read-receipt results in dedicated PostgreSQL/SQLite tables and report through authenticated Odoo leases; never couple them to Telegram read behavior.
- Keep missing media codecs retryable; preserve receipt state in queue export, import and backups. Add provider, real-codec, restart and storage tests.
- Preserve the existing uncommitted contact, notification and branch-location changes recorded in their separate entries.

Files changed:

- `README.md`
- `app/__init__.py`
- `app/main.py`
- `app/media.py`
- `app/providers.py`
- `app/queue_transfer.py`
- `app/sqlite_storage.py`
- `app/storage.py`
- `app/worker.py`
- `changelog.d/2026-11-11-contact-audio-recovery.md`
- `changelog.d/2026-11-11-whatsapp-branch-locations.md`
- `migrations/0001.sql`
- `migrations/sqlite.sql`
- `tests/test_animations_receipts.py`
- `tests/test_branch_locations.py`
- `tests/test_gateway.py`
- `tests/test_sqlite_storage.py`
- `tests/test_storage.py`
- `tests/test_whatsapp_reception.py`
- `changelog.d/2026-11-11-read-receipts-channel-loading-animations.md`
