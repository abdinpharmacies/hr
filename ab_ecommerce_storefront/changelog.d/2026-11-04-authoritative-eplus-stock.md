# Authoritative Eplus inventory refresh

## Current changes before commit:

- Remove the website-delivery guard from selected inventory sync, full-sync preparation, and batch processing. Eplus is the authoritative source; branches issue invoices and deduct stock there outside this storefront flow.
- Preserve native Odoo inventory adjustments, reservations, products, and delivery history. Repeated synchronization sets the source quantity without an additional sales deduction.
- Replace the obsolete guard test with regression coverage for source quantities increasing, decreasing, reaching zero, full sync after delivery, disappeared source rows, branch batching, and failed-refresh rollback.
- Preserve existing English/Arabic catalogs; this change introduces no UI strings.

Files changed:

- `ab_ecommerce_storefront/models/__init__.py` (remove only the guard import; preserve concurrent work)
- `ab_ecommerce_storefront/models/eplus_sync_guard.py` (removed)
- `ab_ecommerce_storefront/tests/test_stock_availability.py`
- `ab_ecommerce_storefront/changelog.d/2026-11-04-authoritative-eplus-stock.md`

Validation:

- Targeted upgrade of `ab_website_sale_product,ab_ecommerce_storefront` on isolated `codex_eplus_sync_20261104`, with HTTP disabled, ports 5169/5172 reserved, workers/cron disabled: 48 tests, 0 failures, 0 errors. Includes stock availability, checkout reservations, public-user access denial, and company/warehouse isolation.
- Both Arabic catalogs passed `msgfmt --check-format`; whitespace checks passed.
- The cloned test database has missing filestore attachments and existing view warnings; these did not fail the focused tests. No live stock update, Eplus write, production upgrade, or server restart was performed.
- Development tests remain in the repository and must be excluded from runtime deployment packages.

- Runtime verification on the isolated database confirmed `Eplus Stock` in `en_US` and `مخزون Eplus` in `ar_001`; the removed guard is absent from the loaded registry.

## Relevant prior commit

Commit: `c41e59e50ca037fa3bc6c4de6944dde60b93e3b2`
Author: Mohamed Fawzy
Date: 2026-10-27
Original commit subject: `ab_ecommerce_storefront/FIX: reserve synced Eplus stock at checkout`

- Introduced the guard under the previous assumption that website deliveries were not deducted in Eplus.

Files changed relevant to this correction:

- `ab_ecommerce_storefront/models/eplus_sync_guard.py`
