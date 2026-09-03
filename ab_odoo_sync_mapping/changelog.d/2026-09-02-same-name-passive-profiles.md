# Same-Name Passive Profile Auto-Mapping

## Recent relevant commit

- Commit: `a9997ecd29e36a3f19d179f79551da7d6bcfef3e`
- Author: Alhassan Hossny
- Date: 2026-09-02
- Subject: `ab_odoo_sync_mapping: auto-map same-name passive report profiles`
- Added automatic same-name passive profiles and safe stored-field mapping.

Files changed:

- `ab_odoo_sync_mapping/changelog.d/2026-09-02-same-name-passive-profiles.md`
- `ab_odoo_sync_mapping/i18n/ar.po`
- `ab_odoo_sync_mapping/i18n/ar_001.po`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_apply_profile.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_mapping_service.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_upload_record.py`

## Current changes before commit

- Classify same-name scalar and relational fields from model or payload metadata
  and enable only safely inferred mappings.
- Resolve Many2one and Many2many references through `(db_serial, rec_id)` for
  sync models and through source-ID identities for business models.
- Evolve automatically generated profiles when later payload revisions introduce
  new compatible fields, while preserving explicit profiles and mappings.
- Apply mapped fields when payload fields are absent from the report model and
  mark the upload as `Partially Applied` with the skipped-field list.
- Treat enabled `Ignore` mappings as handled fields so intentionally omitted
  payload fields can finish as fully applied.
- Add administrator-owned per-upload field overrides and generation-safe manual
  reapplication without creating duplicate target rows.
- Add Arabic translations for the new mapping, status, and reapplication UI.

Files changed:

- `ab_odoo_sync_mapping/__manifest__.py`
- `ab_odoo_sync_mapping/changelog.d/2026-09-02-same-name-passive-profiles.md`
- `ab_odoo_sync_mapping/i18n/ar.po`
- `ab_odoo_sync_mapping/i18n/ar_001.po`
- `ab_odoo_sync_mapping/models/__init__.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_apply_profile.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_mapping_service.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_upload_override.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_upload_record.py`
- `ab_odoo_sync_mapping/security/ir.model.access.csv`
- `ab_odoo_sync_mapping/views/mapping_views.xml`
