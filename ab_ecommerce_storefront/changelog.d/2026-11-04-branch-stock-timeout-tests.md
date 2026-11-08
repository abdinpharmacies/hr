# Branch stock timeout regression coverage

## Current changes before commit:

- Extend the stock integration tests to verify branch-scoped bound parameters, ODBC selection, missing-column fallback, bounded result reads, and no retry of metadata queries after a timeout or partial read.
- Preserve the earlier authoritative-source inventory and branch-refresh rollback coverage.

Files changed:

- `ab_ecommerce_storefront/tests/test_stock_availability.py`
- `ab_ecommerce_storefront/changelog.d/2026-11-04-branch-stock-timeout-tests.md`

Validation: final targeted module upgrades and 51 inventory/reservation tests passed on isolated `codex_eplus_sync_20261104` with 0 failures and 0 errors. Development tests are excluded from runtime deployment packages.

## Relevant prior commit

Commit: `c41e59e50ca037fa3bc6c4de6944dde60b93e3b2`
Author: Mohamed Fawzy
Date: 2026-10-27
Original commit subject: `ab_ecommerce_storefront/FIX: reserve synced Eplus stock at checkout`

- Added stock synchronization and checkout regression coverage.

Files changed relevant to this follow-up:

- `ab_ecommerce_storefront/tests/test_stock_availability.py`
