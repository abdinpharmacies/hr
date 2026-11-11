Recent relevant commit:

- Commit: `ad54994a384f833f482be30e764ed2b8b0d3c31b`
- Author: emadco88
- Date: 2026-09-03
- Original subject: ab_odoo_sync/ UPD sync rules
- User-facing changes:
  - Established the previous baseline for this module before the report-server passive cleanup.
- Files changed:
  - ab_odoo_sync/changelog.d/2026-09-02-same-name-passive-profiles.md
  - ab_odoo_sync/sync-rules.md
  - ab_odoo_sync/test-guide.md

Current changes before commit:

- User-facing changes:
  - Added shared passive mirror metadata fields for report-server sync targets.
  - Removed `required=True` from model field declarations so report sync loads can accept incomplete branch payloads.
- Files changed:
  - ab_odoo_sync/changelog.d/2026-09-03-report-server-passive-cleanup.md
  - ab_odoo_sync/__manifest__.py
  - ab_odoo_sync/models/__init__.py
  - ab_odoo_sync/models/passive_mirror_mixin.py
