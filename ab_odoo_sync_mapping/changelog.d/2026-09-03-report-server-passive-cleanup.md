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
  - Gave the Received Uploads `Partially Applied` status a dedicated `#2775A7` badge color with white text instead of sharing the pending warning color.
  - Updated sync mapping rules so source `create_uid` and `write_uid` can target `ab_users` mirror fields.
  - Removed `required=True` from model field declarations so report sync loads can accept incomplete branch payloads.
- Files changed:
  - ab_odoo_sync_mapping/changelog.d/2026-09-03-report-server-passive-cleanup.md
  - ab_odoo_sync_mapping/__manifest__.py
  - ab_odoo_sync_mapping/models/ab_odoo_sync_apply_profile.py
  - ab_odoo_sync_mapping/models/ab_odoo_sync_branch_registry.py
  - ab_odoo_sync_mapping/models/ab_odoo_sync_identity.py
  - ab_odoo_sync_mapping/models/ab_odoo_sync_upload_override.py
  - ab_odoo_sync_mapping/models/ab_odoo_sync_upload_record.py
  - ab_odoo_sync_mapping/static/src/status_badge/status_badge.js
  - ab_odoo_sync_mapping/static/src/status_badge/status_badge.scss
  - ab_odoo_sync_mapping/views/mapping_views.xml
