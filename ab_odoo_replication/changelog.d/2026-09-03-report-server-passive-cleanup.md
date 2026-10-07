Recent relevant commits:

- Commit: `40e9b25576015b4c52b0d7422d57d8ef388031cf`
- Author: emadco88
- Date: 2026-09-26T18:52:44+03:00
- Original subject: ab_odoo_replication/ UPD sql update/insert then write
- User-facing changes:
  - Commit exact-copy SQL changes before independent, best-effort ORM replay per record.
  - Preserve changed-field replay, audit dates, nested import state, SQL-only exceptions, and caller-controlled commit behavior.
- Files changed:
  - ab_odoo_replication/models/ab_odoo_replication.py
  - ab_odoo_replication/tests/test_replication_override.py
  - ab_odoo_replication/changelog.d/2026-09-03-report-server-passive-cleanup.md

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
  - Fix pre-commit cache assertions during barcode product-link and contract allowed-store replication. Replay scheduling now only captures payloads; it does not discard pending ORM cache values.
  - Flush pending field writes before SQL updates and invalidate inserted/updated values immediately, before extra-field relation writes. Apply the same ordering to deferred Many2one SQL updates.
  - Flush relation writes and their dependent changes at exact-copy batch finalization, then restore source audit dates before scheduling post-commit replay.
  - Preserve relation-only updates, SQL cursor progress, rollback behavior, and per-record replay error isolation.
- Validation:
  - Reproduced the previous assertion in an isolated Odoo 19 database before applying the fix.
  - Installed actual ab_product and ab_contract modules in the isolated database. Runtime checks passed for barcode product_ids and contract allowed_store_ids: SQL insert/update, consecutive batches, populated/empty/changed/unchanged relations, relation-only updates, source dates, caller commit/rollback, nested missing-store imports, and persistence after forced replay failure.
  - Reran transaction checks for changed-only replay, validation/database/callback/recompute failures, unchanged records, audit dates, cursor progress, deferred relations, sequence safety, archived records, translation preservation, SQL errors, nested imports, and main_rec_id creation/update.
  - Targeted module upgrade and all 33 existing module tests passed with HTTP and cron execution disabled; Python syntax and git diff whitespace checks passed.
  - Regression scripts and fixtures remain outside the addon under /tmp/replication_postcommit_e8hf1_7k; no production database writes or service restart were performed.
  - No new or changed UI strings; ar.po and ar_001.po require no translation changes.
- Files changed:
  - ab_odoo_replication/models/ab_odoo_replication.py
  - ab_odoo_replication/changelog.d/2026-09-03-report-server-passive-cleanup.md
