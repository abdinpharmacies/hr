Recent relevant commit:

- Commit: `c559d64e5725d0b4ec76b1c745cba803dd17f404`
- Author: emadco88
- Date: 2026-09-01
- Original subject: ab_odoo_replication/ UPD ab_users fields same as in ab_users module created by Dev Team
- User-facing changes:
  - Established the previous baseline for this module before the report-server passive cleanup.
- Files changed:
  - ab_odoo_replication/models/ab_users.py

Current changes before commit:

- User-facing changes:
  - Removed `required=True` from model field declarations so report sync loads can accept incomplete branch payloads.
- Files changed:
  - ab_odoo_replication/changelog.d/2026-09-03-report-server-passive-cleanup.md
  - ab_odoo_replication/models/ab_odoo_replication_log.py
  - ab_odoo_replication/models/ab_odoo_replication_override.py
