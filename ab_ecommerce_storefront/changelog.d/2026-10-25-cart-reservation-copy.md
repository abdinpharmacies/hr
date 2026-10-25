# Cart reservation messaging

## Current changes before commit:

- Explain the temporary cart reservation and invite customers to complete their order.
- Show minutes and seconds in a clock badge, adding hours only when needed.
- Explain expiry and the subsequent availability check in English and both Arabic catalogs.
- Keep the ticking timer out of live announcements and announce expiry separately.

Files changed:

- `ab_ecommerce_storefront/views/cart_hold.xml`
- `ab_ecommerce_storefront/static/src/js/cart_hold.js`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/tests/test_checkout_reservation.py`
- `ab_ecommerce_storefront/changelog.d/2026-10-25-cart-reservation-copy.md`

## Relevant prior commit

Commit: `220c7a0bca25264f5d680af7233b00635de94ad2`
Author: Mohamed Fawzy
Date: 2026-10-22
Original subject: `ab_ecommerce_storefront/IMP: clarify cart hold countdown`

- Added the earlier reservation notice and hours/minutes/seconds display.

Relevant files changed:

- `ab_ecommerce_storefront/views/cart_hold.xml`
- `ab_ecommerce_storefront/static/src/js/cart_hold.js`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
