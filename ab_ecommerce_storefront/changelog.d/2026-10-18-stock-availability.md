# Storefront availability follows reserved and delivered inventory

## Recent relevant commit

Commit: `f32413527ebe6a5dbce219de10d70d29cc953b7d`
Author: Mohamed Fawzy
Date: 2026-09-20
Original subject: `ab_ecommerce_storefront/feat: add call center order workspace`

User-facing changes:

- Show warehouse dispatch separately from final customer delivery in the call center.
- Require completed outgoing deliveries before marking an order delivered.

Files changed (relevant to this update):

- `ab_ecommerce_storefront/models/sale_order.py`
- `ab_ecommerce_storefront/views/call_center_order_views.xml`

## Current changes before commit:

- Limit E-Plus-linked storefront products to the unreserved Odoo stock in the website warehouse. Retain the existing snapshot and configured quantity/percentage limits as additional caps.
- Apply the same availability to product pages, cart limits and checkout checks. Hide products whose selected warehouse has no free stock from the default catalog.
- Use the sale-order default warehouse when the website has none configured. Checkout uses its delivery warehouse, and cross-company warehouses cannot contribute stock.
- Keep native stock operations responsible for reservations, delivery deductions, cancellation releases and returns. Final customer-delivery confirmation never makes a second stock deduction.
- Preserve the earlier uncommitted catalog and performance work.

Files changed:

- `ab_ecommerce_storefront/models/__init__.py`
- `ab_ecommerce_storefront/models/stock_availability.py`
- `ab_ecommerce_storefront/controllers/shop.py`
- `ab_ecommerce_storefront/tests/__init__.py`
- `ab_ecommerce_storefront/tests/test_stock_availability.py`
- `ab_ecommerce_storefront/changelog.d/2026-10-18-stock-availability.md`

## Validation and operating limits

- Targeted `ab_ecommerce_storefront` upgrade passed on neutralized development database `ecom19_home_ux_20261015`, using ports 5569/5572, workers and cron disabled.
- Thirteen inventory tests passed: reservation, delivery without double deduction, cancellation, return, cart stock limits, unit conversion, partial delivery/backorder, sold-out filtering, warehouse isolation, company isolation, warehouse fallback, configured caps, denied public writes and unchanged native-product behavior. Related assertions share test methods.
- Fourteen regression tests passed: thirteen catalog tests and the existing Arabic runtime view-translation test. The combined result is 27 passing test methods, zero failures and zero errors.
- Both Arabic catalogs pass `msgfmt --check-format`. No user-facing source strings were added or changed by this update.
- Python parsing and `git diff --check` passed. Tests remain development-only and must be excluded from production packaging.
- The initial test run exposed an incorrectly constructed product fixture; it was corrected to create the source link on the product template. The final inventory run reports zero failures and zero errors. The isolated database also reports missing existing image attachments; these do not affect the stock assertions.
- The primary `ecom19` database and running storefront process were not upgraded or restarted. Activation requires loading the updated Python module in that process.
- No external database calls or writes are introduced. The existing explicit E-Plus-to-Odoo inventory synchronization remains a separate inventory-adjustment workflow; reconciliation of that synchronization with local sales is outside this change.
- A configured display cap can remain unchanged while free inventory is above that cap. Availability is the minimum of the configured E-Plus allowance and warehouse free stock; the cap itself is not decremented.
- A fresh install of the dependency chain, browser interaction and load testing were not run for this change.

Inventory test log: `/tmp/ab-storefront-stock-validation-final.log`.
Catalog and translation regression log: `/tmp/ab-storefront-stock-regression.log`.
