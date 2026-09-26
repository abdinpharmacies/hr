Recent relevant commits:

- Commit: `933028c84489619fb9bfd5140f2ef51b9065c7cf`
- Author: emadco88
- Date: 2026-09-15T10:21:12+03:00
- Original subject: ab_odoo_replication/ UPD separate ab_users logic in new file
- User-facing changes:
  - Isolated passive report-user identities in a module-owned extension while preserving existing callers.
- Files changed:
  - ab_odoo_replication/models/__init__.py
  - ab_odoo_replication/models/ab_odoo_replication_reports.py
  - ab_odoo_replication/changelog.d/2026-09-03-report-server-passive-cleanup.md

- Commit: `d9cd2fd85dc59f568f5cbc7cc5f6c8191596673d`
- Author: Emadedeen
- Date: 2026-09-14T14:49:18Z
- Original subject: ab_odoo_replication/ FIX use old replication technique for res.users and res.partner
- User-facing changes:
  - Restored SQL-only main-field replication for users and contacts.
  - Added Odoo 15 user chatter-position conversion.
- Files changed:
  - ab_odoo_replication/__manifest__.py
  - ab_odoo_replication/models/ab_odoo_replication.py
  - ab_odoo_replication/tests/test_replication_override.py

- Commit: `2d7bf83f4e493af690389605d15d50c79a309c4f`
- Author: itharrefaat5
- Date: 2026-09-10T14:35:44+03:00
- Original subject: ab_odoo_replication/ FIX slow replication , only replicate insert , and new updates only
- User-facing changes:
  - Limited existing-record ORM writes and callbacks to changed values.
  - Retained ORM write replay for SQL inserts and resolved deferred relations through ORM writes.
- Files changed:
  - ab_odoo_replication/__manifest__.py
  - ab_odoo_replication/models/ab_odoo_replication.py
  - ab_odoo_replication/tests/test_replication_override.py

Current changes before commit:

- User-facing changes:
  - Commit exact-copy SQL inserts/updates before attempting ORM write replay. Replay each affected record in an independent transaction; log errors and continue without losing committed SQL values.
  - Replay only changed writable fields for existing records, with isolated recomputation, replication callbacks, and source audit-date restoration. Read the latest committed values under a row lock so older pending callbacks cannot overwrite newer imports.
  - Preserve SQL-only users/contacts and ORM creation/update for main_rec_id models. Correct SQL NULL values for integer audit fields on mapped creation.
  - Adapt translated and company-dependent column values for SQL while preserving other languages and companies.
  - Resolve exact-copy deferred Many2one values through SQL before replay. Preserve outer import state across nested imports and propagate caller-controlled commit behavior; rollback discards pending replay.
  - Advance replication cursors with SQL progress, maintain sequences, and commit deferred SQL-only relations even when no ORM replay is scheduled.
  - Update the existing regression assertion for SQL-first updates; keep new integration probes and validation scripts outside the addon.
- Validation:
  - Fresh installation and targeted upgrade passed in an isolated Odoo 19 database with HTTP and cron execution disabled; all 33 existing module tests passed.
  - Real transaction checks passed for SQL visibility before replay, validation/database/callback/recompute error isolation, successful continuation, changed-only writes, cursor progress, audit dates, commit/rollback, repeated pending updates, deferred relations, sequence safety, archived records, Arabic preservation, nested imports, extra-domain preservation, and main_rec_id creation/update.
  - SQL-stage failures still propagate; failed replay has no automatic retry. A process interruption after SQL commit can leave ORM side effects unfinished, and write overrides see values already applied by SQL.
  - User-facing string review found only new server diagnostics and internal docstrings/comments; no new or changed UI strings require ar.po/ar_001.po entries.
- Files changed:
  - ab_odoo_replication/models/ab_odoo_replication.py
  - ab_odoo_replication/tests/test_replication_override.py
  - ab_odoo_replication/changelog.d/2026-09-03-report-server-passive-cleanup.md
