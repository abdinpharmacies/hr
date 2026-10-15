# Remove the product page top assurance strip

## Recent relevant commit

Commit: `4e330189725c9c19be10b78b39fa277e1b7f5ce9`
Author: Mohamed Fawzy
Date: 2026-10-13
Original subject: `ab_ecommerce_storefront/IMP: simplify storefront copy in English and Arabic`

- Simplify product assurance and recommendation wording.

Files changed:

- `ab_ecommerce_storefront/views/product.xml`

## Current changes before commit:

- Remove the strip above product details containing From Abdin Pharmacies, Secure checkout, and Pharmacy help: 19036.
- Preserve the product details and lower product promises. No new or updated user-facing strings; existing Arabic catalogs remain unchanged by this task.

Files changed:

- `ab_ecommerce_storefront/views/product.xml`
- `ab_ecommerce_storefront/changelog.d/2026-10-15-remove-product-top-assurance.md`

Validation:

- XML parsing, both Arabic catalog format checks, and scoped diff whitespace checks passed.
- Targeted module upgrade passed on the isolated database `ecom19_product_ux_20261015`, with HTTP disabled and ports 5069/5072 configured. Log: `/tmp/ab-product-strip-upgrade.log`.
- Combined product views in `en_US` and `ar_001` omit the top strip and retain product details and lower promises. English and Arabic translations remain distinct.
- The `ar` language is not enabled in the test database; its catalog passed static format validation.
- Live database upgrade and browser visual verification were not performed.
