Recent relevant commits:

- Commit: `03ebab7432755ca860a8af200387c68fe2183b36`
- Author: Alhassan Hossny
- Date: 2026-09-06
- Original subject: ab_odoo_replication: clean report sync fields
- User-facing changes:
  - Allowed incomplete replication configuration by removing required field declarations.
- Files changed:
  - ab_odoo_replication/changelog.d/2026-09-03-report-server-passive-cleanup.md
  - ab_odoo_replication/models/ab_odoo_replication_log.py
  - ab_odoo_replication/models/ab_odoo_replication_override.py

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
  - Added independently callable `replicate_ab_users(limit=10000, commit=True, replicate_all=False)` to copy remote user names and logins with matching local IDs.
  - Track passive-user progress separately; replay the last timestamp to catch same-second updates without rewriting unchanged identities. Full refresh ignores the saved cursor.
  - Create missing passive user placeholders when resolving `ab_users` relations, preserving existing records and active flags. Keep `res.users` relation IDs without implicitly creating real accounts.
  - Depend on the standalone `ab_users` addon for model ownership and access rights.
  - Retained the checked-out forced-ID cache refresh, ORM write replay, callback, and sequence handling changes and their test updates.
  - Retained the checked-out required configuration fields, version bump, removal of the duplicate passive model import/ACLs, and expanded schema/cron calls, including explicit real-user replication.
- Validation:
  - Fresh installation and focused Odoo/PostgreSQL checks passed in an isolated temporary database with mocked remote responses: initial/incremental/full imports, pagination, placeholders, sequence safety, unchanged real users, and batch commit/rollback behavior.
  - No new or updated user-facing strings in this addition; Arabic translation files need no changes.
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
