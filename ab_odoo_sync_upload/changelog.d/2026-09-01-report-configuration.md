# Report Connection Configuration

## Recent relevant commit

- Commit: `3a9a41d9c691ecf5e6ca3d029ac58e3f0ad13c62`
- Author: emadco88
- Date: 2026-09-01
- Subject: `ab_odoo_sync_upload/ FIX skip business models`
- Prevented protected master and business models from being loaded as branch upload sources.

Files changed:

- `ab_odoo_sync_upload/models/ab_odoo_sync_upload_source.py`

## Current changes before commit

- Replaced `main_url` and `main_database` with the hard-cutover `report_url` and `report_database` settings.
- Added safe example parameters, an administrator configuration menu, and a one-time installation reminder.
- Prevented placeholder settings from creating queue jobs or HTTP requests.
- Updated report connection messages and Arabic translations.
- Bumped the module version to `19.0.1.1.0`.

Files changed:

- `ab_odoo_sync_upload/__manifest__.py`
- `ab_odoo_sync_upload/data/configuration_todo.xml`
- `ab_odoo_sync_upload/data/system_parameters.xml`
- `ab_odoo_sync_upload/i18n/ar.po`
- `ab_odoo_sync_upload/i18n/ar_001.po`
- `ab_odoo_sync_upload/models/ab_odoo_sync_upload_service.py`
- `ab_odoo_sync_upload/views/configuration_views.xml`
