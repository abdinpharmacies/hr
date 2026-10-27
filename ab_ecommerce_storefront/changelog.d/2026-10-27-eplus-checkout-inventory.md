# Eplus synced inventory at checkout

## Current changes before commit:

- Allow Eplus-linked products through checkout when the latest executed Eplus Inventory Sync for the order warehouse completed and included those products.
- Cap checkout availability by both the Eplus snapshot and Odoo free stock, then subtract other active cart holds before creating a payment transaction.
- Reserve the synced Odoo stock through normal sale confirmation and keep checkout blocked when sync is missing, failed, or for another warehouse.
- Confirm a validated cash-on-delivery checkout before showing an order-confirmed status; keep the payment pending until collection on delivery.
- Show a clear unconfirmed state if checkout stock or transaction validation fails, and let the customer start a new payment attempt.
- Return a failed payment status from Odoo's checkout poll when cash-on-delivery confirmation fails, so the customer reaches the unconfirmed page.
- Stop an Eplus inventory resync from restoring quantities already delivered by the website, including a sync job that is still running.
- Add English and Arabic status and sync-safety messages in both Arabic catalogs.
- Validate completed-sync checkout, competing carts, failed sync, warehouse isolation, cash-on-delivery confirmation, and native stock reservation.

Validation: Targeted upgrade on `ecom19_cart_hold_20261018` passed 42 reservation and stock availability tests with zero failures or errors. Two focused COD tests passed after the row-lock change, and the focused sync-guard test passed with exact warehouse and error assertions. Both Arabic catalogs passed `msgfmt --check-format`. A scoped seven-term Arabic import on the isolated development database confirmed English and Arabic payment status text at runtime. A read-only check of local order 151 showed that its cash-on-delivery transaction remained pending while the sale order remained draft with no picking. No external Eplus sale or stock write was made.

Files changed:

- `ab_ecommerce_storefront/models/cart_hold.py`
- `ab_ecommerce_storefront/models/payment_transaction.py`
- `ab_ecommerce_storefront/models/eplus_sync_guard.py`
- `ab_ecommerce_storefront/models/__init__.py`
- `ab_ecommerce_storefront/controllers/payment_status.py`
- `ab_ecommerce_storefront/controllers/__init__.py`
- `ab_ecommerce_storefront/tests/test_checkout_reservation.py`
- `ab_ecommerce_storefront/tests/test_stock_availability.py`
- `ab_ecommerce_storefront/views/portal.xml`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/changelog.d/2026-10-27-eplus-checkout-inventory.md`

## Relevant prior commit

Commit: `17c191be`
Author: Mohamed Fawzy
Date: 2026-10-20
Original subject: `ab_ecommerce_storefront/IMP: reserve cart stock and deduplicate submissions`

- Added website cart holds, native stock reservation, and the original Eplus checkout guard.

Files changed:

- `ab_ecommerce_storefront/models/cart_hold.py`
- `ab_ecommerce_storefront/tests/test_checkout_reservation.py`
