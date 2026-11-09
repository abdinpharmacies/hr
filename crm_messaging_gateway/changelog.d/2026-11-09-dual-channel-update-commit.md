# Module update committed — 1b4a369f

- Commit: `1b4a369fb87d111bbe0fe88672b124963c1d2073`
- Author: Alhassan Hossny
- Date: 2026-11-09T14:04:35+02:00
- Original subject: crm_messaging_gateway/feat: isolate channel sending and back up PostgreSQL queues

Separate channel sending controls and Odoo credentials, retain unsupported identities for review, add PostgreSQL queue backup and metrics, and provide masked WhatsApp configuration checks.

Commit preparation checks: changed Python, XML, JavaScript and JSON syntax; SCSS compilation; all six Arabic catalog format checks; addon manifest paths and ownership metadata; and `git diff --check` passed. Earlier Odoo/gateway suite results remain recorded in the existing validation reports. Their temporary logs and test environment were unavailable in this session; those suites were not rerun for this commit. No live database upgrade or service restart was performed.

Files changed:
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
