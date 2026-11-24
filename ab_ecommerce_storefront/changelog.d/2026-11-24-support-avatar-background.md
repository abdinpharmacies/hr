# Website Support avatar background

Commit: `e65891ea0049936d712cf9a1f530ab5f54806913`
Author: Alhassan Hossny
Date: 2026-11-23
Original commit subject: ab_ecommerce_storefront/test: preserve price integrity in reservation fixtures

- Preserve price integrity in isolated reservation fixtures.

Files changed in that commit:
- `ab_ecommerce_storefront/changelog.d/2026-11-23-two-server-qa.md`
- `ab_ecommerce_storefront/tests/test_checkout_reservation.py`

Current changes before commit:
- Make the website Support header avatar wrapper transparent so it no longer draws a solid rectangle over the header gradient.
- Preserve the existing circular image, border, sizing and chat behavior.
- Add no user-facing strings; both Arabic catalogs remain unchanged.

Files changed:
- `ab_ecommerce_storefront/static/src/scss/livechat_theme.scss`
- `ab_ecommerce_storefront/changelog.d/2026-11-24-support-avatar-background.md`
