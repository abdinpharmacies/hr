## Current changes before commit:

User-facing changes:

- Added a manually installed reporting application for branch registration,
  authenticated upload intake, raw receipt audit records, mapping profiles, and
  branch-aware identities.
- Added OCA `queue_job` apply jobs and an active one-minute apply feeder cron.
- Exposed only push health/upload routes; pull event and checkpoint routes are
  not part of the reporting runtime.
- Added administrative views and complete Arabic translations for `ar` and
  `ar_001`.

Files changed:

- `ab_odoo_sync_mapping/__init__.py`
- `ab_odoo_sync_mapping/__manifest__.py`
- `ab_odoo_sync_mapping/controllers/__init__.py`
- `ab_odoo_sync_mapping/controllers/main.py`
- `ab_odoo_sync_mapping/models/__init__.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_apply_profile.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_branch_registry.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_identity.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_mapping_service.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_upload_record.py`
- `ab_odoo_sync_mapping/security/ir.model.access.csv`
- `ab_odoo_sync_mapping/data/crons.xml`
- `ab_odoo_sync_mapping/data/queue_jobs.xml`
- `ab_odoo_sync_mapping/views/mapping_views.xml`
- `ab_odoo_sync_mapping/i18n/ar.po`
- `ab_odoo_sync_mapping/i18n/ar_001.po`
- `ab_odoo_sync_mapping/changelog.d/2026-08-26-mapping-runtime.md`
