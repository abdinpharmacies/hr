## 8b7d634520a35aff0d7fcca591995d0871dfafa6

- Author: emadco88-report-server <emadco88@gmail.com>
- Date: 2026-10-27T11:59:44Z
- Subject: ab_odoo_sync_mapping/ UPD

User-facing changes:

- Updated report-side sync mapping behavior.

Files changed:

- `ab_odoo_sync_mapping/README.md`
- `ab_odoo_sync_mapping/__manifest__.py`
- `ab_odoo_sync_mapping/changelog.d/2026-10-26-automatic-queue-control.md`
- `ab_odoo_sync_mapping/changelog.d/2026-10-26-direct-upload-storage.md`
- `ab_odoo_sync_mapping/changelog.d/2026-10-26-immediate-reapply.md`
- `ab_odoo_sync_mapping/changelog.d/2026-10-26-infer-mapping-toggle.md`
- `ab_odoo_sync_mapping/changelog.d/2026-10-26-report-audit-and-ignore.md`
- `ab_odoo_sync_mapping/controllers/report.py`
- `ab_odoo_sync_mapping/data/queue_jobs.xml`
- `ab_odoo_sync_mapping/i18n/ar.po`
- `ab_odoo_sync_mapping/i18n/ar_001.po`
- `ab_odoo_sync_mapping/migrations/19.0.1.7.0/post-migration.py`
- `ab_odoo_sync_mapping/migrations/19.0.1.7.1/end-migration.py`
- `ab_odoo_sync_mapping/migrations/19.0.1.7.2/end-migration.py`
- `ab_odoo_sync_mapping/models/__init__.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_apply_profile.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_mapping_service.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_mapping_toggle_mixin.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_upload_override.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_upload_receipt.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_upload_record.py`
- `ab_odoo_sync_mapping/security/ir.model.access.csv`
- `ab_odoo_sync_mapping/views/mapping_views.xml`
- `ab_odoo_sync_mapping/views/receipt_views.xml`

## Current changes before commit:

User-facing changes:

- Accept Selection-to-Char automatic mapping for both passive mirror mixins in mirror_sync mode; preserve mapping toggles and writable-field checks.
- Updated the module version.

Files changed:

- `ab_odoo_sync_mapping/__manifest__.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_apply_profile.py`
- `ab_odoo_sync_mapping/changelog.d/2026-11-02-open-source-keys.md`
