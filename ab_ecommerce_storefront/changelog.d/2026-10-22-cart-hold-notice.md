# Cart hold notice

## Current changes before commit:

- Explain that cart items are temporarily reserved and when their quantities return to the storefront.
- Display the remaining hold duration as hours, minutes and seconds in both English and Arabic.
- Keep the countdown direction stable inside the Arabic cart layout.
- Validate the cart reservation regression checks for the new notice and countdown format.

Files changed:

- `ab_ecommerce_storefront/views/cart_hold.xml`
- `ab_ecommerce_storefront/static/src/js/cart_hold.js`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/changelog.d/2026-10-22-cart-hold-notice.md`

## Relevant prior commit

Commit: `17c191be813c496fda7355dfd6a37500a48e1031`
Author: Mohamed Fawzy
Date: 2026-10-20
Original subject: `ab_ecommerce_storefront/IMP: reserve cart stock and deduplicate submissions`

User-facing changes:

- Hold available storefront stock for 15 minutes and show the remaining reservation time in the cart.

Files changed:

- `ab_ecommerce_storefront/models/cart_hold.py`
- `ab_ecommerce_storefront/static/src/js/cart_hold.js`
- `ab_ecommerce_storefront/views/cart_hold.xml`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/tests/test_checkout_reservation.py`
