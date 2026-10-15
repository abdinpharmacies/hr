# Product image hover magnification and viewer closing

Commit: `68f7d9ae1cb69fd7ce10436f2cef5614bd90ef29`
Author: Mohamed Fawzy
Date: 2026-10-13
Original subject: `ab_ecommerce_storefront/IMP: add brand deal and availability filters`

- Added the product-page selector to storefront interaction detection.

Files changed:

- `ab_ecommerce_storefront/static/src/js/product_image_zoom.js`

## Current changes before commit:

- Preserve the original circular hover lens, pointer tracking, hover animations, click-to-open viewer, and product-page layout.
- Reduce the maximum hover magnification from 3.8x to 2x, lowering it further when the actual image dimensions cannot support that enlargement.
- Keep the lens visible while loading and on high-density displays; do not suppress it using a device-pixel-ratio eligibility threshold.
- Use the existing preview immediately, then switch to the higher-resolution source after loading and measuring it. Retain the preview if the larger image fails and ignore stale results after leaving or changing images.
- Close the enlarged viewer with a 220 ms transform-based return from its current rendered position, replacing the 980 ms wait and simultaneous width/height/position transitions. Fade the backdrop in sync, cancel panning, handle repeated closes, and clean up on animation completion with a 260 ms fallback.
- Close immediately for reduced-motion preferences and prevent late opening/loading callbacks from disturbing the exit.
- Restore the original interaction selector so the hover behavior does not depend on newly upgraded template classes.
- Withdraw the previous broader viewer/layout/typography changes and their newly added translation entries, preserving all changes that predated this task.

Files changed:

- `ab_ecommerce_storefront/static/src/js/product_image_zoom.js`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/changelog.d/2026-10-15-product-page-image-ux.md`

Validation:

- 12 hover regression tests and 8 close-animation tests passed. Closing coverage includes return geometry, animation completion, panning cancellation, repeated clicks, immediate cleanup, reduced motion, unavailable source geometry, and fallback cleanup.
- JavaScript syntax, Odoo JavaScript transpilation, complete storefront SCSS compilation, and `git diff --check` passed.
- No user-facing strings were added or changed. Both Arabic catalogs retain the pre-task translations.
- The preceding hover correction passed targeted `-u ab_ecommerce_storefront` on the neutralized database `ecom19_product_ux_20261015`, using ports 5069/5072 and its isolated filestore. The subsequent close-animation adjustment changes only JS/SCSS and was validated by the focused tests and compilation checks above.
- Current tests and output: `/tmp/ab-product-ux-validation/hover-regression.test.mjs`, `hover-regression.log`, `close-motion.test.mjs`, and `close-motion.log`. Earlier full-viewer/layout preservation assertions are superseded by the explicitly requested close-animation change.
- Browser visual verification remains unavailable. The running `ecom19` database and service were not upgraded or restarted.
