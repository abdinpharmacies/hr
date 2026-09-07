Recent relevant commit:

- Commit: `c4d41e319d611aa91c2e790fd17901453daf00a2`
- Author: emadco88
- Date: 2026-09-03
- Original subject: ab_odoo_sync_mapping/ UPD default to sync auto
- User-facing changes:
  - Established the previous baseline for this module before the report-server passive cleanup.
- Files changed:
  - ab_odoo_sync_mapping/__manifest__.py
  - ab_odoo_sync_mapping/changelog.d/2026-09-02-same-name-passive-profiles.md
  - ab_odoo_sync_mapping/i18n/ar.po
  - ab_odoo_sync_mapping/i18n/ar_001.po
  - ab_odoo_sync_mapping/models/__init__.py
  - ab_odoo_sync_mapping/models/ab_odoo_sync_apply_profile.py
  - ab_odoo_sync_mapping/models/ab_odoo_sync_mapping_service.py
  - ab_odoo_sync_mapping/models/ab_odoo_sync_upload_override.py
  - ab_odoo_sync_mapping/models/ab_odoo_sync_upload_record.py
  - ab_odoo_sync_mapping/security/ir.model.access.csv
  - ab_odoo_sync_mapping/views/mapping_views.xml

Current changes before commit:

- User-facing changes:
  - Added the shared passive mirror mixin to `ab_odoo_sync_branch_registry` and `ab_odoo_sync_upload_field_override`.
  - Kept sync plumbing models outside this mixin pass while covering the two high-value mapping models from the classification.
  - Blocked enabled apply mappings and upload field overrides from targeting computed, related, non-stored, or otherwise unwritable fields.
  - Allowed disabled stale mappings to remain archived without blocking cleanup writes.
  - Added sync-apply context flags so relation lookups and target writes bypass transfer receive branch/write guards during controlled upload apply.
  - Restored sudo on internal sync target and relation model access after selecting the active apply user, so read-only passive report ACLs do not block mirror creation.
  - Added unique `(db_serial, rec_id)` constraints to the high-value mapping passive models.
  - Added an `active` archive flag to upload field overrides for passive archive compatibility.
  - Fast-pathed archive uploads to write only sync metadata and `active=False`, and to no-op when the mirror row is already absent.

Files changed:
  - ab_odoo_sync_mapping/changelog.d/2026-09-03-report-server-passive-cleanup.md
  - ab_odoo_sync_mapping/i18n/ar.po
  - ab_odoo_sync_mapping/i18n/ar_001.po
  - ab_odoo_sync_mapping/models/ab_odoo_sync_apply_profile.py
  - ab_odoo_sync_mapping/models/ab_odoo_sync_branch_registry.py
  - ab_odoo_sync_mapping/models/ab_odoo_sync_upload_override.py
  - ab_odoo_sync_mapping/models/ab_odoo_sync_upload_record.py
