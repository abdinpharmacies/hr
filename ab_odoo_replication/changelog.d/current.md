# Odoo Replication change log

## Current changes before commit

- Ignore stale database field metadata when selecting fields for product replication.
- Use the loaded Odoo field type and relation for the remaining replication fields.

Files changed:

- `ab_odoo_replication/changelog.d/current.md`
- `ab_odoo_replication/models/ab_odoo_replication.py`

## Recent commits

Commit: `2c8d8059`
Author: emadco88
Date: 2026-11-08
Original subject: `ab_odoo_replication/ FIX checked out from replica19`

User-facing changes:

- Add replica write protections and product replication support to this branch.

Files changed:

- `ab_odoo_replication/__init__.py`
- `ab_odoo_replication/__manifest__.py`
- `ab_odoo_replication/changelog.d/2026-09-03-report-server-passive-cleanup.md`
- `ab_odoo_replication/data/channel_replication.xml`
- `ab_odoo_replication/data/models_to_override.xml`
- `ab_odoo_replication/data/queue_job_record.xml`
- `ab_odoo_replication/models/__init__.py`
- `ab_odoo_replication/models/ab_odoo_replication.py`
- `ab_odoo_replication/models/ab_odoo_replication_download.py`
- `ab_odoo_replication/models/ab_odoo_replication_log.py`
- `ab_odoo_replication/models/ab_odoo_replication_override.py`
- `ab_odoo_replication/models/ab_odoo_replication_reports.py`
- `ab_odoo_replication/models/ab_odoo_replication_run.py`
- `ab_odoo_replication/models/ab_users.py`
- `ab_odoo_replication/security/ir.model.access.csv`
- `ab_odoo_replication/tests/__init__.py`
- `ab_odoo_replication/tests/test_replication_override.py`
- `ab_odoo_replication/views/ab_odoo_replication.xml`
- `ab_odoo_replication/views/cron_ab_odoo_replication.xml`
