# Product hover zoom alignment

Current changes before commit:
- Keep the magnified image point aligned with the pointer at image edges instead of shifting the background inward.
- Position the lens relative to its containing element, accounting for image offset, container borders, and scrolling.
- Render signed background coordinates correctly when hovering near the top or left edge.
- No user-facing strings changed.

Validation:
- JavaScript syntax and `git diff --check` passed.
- Five Node checks using the actual update method passed for edge/center alignment and an offset container.
- Live browser verification has not been performed.

Files changed:
- `static/src/js/product_image_zoom.js`
- `changelog.d/2026-10-19-product-zoom-alignment.md`

Relevant commit:
- Commit: `00067567cce6ef5eb912ed7c95e342f30cbe2f15`
- Author: Mohamed Fawzy
- Date: 2026-10-15
- Original subject: `ab_ecommerce_storefront/FIX: smooth product image viewer closing`
- Improved product image viewer closing behavior.
- Files changed (relevant): `static/src/js/product_image_zoom.js`
