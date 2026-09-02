# Stored Computed Field Capture

## Recent relevant commit

- Commit: `46b0a7416b433cf990951254936fae4166e72c90`
- Author: emadco88
- Date: 2026-09-01
- Subject: `ab_odoo_sync_upload/ Use report connection settings and guide administrators through configuration`
- Added report connection settings, administrator guidance, and upload configuration safeguards.

Files changed:

- `ab_odoo_sync_upload/__manifest__.py`
- `ab_odoo_sync_upload/data/configuration_todo.xml`
- `ab_odoo_sync_upload/data/system_parameters.xml`
- `ab_odoo_sync_upload/i18n/ar.po`
- `ab_odoo_sync_upload/i18n/ar_001.po`
- `ab_odoo_sync_upload/models/ab_odoo_sync_upload_service.py`
- `ab_odoo_sync_upload/views/configuration_views.xml`

## Current changes before commit

- Added transaction-scoped upload snapshot collection so overlapping ORM hooks create one pending upsert per source record.
- Captured active upload-source records scheduled for stored computed-field recomputation through Odoo's recompute queue.
- Added low-level stored-write capture as a persistence safety net for recompute and flush writes.
- Kept archive snapshots prepared before unlink while delaying outbox creation until the collector flushes.
- Bumped the module version to `19.0.1.2.0`.

Files changed:

- `ab_odoo_sync_upload/__manifest__.py`
- `ab_odoo_sync_upload/models/ab_odoo_sync_orm_hook.py`
- `ab_odoo_sync_upload/changelog.d/2026-09-02-computed-field-capture.md`
