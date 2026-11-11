## `da68489f` - emadco88 - 2026-08-26

Original commit subject: `ab_odoo_sync_upload/ NEW from reports19`

User-facing changes:

- Added a manually installed branch application for selecting upload sources,
  capturing full stored-field snapshots, and keeping an immutable outbox.
- Added an OCA `queue_job` sender and an inactive one-minute sender cron.
- Added upload connection testing, administrative views, and complete Arabic
  translations for `ar` and `ar_001`.

Files changed:

- `ab_odoo_sync_upload/__init__.py`
- `ab_odoo_sync_upload/__manifest__.py`
- `ab_odoo_sync_upload/models/__init__.py`
- `ab_odoo_sync_upload/models/ab_odoo_sync_orm_hook.py`
- `ab_odoo_sync_upload/models/ab_odoo_sync_outbox.py`
- `ab_odoo_sync_upload/models/ab_odoo_sync_upload_service.py`
- `ab_odoo_sync_upload/models/ab_odoo_sync_upload_source.py`
- `ab_odoo_sync_upload/security/ir.model.access.csv`
- `ab_odoo_sync_upload/data/crons.xml`
- `ab_odoo_sync_upload/data/queue_jobs.xml`
- `ab_odoo_sync_upload/views/upload_views.xml`
- `ab_odoo_sync_upload/i18n/ar.po`
- `ab_odoo_sync_upload/i18n/ar_001.po`
- `ab_odoo_sync_upload/changelog.d/2026-08-26-upload-runtime.md`

## Current changes before commit:

User-facing changes:

- Fixed **Load Installed Models** so models protected by the shared sync rules
  are skipped while valid inactive upload sources continue loading.

Files changed:

- `ab_odoo_sync_upload/models/ab_odoo_sync_upload_source.py`
- `ab_odoo_sync_upload/changelog.d/2026-08-26-upload-runtime.md`
