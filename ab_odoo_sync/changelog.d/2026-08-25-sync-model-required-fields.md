## 009977908d7046630ecdb3313b94a52a52ca53d0

- Author: Alhassan Hossny <alhassan.hossny@gmail.com>
- Date: Tue Aug 25 10:56:32 2026 +0300
- Subject: ab_odoo_sync: enforce report sync schema rules

User-facing changes:

- Enforced permissive mirror schemas and moved required-value checks into apply-profile mappings.
- Switched Odoo Sync jobs to the Integration Queue Job provider used by the reporting environment at that time.

Files changed:

- `ab_odoo_sync/__manifest__.py`
- `ab_odoo_sync/changelog.d/2026-08-20-never-mirror-reference-models.md`
- `ab_odoo_sync/changelog.d/2026-08-25-sync-model-required-fields.md`
- `ab_odoo_sync/data/ab_odoo_sync_queue_job.xml`
- `ab_odoo_sync/models/ab_odoo_sync_apply_profile.py`
- `ab_odoo_sync/sync-rules.md`

## Current changes before commit:

User-facing changes:

- Reduced `ab_odoo_sync` to a non-application technical core containing only
  shared synchronization rules, services, assets, and the root menu.
- Removed the obsolete MAIN-to-branch event, checkpoint, pull, and cleanup
  runtime from the supported upload-only architecture.
- Updated the upload test guide for separate branch upload and reporting
  mapping applications.

Files changed:

- `ab_odoo_sync/__init__.py`
- `ab_odoo_sync/__manifest__.py`
- `ab_odoo_sync/controllers/`
- `ab_odoo_sync/data/`
- `ab_odoo_sync/i18n/ar.po`
- `ab_odoo_sync/i18n/ar_001.po`
- `ab_odoo_sync/models/__init__.py`
- `ab_odoo_sync/models/ab_odoo_sync_service.py`
- `ab_odoo_sync/models/` obsolete runtime files
- `ab_odoo_sync/security/ir.model.access.csv`
- `ab_odoo_sync/test-guide.md`
- `ab_odoo_sync/views/menus.xml`
- `ab_odoo_sync/views/` obsolete runtime views
- `ab_odoo_sync/changelog.d/2026-08-25-sync-model-required-fields.md`
