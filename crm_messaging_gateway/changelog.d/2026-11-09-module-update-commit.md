# Module update committed — 549e69e2

- Commit: `549e69e214ea67f695a5981829c1ae272dabf3c6`
- Author: Alhassan Hossny
- Date: 2026-11-09T10:26:24+02:00
- Original subject: crm_messaging_gateway/feat: add SQLite queues and richer Telegram events

Add SQLite queue storage, backup and transfer tools, operational metrics and service configuration. Handle Telegram edits, locations and expanded media payloads with regression coverage.

Validation: 164 gateway tests passed; one FFmpeg-dependent test skipped because FFmpeg is unavailable.

Files changed:
- `app/__init__.py`
- `app/backup.py`
- `app/benchmark.py`
- `app/config.py`
- `app/local_setup.py`
- `app/main.py`
- `app/media.py`
- `app/observability.py`
- `app/odoo.py`
- `app/ops.py`
- `app/providers.py`
- `app/queue_transfer.py`
- `app/receiver.py`
- `app/sqlite_storage.py`
- `app/storage.py`
- `app/telegram_setup.py`
- `app/worker.py`
- `deploy/config.example.json`
- `deploy/crm-messaging-backup.service`
- `deploy/crm-messaging-backup.timer`
- `deploy/crm-messaging-callcenter-backup.service`
- `deploy/crm-messaging-callcenter-backup.timer`
- `deploy/crm-messaging-callcenter-receiver.service`
- `deploy/crm-messaging-callcenter-worker.service`
- `deploy/crm-messaging-callcenter.service`
- `deploy/crm-messaging-gateway.service`
- `deploy/crm-messaging-receiver.service`
- `deploy/crm-messaging-worker.service`
- `migrations/sqlite.sql`
- `requirements.lock`
- `scripts/dev_services.py`
- `tests/test_branch_locations.py`
- `tests/test_edits.py`
- `tests/test_gateway.py`
- `tests/test_incoming_attachments.py`
- `tests/test_locations.py`
- `tests/test_sqlite_storage.py`
- `tests/test_storage.py`
