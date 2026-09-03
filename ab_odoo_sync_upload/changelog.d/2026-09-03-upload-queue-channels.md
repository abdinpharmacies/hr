# Upload Queue Channels

## Recent relevant commit

- Commit: `dca01d86b6c006091d7054eb49e9a28a8c42e4f4`
- Author: Alhassan Hossny <alhassan.hossny@gmail.com>
- Date: 2026-09-02
- Subject: `ab_odoo_sync_upload/ Capture stored compute flushes in upload hooks`
- Added transaction-scoped capture for stored computed-field recompute scheduling and flush writes.

Files changed:

- `ab_odoo_sync_upload/changelog.d/2026-09-02-computed-field-capture.md`
- `ab_odoo_sync_upload/models/ab_odoo_sync_orm_hook.py`

## Current changes before commit

- Added module-owned `root.live_sales` and `root.historical_sales` sibling queue channels for branch upload jobs.
- Moved live sender jobs to the live channel and historical scanner jobs to the historical channel.
- Added a dedicated historical sender job that delegates to the existing upload sender logic while keeping historical jobs on the historical channel.
- Used separate historical sender identity keys so live and historical sender jobs do not deduplicate each other.
- Kept historical sender execution limited to explicit historical outbox batches so it cannot drain unrelated live pending outbox rows.
- Added Arabic translations for the new historical sender queue description.

Files changed:

- `ab_odoo_sync_upload/changelog.d/2026-09-03-upload-queue-channels.md`
- `ab_odoo_sync_upload/data/queue_jobs.xml`
- `ab_odoo_sync_upload/i18n/ar.po`
- `ab_odoo_sync_upload/i18n/ar_001.po`
- `ab_odoo_sync_upload/models/ab_odoo_sync_upload_service.py`
- `ab_odoo_sync_upload/models/ab_odoo_sync_upload_source.py`
