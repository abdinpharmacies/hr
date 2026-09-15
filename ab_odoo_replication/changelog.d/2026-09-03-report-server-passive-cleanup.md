Recent relevant commits:

- Commit: `87fb748c91a9e400eb78fe7127d3c3bbe02e9fde`
- Author: Emadedeen
- Date: 2026-09-14T14:49:18Z
- Original subject: ab_odoo_replication/ FIX use old replication technique for res.users and res.partner
- User-facing changes:
  - Restored direct SQL replication of user/contact main fields while retaining ORM handling for other models.
  - Added Odoo 15 user chatter preference conversion.
- Files changed:
  - ab_odoo_replication/__manifest__.py
  - ab_odoo_replication/models/ab_odoo_replication.py
  - ab_odoo_replication/tests/test_replication_override.py

- Commit: `98d8b27217aa7db4b078d20acb9339a39a47c8fd`
- Author: emadco88
- Date: 2026-09-13T16:32:48+03:00
- Original subject: ab_odoo_replication/ UPD , checked out from hr , orm.write after create to trigger computed values
- User-facing changes:
  - Adopted the HR engine with forced-ID write replay, changed-value updates, and sequence handling.
  - Added passive identity synchronization and placeholder resolution using the standalone ab_users addon.
- Files changed:
  - ab_odoo_replication/__manifest__.py
  - ab_odoo_replication/changelog.d/2026-09-03-report-server-passive-cleanup.md
  - ab_odoo_replication/models/__init__.py
  - ab_odoo_replication/models/ab_odoo_replication.py
  - ab_odoo_replication/models/ab_odoo_replication_log.py
  - ab_odoo_replication/models/ab_odoo_replication_override.py
  - ab_odoo_replication/models/ab_odoo_replication_run.py
  - ab_odoo_replication/security/ir.model.access.csv
  - ab_odoo_replication/tests/test_replication_override.py
  - ab_odoo_replication/views/cron_ab_odoo_replication.xml

Current changes before commit:

- User-facing changes:
  - Isolated reports-specific user handling in an inherited class in models/ab_odoo_replication_reports.py; existing callers and replication behavior remain unchanged.
  - Restored the shared engine file to match pos19 so future shared fixes can be transferred independently.
  - Preserved passive identity placeholders, synchronization cursors, active flags, transaction handling, and the direct res.users ID exception.
  - Keep reports extension/import/dependency changes separate from shared-engine fixes when preparing future commits; do not replace the whole addon from POS.
- Validation:
  - Fresh installation passed in an isolated Odoo 19 database with cron execution disabled.
  - Mocked-source runtime checks passed for registry inheritance, placeholder creation/preservation, core relationship delegation, initial/incremental/full synchronization, same-timestamp pagination, unchanged identities, sequence safety, unchanged real accounts, rollback, and committed identity/cursor persistence.
  - Extracted helper method ASTs match the original implementation; the shared engine matches pos19 byte for byte.
  - User-facing string review found no additions or changes; ar.po and ar_001.po require no updates.
- Files changed:
  - ab_odoo_replication/changelog.d/2026-09-03-report-server-passive-cleanup.md
  - ab_odoo_replication/models/__init__.py
  - ab_odoo_replication/models/ab_odoo_replication.py
  - ab_odoo_replication/models/ab_odoo_replication_reports.py
