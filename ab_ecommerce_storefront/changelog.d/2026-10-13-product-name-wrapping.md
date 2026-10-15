# Product card name wrapping

Commit: `95fdee2da4ed2cd7c248d7961db6bc275e9c9dea`
Author: Mohamed Fawzy
Date: 2026-10-13
Original subject: `ab_ecommerce_storefront/FIX: translate dynamic storefront labels through Odoo`

- Replaced the hardcoded selected-address label in the storefront stylesheet with a translated data attribute.

Files changed:

- `ab_ecommerce_storefront/static/src/scss/storefront.scss`

## Current changes before commit:

- Remove the two-line clamp and maximum height from module-owned product card names so the complete name can wrap.
- Allow the title grid row to grow with its content and wrap long unbroken names within the card.
- Preserve the existing minimum title height and styles for prices and purchase controls.

Files changed:

- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/changelog.d/2026-10-13-product-name-wrapping.md`

Validation:

- The full storefront SCSS compiled successfully with the Odoo virtual environment's Sass compiler.
- `git diff --check` passed. No user-facing strings were added or changed, so both Arabic catalogs remain unchanged for this fix.
- Browser layout verification was unavailable because the browser tool reported no enabled browser surfaces.
- No database upgrade or service restart was performed for this stylesheet change.
