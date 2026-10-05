# Responsive header layout and scroll behavior

## Recent relevant commit

Commit: `94abdb9`
Author: Mohamed Fawzy
Date: 2026-09-29
Original subject: `ab_ecommerce_storefront/fix: align account password mask in RTL layout`

User-facing changes:

- Align the account password mask with the RTL layout.

Files changed:

- `ab_ecommerce_storefront/static/src/scss/storefront.scss`

Commit: `d4d5023`
Author: Mohamed Fawzy
Date: 2026-09-13
Original subject: `ab_ecommerce_storefront/fix: stabilize storefront product and sticky interactions`

User-facing changes:

- Stabilize storefront product controls and sticky navigation interactions.

Files changed:

- `ab_ecommerce_storefront/static/src/js/sticky_shop_nav.js`

## Current changes before commit:

- Place the logo on the left and account, wishlist, cart, and navigation controls on the right in the English header below 992px.
- Let the header grid follow the page direction so Arabic keeps the logo on the right and controls on the left.
- Use an account icon with the existing accessible label and tooltip below 576px, and allow the logo container to shrink on narrow phones.
- Move the same header, search field, and controls continuously between their measured positions over 280ms, with gentle acceleration and deceleration and no fade-out followed by a replacement header.
- Center the sticky header using equal side offsets and scrollbar-aware width, avoiding horizontal translation differences between Arabic and English.
- Keep the full normal-header height reserved while scrolling so page content stays in place; prevent repeated scroll events from restarting the return.
- Cancel and continue from the current animated positions when scrolling reverses, and respect reduced-motion preferences.
- Reduce mobile navigation padding and row spacing, bringing the delivery row closer to the menu.

Files changed:

- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/static/src/js/sticky_shop_nav.js`
- `ab_ecommerce_storefront/changelog.d/2026-09-30-header-direction.md`

Validation:

- SCSS compilation and `git diff --check` passed.
- The rendered English and Arabic headers passed alignment and overflow checks at 320, 375, 575, 576, 767, 991, and 992px.
- Frame checks passed at 375px and 991px in English and Arabic: continuous visibility and resizing, centered position, reserved header space, stationary page content, and rapid scroll reversals.
- JavaScript syntax, SCSS compilation, and `git diff --check` passed.
- At 375px, reduce the header from about 257px to 210px and the gap below the delivery row from about 20px to 5px.
