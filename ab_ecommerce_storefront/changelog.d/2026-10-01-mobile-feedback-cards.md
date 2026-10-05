# Mobile feedback card visibility

## Recent relevant commit

Commit: `0296141`
Author: Mohamed Fawzy
Date: 2026-09-27
Original subject: `ab_ecommerce_storefront/ux: refine storefront product and portal experience`

User-facing changes:

- Refine social feedback cards with platform badges, screenshot panels, and a horizontally scrolling mobile layout.

Files changed:

- `ab_ecommerce_storefront/static/src/scss/storefront.scss`

## Current changes before commit:

- At widths of 444px and below, size feedback cards to 82% of the available rail width, capped at 300px, so the next card remains visible.
- Tighten card padding and source-label spacing, allowing the comment label to wrap on narrow phones.
- Preserve direction-aware horizontal scrolling and scroll snapping.
- No user-facing strings changed; existing English and Arabic translations remain applicable.

Files changed:

- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/changelog.d/current.md`
- `ab_ecommerce_storefront/changelog.d/2026-10-01-mobile-feedback-cards.md`

Validation:

- SCSS compilation and `git diff --check` passed.
- Arabic and English browser checks passed at 320, 360, 375, 390, 414, and 444px, with 55–117px of the next card visible and the first card fully visible.
- Horizontal scrolling brings the next card fully into view without page overflow; 445px and 576px retain their existing layouts.
- Final 320px checks passed in both directions with the source label fully visible; visually inspected the Arabic card preview.
