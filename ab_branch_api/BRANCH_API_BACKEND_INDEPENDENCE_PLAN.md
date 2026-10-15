 
# Isolate the Sales Backend Behind Reviewable Inherited Helpers

## Summary

Make ab_branch_api delegate reads and writes to ab_sales. Introduce focused inheritance files inside ab_sales as the review and future backend-migration boundary.

Callcenter → ab_branch_api → ab_sales inherited helpers
                                  → existing sales workflows
                                  → Odoo ORM / current backend

Live reads and synchronous writes remain supported. No separate service model, stock-batch model, new inventory cache, or additional synchronization jobs are required.

## Inherited helper structure

Add these files under branch ab_sales/models/ and import them after the existing model implementations:

| File | Existing model extended | Responsibility |
|---|---|---|
| ab_sales_header_backend.py | ab_sales_header | Batch-stock reading, batch invoice-status lookup, sale submission delegation, and reconciliation-only entry point |
| ab_sales_return_backend.py | ab_sales_return_header | Return preparation/loading, submission delegation, and reconciliation-only entry point |
| ab_sales_inventory_backend.py | ab_sales_inventory | Selected-product balances/prices and complete branch inventory snapshots |
| ab_sales_per_day_backend.py | ab_sales_per_day | Explicit-branch daily-sales retrieval |
| ab_sales_pos_backend.py | ab_sales_pos_api | Customer lookup/creation delegation and shared branch connection routing |

- Extend existing models with _inherit; do not introduce new Odoo models.
- Use consistently named _backend_* entry points with backend-neutral arguments and documented results.
- Document each entry point’s ORM changes, external reads/writes, transaction ownership, and failure behavior.
- Reuse existing implementations rather than copy their business logic. Use super() for genuine overrides.
- Treat these files as the migration entry points. Initially they may delegate to existing E-Plus implementations elsewhere in ab_sales; this phase does not relocate every legacy SQL statement.

## Implementation changes

### Reuse and consolidate ab_sales behavior

- Delegate aggregate balances to pos_refresh_pos_balances() and obtain refreshed default prices from ab_sales_inventory.
- Move the API-owned batch-stock reader into the header helper file. Reuse its result when populating existing sales-line inventory_json; do not create artificial sales lines.
- Extract a branch-filtered batch invoice-status reader. Keep query execution separate from the cron’s record-update policy.
- Extend existing inventory and daily-sales readers to support explicit branch requests without duplicating queries or changing scheduled callers.
- Consolidate API-specific return loading with existing native return helpers.
- Add reconciliation-only entry points around native recovery primitives. They may inspect committed backend transactions and update Odoo state, but must never submit a new posting.
- Preserve sale and return submission through existing workflows, including installed doctor, promotion, contract, and employee extensions.
- Move necessary API-owned routing, connection, and return-query adaptations into the inherited helper files. Preserve ordinary branch POS behavior.

### Remove backend implementation from ab_branch_api

- Route backend-dependent operations through the inherited helpers. Keep ORM-only bill search, details, notes, and printing delegated to existing ab_sales methods.
- Remove E-Plus connector inheritance/imports, SQL Server queries, server-address selection, connection pools, cursor wrappers, and backend transaction/recovery implementation.
- Retain authentication, request validation, pagination, response formatting, and transport-operation journaling.
- Preserve existing operation records. Pass neutral references or recovery evidence into ab_sales; never introduce a reverse dependency on API-owned models.
- Keep backend reference translation and status interpretation inside ab_sales.

## Compatibility and failure behavior

- Preserve all 20 endpoint names, request fields, response structures, identifiers, tokens, and request revisions. E-Plus-named fields remain compatibility aliases.
- Preserve F1: failed submitted bills remain immutable, and retries reuse the original request without advancing its revision.
- Replace silent balance-refresh failures with explicit unavailable errors. Preserve cached values rather than presenting a failed read as zero stock.
- Preserve branch-specific routing before removing API overrides.
- Preserve required read-triggered ORM updates and reconciliation through explicit helper calls.
- Do not change synchronization schedules, add migration hooks, or perform external synchronization during module installation.

## Verification and rollout

- Review the new inheritance files as a group, with only necessary delegation changes in existing files.
- Test helper contracts, branch isolation, stock quantities/prices, batch JSON, complete inventory snapshots, daily sales, and invoice statuses.
- Test API delegation with mocked helpers and no external connection available.
- Verify ab_branch_api contains no E-Plus connection, SQL Server, or backend transaction logic.
- Verify ordinary POS behavior and installed sales extensions remain intact.
- Test failures, duplicate requests, uncertain commits, reconciliation without posting, and F1 request preservation using mocked transactions or isolated fixtures.
- Keep test artifacts outside production addon packages.
- Implement helpers first, switch API callers second, and remove obsolete API implementations last.
- Upgrade branch ab_sales before ab_branch_api; update callcenter error handling where required.
- Update changelogs, affected English/Arabic messages, the checklist, and the saved architecture plan. Include a short ownership map identifying which helper to change when replacing the backend.

