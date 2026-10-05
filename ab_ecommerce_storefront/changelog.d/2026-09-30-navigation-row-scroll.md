# Navigation row scrolling

## Recent relevant commit

Commit: `0296141`
Author: Mohamed Fawzy
Date: 2026-09-27
Original subject: `ab_ecommerce_storefront/ux: refine storefront product and portal experience`

User-facing changes:

- Refine storefront header navigation and responsive layouts.

Files changed:

- `ab_ecommerce_storefront/static/src/scss/storefront.scss`

## Current changes before commit:

- Keep the phone navigation links in a horizontally scrollable row without shrinking the buttons.
- Add mouse dragging and wheel scrolling to reach hidden navigation links in English and Arabic.
- Preserve native touch swiping and ordinary link clicks, and prevent navigation when dragging a link.

Files changed:

- `ab_ecommerce_storefront/static/src/js/sticky_shop_nav.js`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/changelog.d/2026-09-30-navigation-row-scroll.md`

Validation:

- JavaScript syntax, SCSS compilation, and `git diff --check` passed.
- Browser checks passed for English and Arabic at 320px and 375px using normal and debug assets.
- Verified mouse dragging on links, mouse-wheel scrolling, native touch swipes, no accidental navigation after dragging, and ordinary link clicks.
- No user-facing source strings changed; no translation additions are required.
