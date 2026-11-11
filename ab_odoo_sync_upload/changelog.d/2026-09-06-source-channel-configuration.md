# Source Channel Configuration

## Recent relevant commit

- Commit: `e1846242834d4a4f290261698639e9b927f118fe`
- Author: Hossam Elsheikh <hossam.m.elsheikh@gmail.com>
- Date: 2026-09-03
- Subject: `ab_odoo_sync_upload/Added module-owned  and  sibling queue channels for branch upload jobs.`
- Added module-owned live and historical queue channels for upload jobs.
- Separated live and historical sender scheduling paths.

Files changed:

- `ab_odoo_sync_upload/changelog.d/2026-09-02-computed-field-capture.md`
- `ab_odoo_sync_upload/changelog.d/2026-09-03-upload-queue-channels.md`
- `ab_odoo_sync_upload/data/queue_jobs.xml`
- `ab_odoo_sync_upload/doc/stored_computed_field_capture_test_edge_cases.md`
- `ab_odoo_sync_upload/i18n/ar.po`
- `ab_odoo_sync_upload/i18n/ar_001.po`
- `ab_odoo_sync_upload/models/ab_odoo_sync_upload_service.py`
- `ab_odoo_sync_upload/models/ab_odoo_sync_upload_source.py`

## Current changes before commit

User-facing changes:

- Added source-level live and historical queue channel configuration.
- Preserved each outbox event's selected queue channel for retries and recovery.
- Renamed upload queue channels to `root.sync_live` and
  `root.sync_historical`.
- Added an authoritative source-configuration API for bridge modules.
- Grouped pending and failed sender jobs by persisted outbox channel so live and
  historical work are not mixed.
- Bumped the module version to `19.0.1.3.0`.

Files changed:

- `ab_odoo_sync_upload/__manifest__.py`
- `ab_odoo_sync_upload/changelog.d/2026-09-06-source-channel-configuration.md`
- `ab_odoo_sync_upload/data/queue_jobs.xml`
- `ab_odoo_sync_upload/i18n/ar.po`
- `ab_odoo_sync_upload/i18n/ar_001.po`
- `ab_odoo_sync_upload/models/ab_odoo_sync_outbox.py`
- `ab_odoo_sync_upload/models/ab_odoo_sync_upload_service.py`
- `ab_odoo_sync_upload/models/ab_odoo_sync_upload_source.py`
- `ab_odoo_sync_upload/views/upload_views.xml`
