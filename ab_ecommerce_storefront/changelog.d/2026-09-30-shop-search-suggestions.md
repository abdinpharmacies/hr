# Product search suggestions

## Recent relevant commit

Commit: `94abdb9`
Author: Mohamed Fawzy
Date: 2026-09-29
Original subject: `ab_ecommerce_storefront/fix: align account password mask in RTL layout`

User-facing changes:

- Align the account password mask with the RTL layout.

Files changed:

- `ab_ecommerce_storefront/static/src/scss/storefront.scss`

## Current changes before commit:

- Open product-page search suggestions below the search field with matching width and direction-aware alignment.
- Limit the suggestions to available viewport space and scroll long result lists internally.
- Recalculate available space on scrolling, resizing, and visual viewport changes.
- Preserve existing search behavior outside the product grid and retain keyboard navigation, Escape, and clearing.
- Add rounded result highlights and a shadow to separate suggestions from product cards.
- No user-facing strings changed; the existing English and both Arabic translations remain applicable.

Files changed:

- `ab_ecommerce_storefront/static/src/js/search_autocomplete_clear.js`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/changelog.d/current.md`
- `ab_ecommerce_storefront/changelog.d/2026-09-30-shop-search-suggestions.md`

Validation:

- JavaScript syntax, SCSS compilation, and `git diff --check` passed.
- Arabic and English browser checks passed at 1024, 1280, and 1440px: downward placement, field-width alignment, viewport bounds, internal scrolling, keyboard selection, Escape, and clearing.
- Visually inspected the rendered Arabic suggestions below the product search field.
