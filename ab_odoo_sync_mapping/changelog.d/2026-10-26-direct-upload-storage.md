# Direct upload storage and receipt removal

Recent relevant commit: `1a0282cbc17619acc773e996288d9e96bc0a5d53`
Author: emadco88-report-server
Date: 2026-10-07
Original subject: ab_odoo_sync_mapping/ FIX it should not refuse to receive any authnicated payload

Current changes before commit:

- Store validated uploads directly in ab_odoo_sync_upload_record before acknowledging delivery, without requiring mapping or target model installation.
- Retain the highest revision per authenticated branch/model/source ID. Exact retries and older revisions preserve application state; newer revisions reset tracking and invalidate obsolete jobs.
- Reject malformed rows, protected models, branch mismatches, same-revision content conflicts, and detectable reuse of current event UUIDs through indexed sender-compatible errors.
- Retry database concurrency/storage failures; retain pending uploads when non-database queue scheduling fails.
- Queue only direct apply jobs for opted-in active apply-capable profiles. Preserve immediate manual reapplication and existing apply feeders.
- Remove the receipt model, UI, access rule, processing job registration, active translations, and documentation.
- Add a bounded 19.0.1.7.0 deployed-upgrade cleanup for receipt jobs, model metadata, and the physical receipt table. No receipt data is migrated.

Validation and production deployment:

- 53 direct-receiver checks passed on both the upgraded isolated database and a fresh installation. Forty manual reapply checks and four real PostgreSQL concurrency checks passed (150 check executions in total).
- Isolated upgrade removed existing receipt jobs and table. Fresh install has no receipt model/table. XML, Python syntax, Arabic message catalogs, and git diff --check passed.
- Scripts and logs are retained outside the production addon under /opt/odoo19/validation/sync_direct and /tmp/sync-direct-*.log.
- Backed up all other report19 data, excluding receipt rows as explicitly requested, to /opt/odoo19/resource-tuning-backups/20261026-direct-upload/report19-without-receipt-data.dump. Archive directory validation passed; backup size is approximately 505 MB.
- Upgraded only ab_odoo_sync_mapping to installed version 19.0.1.7.0 and restarted odoo19.service. Queue runner remains inactive.
- Verified receipt table, model metadata, fields, and processing jobs are absent. Existing upload-record and sales-line counts matched before/after upgrade, before resuming intake; profile snapshots match exactly.
- Observed successful real branch uploads after restart, with disabled profiles pending and enabled sales lines queued. Login endpoint returns HTTP 200.
- Receipt removal released approximately 123 GB; database size is approximately 4.9 GB and filesystem free space approximately 171 GB. No vacuum or historical replay was run.

Files changed:

- `__manifest__.py`
- `README.md`
- `controllers/report.py`
- `models/__init__.py`
- `models/ab_odoo_sync_apply_profile.py`
- `models/ab_odoo_sync_mapping_service.py`
- `models/ab_odoo_sync_upload_record.py`
- `models/ab_odoo_sync_upload_receipt.py` (removed)
- `views/receipt_views.xml` (removed)
- `data/queue_jobs.xml`
- `security/ir.model.access.csv`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `migrations/19.0.1.7.0/post-migration.py`
- `changelog.d/2026-10-26-direct-upload-storage.md`
