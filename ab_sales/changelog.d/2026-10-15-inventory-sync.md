## 9f7c5e97b1b47094478ca41c5be37564ccb43798 — Hossam Elsheikh — 2026-10-15

Original commit subject: ab_sales/Added five backend helper files in ab_sales.

User-facing changes:
- Centralize branch backend reads, submission and recovery in Sales.
- Reuse POS inventory refresh for branch API balance requests.

Files changed:
- ab_sales/changelog.d/2026-10-15-backend-independence.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/__init__.py
- ab_sales/models/ab_sales_header.py
- ab_sales/models/ab_sales_header_backend.py
- ab_sales/models/ab_sales_inventory_backend.py
- ab_sales/models/ab_sales_per_day.py
- ab_sales/models/ab_sales_per_day_backend.py
- ab_sales/models/ab_sales_pos_backend.py
- ab_sales/models/ab_sales_pos_balance_refresh.py
- ab_sales/models/ab_sales_return_backend.py

## Current changes before commit:

- Record the UTC start of each successful accepted branch inventory read in nullable, readonly `last_sync_at`, without a default or historical backfill.
- Share validated updates across remote/default branch cron queries and POS refresh. Lock branch and inventory rows after external reads, recheck timestamp eligibility, and retain equal/newer balances, prices and timestamps.
- Zero only eligible absent rows after a complete successful snapshot; POS zeroing is limited to requested products. Missing configuration and invalid/failed reads preserve the cache.
- Prevent duplicate branch/product rows with a model constraint, reject existing duplicates, bound insert contention and propagate serialization conflicts for safe transaction retry/rollback.
- Use committed reads for branch cache updates; reject invalid/null quantities and unit conversions. Total-only synchronization remains outside timestamp handling; remove its destructive no-store fallback.
- Return selected-branch timestamps in normal, filtered and barcode searches. Preserve numeric refresh responses by default; opt-in metadata returns retained balances, timestamps and success status.
- Check caller access and configured/assigned branches before elevated cache writes. Managers/admins are checked before branch restrictions. Log cache price changes with old/new values, actor and time.
- Show a frozen, single-unit age before failed red balances only in POS search cards. Manual retry recalculates it; success clears it. Reset branch context and reject obsolete refresh responses.
- Preserve the original `ab_sales.ProductCard` call required by the Lead extension. Enable its age label through a POS-only flag; keep invoice lines and Add Products free of age labels. Preserve spinner and disabled-button behavior.
- Append exported English/Arabic translation pairs to both Arabic catalogs.
- Show invoice submission failures through standard dismissible Odoo notifications (danger for failure, warning for unknown outcomes), replacing the error modal and duplicate inline error details. Retain invoice lock/retry guidance and existing success notifications; reuse translated source messages.

Files changed:
- ab_sales/changelog.d/2026-10-15-inventory-sync.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/ab_sales_inventory.py
- ab_sales/models/ab_sales_pos_api.py
- ab_sales/models/ab_sales_pos_balance_refresh.py
- ab_sales/models/ab_sales_ui_api.py
- ab_sales/static/src/pos/pos_action.js
- ab_sales/static/src/pos/pos_action.xml
- ab_sales/static/src/pos/pos_balance_refresh.js
- ab_sales/static/src/pos/pos_product_card.xml

Validation:
- Read-only preflight on configured POS database `abdin_pos`: 2,510 duplicate branch/product pairs, 2,586 extra rows. No records were merged/deleted. No upgrade was run against this database by this task; duplicates require deliberate resolution first. Subsequent inspection found the timestamp column present but the required uniqueness constraint absent.
- Isolated database `ab_sales_sync_validation_20261015`: clean install and targeted `-u ab_sales` upgrade passed; uniqueness constraint verified in PostgreSQL. Existing Odoo services were not stopped; validation used port 4191 with cron disabled.
- External harnesses in `/tmp`: 17 ORM tests, 6 real concurrent-transaction tests, and 7 frontend test groups passed. External SQL reads were mocked.
- Initial browser fixture passed label lifecycle checks but omitted the installed Lead extension and missed a template-call regression. Reverted the incompatible rename, installed Lead in the isolated database, and verified that the real POS action opens. A compiled-card fixture verified the Lead button, age placement, spinner/disabled state and Add Products exclusion; all 7 frontend groups passed again.
- Odoo POT export, both `msgfmt --check-format` checks, runtime Arabic inventory menu/field checks and all eight Arabic JS age messages passed.
- Browser checks of the loaded POS action with mocked rejected, unknown, RPC-failure and saved responses passed: standard notifications rendered, unresolved bills retained, and success cleanup preserved. No real invoice was submitted. JavaScript syntax, XML parsing, both Arabic catalog format checks and diff whitespace checks passed.
- No connector or API module changes, cron schedule changes, new jobs, hooks, migration files or external database writes.

Operational limits:
- `last_sync_at` orders successful Odoo reads; it does not certify replica freshness.
- The original POS database upgrade is blocked by existing duplicates. Live SQL Server execution/posting was not tested.
- Existing legacy addon tests calling the old private helper signature need an explicit read-start timestamp if run separately; new harnesses remain outside the runtime addon.
