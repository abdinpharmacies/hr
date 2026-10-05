# Shop search assurance strip

## Recent relevant commit

Commit: `0296141`
Author: Mohamed Fawzy
Date: 2026-09-27
Original subject: `ab_ecommerce_storefront/ux: refine storefront product and portal experience`

User-facing changes:

- Refine the shop layout, category navigation, and browsing-history rail.

Files changed:

- `ab_ecommerce_storefront/views/shop.xml`

## Current changes before commit:

- Hide the genuine-products, secure-checkout, delivery, and hotline strip on shop search results, including searches with no matching products.
- Keep the existing category-page exclusion and show the strip on the unfiltered shop page.
- No user-facing strings changed; existing English and Arabic translations remain applicable.

Files changed:

- `ab_ecommerce_storefront/views/shop.xml`
- `ab_ecommerce_storefront/changelog.d/current.md`
- `ab_ecommerce_storefront/changelog.d/2026-10-04-shop-search-assurance.md`

Validation:

- XML parsing and `git diff --check` passed.
- The supplied Arabic search URL and its English equivalent render without the strip; the unfiltered Arabic shop still renders it.
