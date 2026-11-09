# Dual-channel preparation

Previous module commit: `1da5532ab60577848dc4663276ce411281b711f4`
Author: Alhassan Hossny
Date: 2026-11-09T10:41:10+02:00
Original subject: crm_messaging_gateway/docs: document SQLite operations and messaging updates

Changes included in implementation commit `1b4a369f`:

- Add per-account sending controls and dedicated Odoo credentials while preserving Telegram defaults.
- Pin WhatsApp Graph v26.0 and provide masked configuration consistency checks.
- Preserve unsupported opaque identities in durable review without guessed contacts.
- Back up PostgreSQL queues, verify isolated restoration and report PostgreSQL backlog/polling metrics.
- Restore pinned test dependencies and consolidate the current PostgreSQL deployment runbook.

Verification: see `docs/omnichannel-callcenter-validation.md` in the checkout. Live deployment is gated separately.

Files changed:
- `DEVELOPMENT.md`
- `README.md`
- `app/backup.py`
- `app/config.py`
- `app/odoo.py`
- `app/ops.py`
- `app/postgres_backup.py`
- `app/providers.py`
- `app/sqlite_storage.py`
- `app/storage.py`
- `app/whatsapp_check.py`
- `app/worker.py`
- `deploy/config.example.json`
- `deploy/nginx.conf`
- `requirements-dev.txt`
- `tests/test_dual_channel.py`
- `tests/test_gateway.py`
- `tests/test_storage.py`
- `changelog.d/2026-11-09-dual-channel-preparation.md`
