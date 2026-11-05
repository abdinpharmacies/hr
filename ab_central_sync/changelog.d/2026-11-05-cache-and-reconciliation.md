Current changes before commit:

- Treat missing and legacy uninitialized cache rows as zero sellable central stock after a complete initial snapshot; preserve readiness checks and legacy values.
- Add an administrator-only reconciliation wizard for rejected incoming sales, linking a reviewed pending central sale without posting inventory a second time.
- Require matching store, original line order, products, units, quantities, customer/header, promotions, prices, discounts, stock deductions and financial totals; retain branch and central batch/cost evidence with reason, administrator and timestamp.
- Reject missing predecessors, reused posting evidence (including archived links), unposted/settled/foreign-store sales and unauthorized callers. Keep payloads immutable and preserve ordinary settlement, return and cancellation replay.
- Lock Retry against central acceptance and reconciliation so a stale action cannot reopen an accepted operation.
- Add workflow.md and module-local maintenance instructions requiring workflow updates with future flow changes; link the workflow and recovery procedure from README.md.
- Add exported Odoo 19 translation entries in both Arabic catalogs and increment the module version to 19.0.2.0.1.

Files changed:

- ab_central_sync/AGENTS.md
- ab_central_sync/README.md
- ab_central_sync/__init__.py
- ab_central_sync/__manifest__.py
- ab_central_sync/changelog.d/2026-11-05-cache-and-reconciliation.md
- ab_central_sync/i18n/ar.po
- ab_central_sync/i18n/ar_001.po
- ab_central_sync/models/cache.py
- ab_central_sync/models/operation.py
- ab_central_sync/models/sales.py
- ab_central_sync/security/ir.model.access.csv
- ab_central_sync/views/operations.xml
- ab_central_sync/views/reconciliation.xml
- ab_central_sync/wizard/__init__.py
- ab_central_sync/wizard/sale_reconciliation.py
- ab_central_sync/workflow.md

Verification (2026-11-05):

- Targeted ab_central_sync upgrade passed in the isolated codex_central_sync_recovery_20261105 database; no live database upgrade performed.
- Ten Odoo integration-check groups passed: legacy-cache readiness and no stale balance exposure; branch journal without stock movements; changed-batch rejection with rollback; permission/evidence/mismatch guards; role/store isolation; serial ordering; audited one-time reconciliation and immutable payload; branch acknowledgment/watermarks; settlement and partial return; cancellation reversal.
- Regression harness: /tmp/central_sync_recovery_test.py; results: /tmp/central_sync_recovery_test_results.json. Test fixtures are rollback-only and are not shipped inside the production addon.
- Odoo 19 POT exported before appending translations; both catalogs pass msgfmt --check-format. Runtime en_US/ar_001 reconciliation form buttons and field labels differ as expected.
- Python/XML parsing and git diff --check passed; runtime and workflow files match across both worktrees.

Recent relevant commit:

- Commit: 235b12bb80903a179533d5efc228d3cb336b30a3
- Author: hager yasser
- Date: 2026-11-04T18:03:14+02:00
- Original subject: feat(ab_central_sync): add store-scoped enrollment and custom CA trust
- Select synchronization stores independently of the replica's other sales stores and support a trusted custom CA bundle.
- Preserve legacy-store routing while enforcing enrollment scope and stock readiness.

Files changed:

- ab_central_sync/README.md
- ab_central_sync/changelog.d/2026-11-04-scoped-pilot.md
- ab_central_sync/controllers/main.py
- ab_central_sync/i18n/ar.po
- ab_central_sync/i18n/ar_001.po
- ab_central_sync/models/cache.py
- ab_central_sync/models/enrollment.py
- ab_central_sync/models/operation.py
- ab_central_sync/models/replication.py
- ab_central_sync/models/sales.py
- ab_central_sync/views/enrollment.xml
