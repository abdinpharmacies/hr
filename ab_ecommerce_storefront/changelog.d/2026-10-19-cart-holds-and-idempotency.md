# Cart holds and duplicate submission protection

## Recent relevant commit

Commit: `04fc6d38c2ebaadb1f1256276747d603fd90b7d7`
Author: Mohamed Fawzy
Date: 2026-09-29
Original subject: `ab_ecommerce_storefront/feat: reuse saved prescription delivery address`

User-facing changes:

- Reuse the customer's saved delivery address when submitting a prescription.

Files changed:

- `ab_ecommerce_storefront/controllers/prescription_order.py`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/views/prescription_order_templates.xml`

## Current changes before commit:

- Hold available website stock for 15 minutes from the first cart addition. Refreshing or editing an active cart does not extend its deadline. Removing an item releases its hold immediately; an expired hold stops reducing availability without a scheduled job or an inventory quantity edit. A later cart mutation can acquire a new hold after checking availability again.
- Display a countdown and expiry message in the cart, using server time. Keep expired items in the cart and check their availability again before checkout. Apply held quantities to catalog filtering, product availability and cart checks, using the actual company and warehouse, including warehouse fallback.
- Serialize competing cart allocations with PostgreSQL row locks and an ORM-written revision. The revision forces conflicting Repeatable Read transactions through Odoo's transaction retry mechanism instead of relying on a lock with a stale snapshot. Store hold quantities in the product's inventory unit.
- Issue unique server-side submission keys for checkout and prescription forms. Bind keys to the website, company, operation and customer/session; compare a canonical payload fingerprint. Repeated successful submissions reuse the existing transaction or prescription and quotation. Reject another owner, changed details or an expired unused form. Failed/cancelled payment attempts can receive a new key when reopening the payment page.
- Prevent direct website-order confirmation from bypassing reservation checks. Native Odoo confirmation must reserve all generated stock moves. A prescription image is received for review; confirmation requires identified products and a confirmed linked sales order.
- Restrict the hold/submission models to administrator read access and private, scoped workflow writes. Add company record rules.
- Wait for frontend translations before starting cart-selection behavior; its previous startup race interrupted the asset bundle and prevented the hold countdown from loading.
- Add English source strings and Arabic translations in both catalogs. Preserve the other ongoing storefront changes.

Files changed:

- `ab_ecommerce_storefront/__manifest__.py`
- `ab_ecommerce_storefront/controllers/__init__.py`
- `ab_ecommerce_storefront/controllers/checkout_submission.py`
- `ab_ecommerce_storefront/controllers/submission_security.py`
- `ab_ecommerce_storefront/controllers/prescription_order.py`
- `ab_ecommerce_storefront/controllers/shop.py`
- `ab_ecommerce_storefront/models/__init__.py`
- `ab_ecommerce_storefront/models/cart_hold.py`
- `ab_ecommerce_storefront/models/checkout_submission.py`
- `ab_ecommerce_storefront/models/prescription_order.py`
- `ab_ecommerce_storefront/security/checkout_security.xml`
- `ab_ecommerce_storefront/security/ir.model.access.csv`
- `ab_ecommerce_storefront/static/src/js/cart_hold.js`
- `ab_ecommerce_storefront/static/src/js/cart_selection.js`
- `ab_ecommerce_storefront/views/cart_hold.xml`
- `ab_ecommerce_storefront/views/prescription_order_templates.xml`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/tests/__init__.py`
- `ab_ecommerce_storefront/tests/test_checkout_reservation.py`
- `ab_ecommerce_storefront/tests/test_stock_availability.py`
- `ab_ecommerce_storefront/tests/check_checkout_races.py`
- `ab_ecommerce_storefront/changelog.d/2026-10-19-cart-holds-and-idempotency.md`

## E-Plus operating limit

These are website-only holds. PostgreSQL cannot prevent an E-Plus branch cashier from selling the same physical stock. No supported pre-invoice E-Plus reservation interface was available in the inspected integration. The existing invoice-push flow is not used as a temporary reservation.

Consequently, `_ab_require_authoritative_reservation` rejects checkout and confirmation of E-Plus-linked products. This is an intentional incomplete-integration gate, not a successful physical reservation. Enabling this change on the primary storefront while that gate remains in place blocks those checkouts.

Completing the shared-stock guarantee requires a supported E-Plus operation that atomically reserves every line against the authoritative source, reduces cashier-available quantities, and returns a durable reservation identifier. It must support the same idempotency key on retry, lookup by key after an uncertain timeout, expiry/release, and conversion to a firm order without double deduction. Source branch, batch and unit conversion must remain explicit even when fulfillment may use any authorized branch. Consolidated snapshots and `NOLOCK` reads cannot establish that guarantee. No E-Plus reservation, release or cross-system reconciliation is implemented or claimed here.

## Validation

- Targeted module upgrade passed on isolated, neutralized database `ecom19_cart_hold_20261018`, with ports 5669/5672 and workers/cron disabled. POT export and targeted translation merges completed; both Arabic catalogs pass `msgfmt --check-format`, and the cart notice differs between `en_US` and `ar_001` at runtime.
- The combined run passed 33 test methods with zero failures/errors: 19 reservation/submission tests, 13 inventory regression tests, and one browser test exercising active and expired countdowns. The later catalog fallback/expiry regression passed separately, bringing coverage to 34 passing test methods across these runs. Logs: `/tmp/ab-cart-hold-validation/verified-tests.log` and `/tmp/ab-cart-hold-validation/catalog-hold-tests.log`.
- The inventory regression fixture bypasses the unimplemented E-Plus gate to test native Odoo stock behavior. A separate reservation test verifies that actual E-Plus-linked checkout and confirmation are blocked. These tests do not establish external reservation support.
- Independent PostgreSQL cursor/thread tests established competing Repeatable Read snapshots: two carts allocated the last unit only once without changing physical quantity; simultaneous retries returned one prescription and quotation, with no orphan duplicate quotation. Expected serialization failures were retried by Odoo. Script: `tests/check_checkout_races.py`; database log: `/tmp/ab-cart-hold-validation/races.log`.
- Python/XML parsing, JavaScript syntax checks and `git diff --check` passed. Tests are development-only and must be excluded from production packaging.
- The primary `ecom19` database and its running process were not upgraded or restarted. No external database operations, deployment or Git commit were performed. Fresh installation of the entire dependency chain, sustained load testing and live E-Plus end-to-end validation remain unverified.

## Design references

- [commercetools: reserve stock on a cart](https://docs.commercetools.com/guides/reserve-stock-on-cart): expiring cart reservations. Fifteen minutes is this project's initial policy recommendation, not a universal duration prescribed by the source.
- [Stripe: idempotent requests](https://docs.stripe.com/api/idempotent_requests): key reuse and parameter consistency.
- [PostgreSQL: transaction isolation](https://www.postgresql.org/docs/16/transaction-iso.html): Repeatable Read conflicts require retrying the complete transaction.
