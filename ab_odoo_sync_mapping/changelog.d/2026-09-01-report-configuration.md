# Report Sync Configuration

## Recent relevant commit

- Commit: `8c72e6628d71f0e008341fb79385036f19cc62e4`
- Author: emadco88
- Date: 2026-08-26
- Subject: `ab_odoo_sync_mapping/ NEW for reports server`
- Split the report-side receiver, apply mapping, branch registry, and queue runtime into this module.

Files changed:

- `ab_odoo_sync_mapping/`

## Current changes before commit

- Renamed the report HTTP controller file and active mapping messages to report terminology.
- Rejected empty and example-placeholder API keys at the public endpoints.
- Added an administrator API-key configuration menu and a one-time installation reminder.
- Updated Arabic translations from a freshly exported Odoo 19 POT.
- Bumped the module version to `19.0.1.1.0`.

Files changed:

- `ab_odoo_sync_mapping/__manifest__.py`
- `ab_odoo_sync_mapping/controllers/__init__.py`
- `ab_odoo_sync_mapping/controllers/main.py`
- `ab_odoo_sync_mapping/controllers/report.py`
- `ab_odoo_sync_mapping/data/configuration_todo.xml`
- `ab_odoo_sync_mapping/i18n/ar.po`
- `ab_odoo_sync_mapping/i18n/ar_001.po`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_apply_profile.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_upload_record.py`
- `ab_odoo_sync_mapping/views/configuration_views.xml`
