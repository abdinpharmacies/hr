# Website transport and account-scoped workers

Recent relevant commit: `c37c7bf2` — Alhassan Hossny — 2026-11-11 — `crm_messaging_gateway/docs: record reception recovery and reconciliation controls`.

Current changes before commit:

- Add the optional Website polling transport, durable event delivery and agent replies.
- Scope incoming claims, receipt recovery, expired-send recovery, dispatch and reporting by each worker's assigned accounts on PostgreSQL and SQLite.
- Add separate Website, WhatsApp and Telegram service templates and regression tests.
- Preserve the existing unrelated in-progress messaging changes, including read receipts and location handling.

Files changed for this task:

- `README.md`
- `app/config.py`
- `app/odoo.py`
- `app/providers.py`
- `app/sqlite_storage.py`
- `app/storage.py`
- `app/website.py`
- `app/worker.py`
- `deploy/crm-messaging-callcenter-website-worker.service`
- `deploy/crm-messaging-callcenter-whatsapp-worker.service`
- `deploy/crm-messaging-callcenter-telegram-worker.service`
- `tests/test_website.py`
- `changelog.d/2026-11-11-website-adapter.md`
