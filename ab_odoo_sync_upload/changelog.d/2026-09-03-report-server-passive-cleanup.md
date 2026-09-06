Recent relevant commit:

- Commit: `7b8b1a42efe77d308f2b5f54f1479aa5e1122622`
- Author: Alhassan Hossny
- Date: 2026-09-02
- Original subject: ab_odoo_sync_upload/ Capture stored compute flushes in upload hooks
- User-facing changes:
  - Established the previous baseline for this module before the report-server passive cleanup.
- Files changed:
  - ab_odoo_sync_upload/__manifest__.py
  - ab_odoo_sync_upload/changelog.d/2026-09-02-computed-field-capture.md
  - ab_odoo_sync_upload/models/ab_odoo_sync_orm_hook.py

Current changes before commit:

- User-facing changes:
  - Removed `required=True` from model field declarations so report sync loads can accept incomplete branch payloads.
  - Made upload capture hooks skip sync metadata lookups while a new registry is still loading, preventing sync module upgrades from failing on partially available models.
- Files changed:
  - ab_odoo_sync_upload/changelog.d/2026-09-03-report-server-passive-cleanup.md
  - ab_odoo_sync_upload/models/ab_odoo_sync_orm_hook.py
  - ab_odoo_sync_upload/models/ab_odoo_sync_outbox.py
  - ab_odoo_sync_upload/models/ab_odoo_sync_upload_source.py
