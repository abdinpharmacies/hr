# Website account diagnostics

## Recent relevant commit

- Commit: `7b9fe019a2f6a3c2974d1a9ebd3a3026d845fefd`
- Author: Alhassan Hossny
- Date: 2026-11-23
- Original subject: `crm_messaging_gateway/fix: retry website transaction conflicts safely`
- Preserved queued operations during Website transaction conflicts.
- Files changed: `README.md`, `app/health.py`, `app/odoo.py`, `app/ops.py`,
  `app/sqlite_storage.py`, `app/storage.py`, `app/website.py`,
  `app/website_media_protocol.py`, `app/worker.py`, `tests/test_odoo_conflicts.py`,
  `tests/test_website.py`, `tests/test_website_media.py`,
  `changelog.d/2026-11-17-native-chat.md`, `changelog.d/2026-11-18-order-replies-media.md`,
  `changelog.d/2026-11-18-reliable-conversations.md`, `changelog.d/2026-11-23-two-server-qa.md`.

## Current changes before commit:

- Add optional `app.ops status --account CODE`, scoping counts, ages, backlog and health.
- Reject unknown accounts before queue access and preserve unfiltered status behavior.
- Log classified Website failures with account, phase, version and available HTTP status;
  exclude exception text, credentials, customer content and attachment URLs.
- Test status isolation on SQLite and PostgreSQL, CLI rejection and diagnostic privacy.
- Files changed: `app/ops.py`, `app/website.py`, `tests/test_website_diagnostics.py`,
  `changelog.d/2026-11-23-account-diagnostics.md`.
