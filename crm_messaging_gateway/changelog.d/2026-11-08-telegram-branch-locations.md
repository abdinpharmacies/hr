# Native Telegram branch venues — 1.3.0

Current changes before commit:
- Route authorized location operations through Telegram `sendVenue` with title, address and coordinates; retain reply parameters and existing delivery outcome classification.
- Reject malformed coordinates, empty titles/addresses, incompatible content and WhatsApp location sends before any provider request.
- Add disabled-by-default per-account `location_enabled` and document activation after Odoo consumers are upgraded.
- Test native request bodies, receipt handling, failed/uncertain outcomes and durable location payload conflicts/retries.

Files changed:
- `app/__init__.py`
- `app/config.py`
- `app/providers.py`
- `deploy/config.example.json`
- `tests/test_branch_locations.py`
- `tests/test_sqlite_storage.py`
- `README.md`
- `changelog.d/2026-11-08-telegram-branch-locations.md`
