# Remove the shop assurance strip

## Recent relevant commit

Commit: `4e330189725c9c19be10b78b39fa277e1b7f5ce9`
Author: Mohamed Fawzy
Date: 2026-10-13
Original subject: `ab_ecommerce_storefront/IMP: simplify storefront copy in English and Arabic`

User-facing changes:

- Simplify the shop introduction.

Files changed:

- `ab_ecommerce_storefront/views/shop.xml`

## Current changes before commit:

- Remove the genuine-products, secure-checkout, delivery, and hotline strip from product listings, including filtered and unfiltered shop pages.
- Preserve the browsing-history rail and existing translations; no new or updated user-facing strings.

Files changed:

- `ab_ecommerce_storefront/views/shop.xml`
- `ab_ecommerce_storefront/changelog.d/2026-10-13-remove-shop-assurance.md`

Validation:

- XML parsing passed.
- Live HTML for the supplied Arabic price-filter URL, its English equivalent, and the unfiltered Arabic shop renders the shop container without the assurance strip.
