# Same-Name Passive Profile Auto-Mapping

## Recent relevant commit

- Commit: `7a0b9a6bca138eb3abd6d09328783ac781d74733`
- Author: Alhassan Hossny
- Date: 2026-09-01
- Subject: `ab_odoo_sync_mapping: queue report mapping from sync events`
- Queued report-side apply feeders from profile and mapping changes so existing received uploads are picked up after configuration changes.

Files changed:

- `ab_odoo_sync_mapping/__manifest__.py`
- `ab_odoo_sync_mapping/changelog.d/2026-08-26-mapping-runtime.md`
- `ab_odoo_sync_mapping/data/crons.xml`
- `ab_odoo_sync_mapping/i18n/ar.po`
- `ab_odoo_sync_mapping/i18n/ar_001.po`
- `ab_odoo_sync_mapping/migrations/19.0.1.2.0/post-migration.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_apply_profile.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_mapping_service.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_upload_record.py`
- `ab_odoo_sync_mapping/views/mapping_views.xml`

## Current changes before commit

- Default new received-upload targets and mirror profile targets to the same technical model name as the source.
- Auto-create same-name passive `mirror_sync` profiles for valid passive report models and load enabled safe stored field mappings.
- Keep report-owned master/reference models out of auto-mirroring and surface pending-mapping errors directing them to `business_model` profiles.
- Enforce strict same-name passive metadata for `mirror_sync` profiles and repair stale non-applied upload targets through profile handling.
- Default relation mappings to source-ID sync for passive sync models and ID-only reference models while leaving stable-key mappings for manual exceptions.
- Add Arabic translations for new report-side validation and pending-mapping messages.

Files changed:

- `ab_odoo_sync_mapping/i18n/ar.po`
- `ab_odoo_sync_mapping/i18n/ar_001.po`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_apply_profile.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_mapping_service.py`
- `ab_odoo_sync_mapping/models/ab_odoo_sync_upload_record.py`
