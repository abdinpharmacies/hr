# Automatic First Hardware Binding

## Recent relevant commit

- Commit: `23f83917a6d9f094d1913620639ce31044e5c959`
- Author: Alhassan Hossny <alhassan.hossny@gmail.com>
- Date: 2026-09-14
- Original subject: `ab_odoo_sync_mapping: add branch key and hardware-bound upload auth`
- User-facing changes: Added branch API keys, hardware approval and replacement, and security audit records for report uploads.

Files changed:

- `ab_odoo_sync_mapping/__manifest__.py`
- `ab_odoo_sync_mapping/changelog.d/2026-09-13-branch-key-hardware-auth.md`
- `ab_odoo_sync_mapping/controllers/report.py`
- `ab_odoo_sync_mapping/i18n/ar.po`
- `ab_odoo_sync_mapping/i18n/ar_001.po`
- `ab_odoo_sync_mapping/models/__init__.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_apply_profile.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_branch_audit.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_branch_hardware_wizard.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_branch_registry.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_mapping_service.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_security.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_upload_override.py`
- `ab_odoo_sync_mapping/security/ir.model.access.csv`
- `ab_odoo_sync_mapping/views/configuration_views.xml`
- `ab_odoo_sync_mapping/views/mapping_views.xml`

## Current changes before commit:

- Bind the first normalized hardware serial after successful branch API-key authentication and continue the same health or upload request.
- Automatically approve a previously pending serial only when the incoming serial matches; reject other serials without replacing the pending or approved identity.
- Preserve explicit administrator rejection until manual approval or replacement.
- Refresh security fields after obtaining the branch row lock; concurrent first requests cannot overwrite the winning binding.
- Keep enrollment private to Python callers so direct RPC cannot skip API-key authentication.
- Record automatic approval with its timestamp and translated reason, without attributing it to a human approver or public user; preserve manual audit attribution.
- Bump the module version to `19.0.1.4.1` and add the audit reason to both Arabic catalogs.

Validation:

- Fresh module installation and targeted upgrade passed in an isolated local database with cron and queue runners disabled.
- Real Odoo ORM checks passed for first binding, normalization, repeated requests, pending/approved mismatches, rejected branches, invalid credentials/serials, and inactive/unknown branches.
- Direct RPC enrollment, direct protected-field writes, and non-admin approval/replacement were rejected; administrator approval and hardware replacement/key rotation passed.
- Separate concurrent transactions with prefetched state passed through Odoo's serialization retry mechanism: different serials produced one approval and one mismatch; identical serials both succeeded with one approval event.
- Local HTTP checks passed for health-first and upload-first binding, matching requests, mismatch HTTP 403, invalid serial HTTP 400, and invalid API-key HTTP 401.
- Exported the module POT before appending translations; both PO format checks and Arabic runtime audit text/field-label checks passed.
- Python syntax and diff whitespace checks passed. No production deployment or queue replay was performed.

Files changed:

- `ab_odoo_sync_mapping/__manifest__.py`
- `ab_odoo_sync_mapping/changelog.d/2026-09-25-sticky-hardware-binding.md`
- `ab_odoo_sync_mapping/i18n/ar.po`
- `ab_odoo_sync_mapping/i18n/ar_001.po`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_branch_registry.py`
