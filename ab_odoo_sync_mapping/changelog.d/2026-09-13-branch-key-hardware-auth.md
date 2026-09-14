# Branch Key And Hardware Auth

## Recent relevant commit

- Commit: `d7a7b18ccbdecbe92511574d6e333f8200228d95`
- Author: Alhassan Hossny <alhassan.hossny@gmail.com>
- Date: 2026-09-07
- Original subject: ab_odoo_sync_mapping: harden passive upload apply
- User-facing changes:
  - Hardened passive upload apply handling before adding branch-level upload authentication.

Files changed:

- `ab_odoo_sync_mapping/changelog.d/2026-09-03-report-server-passive-cleanup.md`
- `ab_odoo_sync_mapping/i18n/ar.po`
- `ab_odoo_sync_mapping/i18n/ar_001.po`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_apply_profile.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_branch_registry.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_upload_override.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_upload_record.py`

## Current changes before commit

User-facing changes:

- Replaced shared report upload authorization with per-branch API key hashes and hardware serial binding.
- Added one-time branch API key rotation, first hardware approval/rejection, hardware replacement, and append-only security audit records.
- Rejected unknown branches, missing/wrong keys, invalid serials, pending hardware, and hardware mismatches before upload records, mapping profiles, or apply jobs can be created.
- Protected branch credential and hardware fields from normal writes and sync mappings.
- Rejected internal `ab_odoo_sync*` security models before upload records are created, even when the branch key and hardware serial are valid.
- Added Arabic translations for the new report-side security fields, actions, and errors.
- Bumped the module version to `19.0.1.4.0` and set the developer to the current git user.

Validation:

- Targeted report upgrade passed for `ab_odoo_sync_mapping`.
- Targeted POS upgrade passed for `ab_odoo_sync_upload`.
- Python compile checks passed for `ab_odoo_sync_mapping` and `ab_odoo_sync_upload`.
- Arabic PO format checks passed for both language catalogs in both modules.
- Endpoint smoke checks passed for missing key, missing serial, correct key with approved serial, unknown branch, wrong key, invalid serial, and hardware mismatch.
- Rejected dummy batches created no upload records, apply profiles, or queue jobs; authenticated hardware mismatch created the expected audit record.
- Admin-only rollback checks confirmed non-admin users cannot rotate keys, approve hardware, or replace hardware.
- Pending hardware rollback checks confirmed a second serial cannot overwrite the first pending serial.
- Crafted payload test confirmed internal sync security models are rejected before upload records, profiles, or queue jobs are created.

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
