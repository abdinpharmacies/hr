# Mobile navigation scrolling

## Recent relevant commit

Commit: `0296141`
Author: Mohamed Fawzy
Date: 2026-09-27
Original subject: `ab_ecommerce_storefront/ux: refine storefront product and portal experience`

User-facing changes:

- Refine storefront product pages, header navigation, and portal layouts.

Files changed:

- `ab_ecommerce_storefront/views/layout.xml`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`

## Current changes before commit:

- Wrap long mobile navigation labels to prevent horizontal scrolling and clipped category icons.
- Preserve navigation row and icon sizes while scrolling vertically inside the menu.
- Contain vertical scrolling within the menu when reaching its top or bottom.

Files changed:

- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/changelog.d/2026-09-30-mobile-navigation-scroll.md`

Validation:

- SCSS compilation, `git diff --check`, and Arabic PO format validation passed.
- All 20 browser cases passed in English and Arabic at widths of 320, 375, 768, and 991px, including a 420px-high viewport and the sticky header.
- Verified no horizontal overflow, fixed menu header, reachable final links, contained wheel scrolling, and normal page scrolling after closing.
- No user-facing source strings changed; both existing Arabic translations remain valid.
