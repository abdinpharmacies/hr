# Historical Upload Backfill

## Recent relevant commit

- Commit: `bc8067d`
- Author: emadco88
- Date: 2026-09-01
- Subject: `ab_odoo_sync_upload/ Use report connection settings and guide administrators through configuration`
- Added report database connection settings and administrator configuration guidance for branch upload transport.
- Prevented missing placeholder settings from creating branch upload jobs or HTTP requests.

Files changed:

- `ab_odoo_sync_upload/__manifest__.py`
- `ab_odoo_sync_upload/changelog.d/2026-09-01-report-configuration.md`
- `ab_odoo_sync_upload/data/configuration_todo.xml`
- `ab_odoo_sync_upload/data/system_parameters.xml`
- `ab_odoo_sync_upload/i18n/ar.po`
- `ab_odoo_sync_upload/i18n/ar_001.po`
- `ab_odoo_sync_upload/models/ab_odoo_sync_upload_service.py`
- `ab_odoo_sync_upload/views/configuration_views.xml`

## Current changes before commit

- Added manual historical upload backfills per branch upload source, based on `write_date >= historical_upload_from`.
- Added queued, running, done, failed, and cancelled state tracking with frozen run cutoff, composite cursor, counters, last error, and completion timestamp.
- Processed historical uploads newest-first in queue-job batches, using the existing outbox and sender payload without changing the live-upload pipeline.
- Skipped already-covered upsert outbox events with equal-or-newer source write dates to avoid duplicate historical snapshots.
- Added cancellation, running-edit guards, administrator action checks, multi-edit list controls, and Arabic translations.
- Bumped the module version to `19.0.1.2.0`.

Files changed:

- `ab_odoo_sync_upload/__manifest__.py`
- `ab_odoo_sync_upload/changelog.d/2026-09-01-historical-upload-backfill.md`
- `ab_odoo_sync_upload/data/queue_jobs.xml`
- `ab_odoo_sync_upload/i18n/ar.po`
- `ab_odoo_sync_upload/i18n/ar_001.po`
- `ab_odoo_sync_upload/models/ab_odoo_sync_outbox.py`
- `ab_odoo_sync_upload/models/ab_odoo_sync_upload_source.py`
- `ab_odoo_sync_upload/views/upload_views.xml`
