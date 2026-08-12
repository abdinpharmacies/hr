## 3db5d596c9429ff082c3fe9b0466692b945f788f

- Author: emadco88 <emadco88@gmail.com>
- Date: Tue Jul 28 15:21:42 2026 +0300
- Subject: INIT commit pos19

User-facing changes:

- Added the Odoo Sync addon for event-driven one-way synchronization from MAIN to BRANCH servers.
- Added sync configuration, event log, checkpoint views, HTTP endpoints, and scheduled branch pull behavior.

Files changed:

- `ab_odoo_sync/__init__.py`
- `ab_odoo_sync/__manifest__.py`
- `ab_odoo_sync/controllers/__init__.py`
- `ab_odoo_sync/controllers/main.py`
- `ab_odoo_sync/data/ab_odoo_sync_cron.xml`
- `ab_odoo_sync/models/__init__.py`
- `ab_odoo_sync/models/ab_odoo_sync_checkpoint.py`
- `ab_odoo_sync/models/ab_odoo_sync_config.py`
- `ab_odoo_sync/models/ab_odoo_sync_event.py`
- `ab_odoo_sync/models/ab_odoo_sync_orm_hook.py`
- `ab_odoo_sync/models/ab_odoo_sync_service.py`
- `ab_odoo_sync/security/ir.model.access.csv`
- `ab_odoo_sync/views/ab_odoo_sync_views.xml`

## Current changes before commit

User-facing changes:

- Replaced free-text branch checkpoint identity with configured `db_serial`.
- Added branch-side sync event states for pending, full sync, partial sync, failed, and manually skipped events.
- Recorded missing branch fields as partial sync details instead of silently ignoring them.
- Added admin actions to mark failed or pending events as Not Sync and to manually clean consumed events.
- Disabled automatic event cleanup and kept cleanup bounded by active `db_serial` checkpoints.
- Added Arabic translations for the new Odoo Sync labels and notifications.

Files changed:

- `ab_odoo_sync/changelog.d/2026-08-12-db-serial-event-state.md`
- `ab_odoo_sync/controllers/main.py`
- `ab_odoo_sync/data/ab_odoo_sync_cron.xml`
- `ab_odoo_sync/i18n/ar.po`
- `ab_odoo_sync/i18n/ar_001.po`
- `ab_odoo_sync/models/__init__.py`
- `ab_odoo_sync/models/ab_odoo_sync_checkpoint.py`
- `ab_odoo_sync/models/ab_odoo_sync_event_state.py`
- `ab_odoo_sync/models/ab_odoo_sync_orm_hook.py`
- `ab_odoo_sync/models/ab_odoo_sync_service.py`
- `ab_odoo_sync/security/ir.model.access.csv`
- `ab_odoo_sync/views/ab_odoo_sync_views.xml`