## Implementation record — 2026-10-15

Ownership map (all paths below are under `ab_sales/models/`):

| Backend responsibility | File / private entry points |
|---|---|
| Batch stock, invoice statuses, sales | `ab_sales_header_backend.py`: `_backend_stock_lines`, `_backend_invoice_statuses`, `_backend_submit`, `_backend_reconcile` |
| Returns | `ab_sales_return_backend.py`: `_backend_invoice_date`, `_backend_prepare`, `_backend_submit`, `_backend_reconcile` |
| Historical recovery evidence | `_backend_legacy_reconcile` on headers/returns; shared legacy journal observation is implemented in the header helper |
| Balance/price cache and complete inventory | `ab_sales_inventory_backend.py`: `_backend_product_balances`, `_backend_inventory_snapshot` |
| Daily totals | `ab_sales_per_day_backend.py`: `_backend_sales_day`, `_backend_daily_rows` |
| Branch session lifetime and customer operations | `ab_sales_pos_backend.py`: `_backend_request`, `_backend_customer_values`, `_backend_lookup_customer`, `_backend_create_customer`, `_backend_import_customer` |

Helper arguments use branch/product references and ordinary values. Returned
E-Plus-named keys remain compatibility aliases. No API operation recordsets are
passed into `ab_sales`. Historical lock namespaces remain unchanged so old
in-flight requests and their journals retain the same concurrency boundary.

Consistency and transaction decisions:

- Batch stock, shortage validation, invoice statuses, returns and API daily totals
  use committed reads. Selected-product API refresh opts into committed reads and
  active/valid-unit price validation while reusing native POS bounded connection
  timeouts, quantity calculation and inventory cache updates.
- Ordinary POS informational refresh and scheduled daily-sales consistency remain
  unchanged. The invoice-status cron shares the branch-filtered status reader but
  still owns its existing update/archive policy and schedule.
- Return display and posting share the scoped loader and native conversion helpers;
  posting supplies its own cursor. Selected units/quantities are preserved.
- Native workflows own business transaction commits. Reconciliation helpers own
  read/lock sessions, always roll them back/close them, and never call posting.
  The API owns the final journal update/PostgreSQL commit.
- No callcenter source changes are needed: its existing balance client propagates
  errors before applying cache rows, and its UI marks the retained balance stale.

Implementation checklist:

- [x] Add five inherited backend helper files and load them after native models.
- [x] Switch all backend-dependent API operations to helpers; preserve all 20 endpoint signatures.
- [x] Remove API connector inheritance, connection pools, return cursor wrappers and external SQL/recovery implementations.
- [x] Preserve native submission dispatch, request journals and legacy recovery evidence.
- [x] Preserve committed stock validation and fail explicitly on unavailable balance refresh.
- [x] Consolidate invoice-status and daily-sales query execution with existing callers.
- [x] Export Odoo POT and append moved/new Arabic translations in both language files.
- [x] Validate development registry, targeted upgrades, translation formats and Arabic menu rendering.
- [x] Run isolated mocked branch/failure/recovery tests outside production addon packages.
- [ ] Deployment acceptance: controlled end-to-end POS/callcenter sale and return on an approved test backend.

Validation environment: `abdin_old_pos19`, alternate ports 5069/5072, workers and
cron threads disabled. Targeted `ab_sales` and then `ab_branch_api` upgrades passed.
Existing unrelated documentation-rendering and field/schema warnings remain.
No live external sale, return or inventory write was performed. The controlled
end-to-end posting check remains a deployment acceptance task.

Final verification: 27 mocked checks passed, including endpoint signature preservation,
completed-request replay, unchanged-revision payload rejection, failed-refresh cache
preservation, branch isolation, duplicate product aliases, return cursor scoping,
ordinary POS fallback, and recovery with absent/incomplete/unavailable evidence.
Both PO files passed `msgfmt --check-format`; all moved/new backend messages have
Arabic translations and Odoo module metadata. Runtime `ar_001` menu rendering
differs from `en_US`. `git diff --check` passed. Temporary validation ports were
released. Test source and output are retained outside addon packages at
`/tmp/test_branch_backend.py` and `/tmp/backend-tests-results.txt`.
