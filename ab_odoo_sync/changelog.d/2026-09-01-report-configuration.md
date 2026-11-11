# Report Sync Configuration

## Recent relevant commit

- Commit: `ccf3ea2877884b78e39ed13ed9d12bd1a0712a44`
- Author: Alhassan Hossny
- Date: 2026-09-01
- Subject: `ab_odoo_sync/ add branch report sync setup guide`
- Added the branch and report setup guide and reusable Odoo shell configuration script.

Files changed:

- `ab_odoo_sync/readme.md`
- `ab_odoo_sync/scripts/configure_sync.py`
- `ab_odoo_sync/changelog.d/2026-09-01-sync-setup-script.md`

## Current changes before commit

- Added the safe shared API-key placeholder and reusable placeholder validation.
- Renamed branch destination settings and setup-script variables from `main` to `report` with no legacy fallback.
- Updated active setup and validation documentation to use report terminology.
- Bumped the module version to `19.0.3.1.0`.

Files changed:

- `ab_odoo_sync/__manifest__.py`
- `ab_odoo_sync/data/system_parameters.xml`
- `ab_odoo_sync/i18n/ar.po`
- `ab_odoo_sync/i18n/ar_001.po`
- `ab_odoo_sync/models/ab_odoo_sync_service.py`
- `ab_odoo_sync/readme.md`
- `ab_odoo_sync/scripts/configure_sync.py`
- `ab_odoo_sync/sync-rules.md`
- `ab_odoo_sync/test-guide.md`
