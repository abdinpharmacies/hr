# Remove the unconfirmed product shipping estimate

Commit: `4e330189725c9c19be10b78b39fa277e1b7f5ce9`
Author: Mohamed Fawzy
Date: 2026-10-13
Original subject: `ab_ecommerce_storefront/IMP: simplify storefront copy in English and Arabic`

- Simplify product assurance and recommendation wording.

Files changed:

- `ab_ecommerce_storefront/views/product.xml`

## Current changes before commit:

- The existing pending product template replacement removes Odoo's default “Shipping: 2-3 Business Days” estimate, including its Arabic rendering, by calling the module's policy links template.
- Verified the existing replacement without adding another override or changing its policy links.
- No new or updated user-facing strings were introduced by this task.

Files changed:

- `ab_ecommerce_storefront/views/product.xml`
- `ab_ecommerce_storefront/views/legal_templates.xml`
- `ab_ecommerce_storefront/changelog.d/2026-10-15-remove-shipping-estimate.md`

Validation:

- XML parsing and the XPath target against local Odoo 19 source passed; the replacement template contains no shipping estimate or nested template calls.
- Both Arabic catalogs passed `msgfmt --check-format`; scoped view diff whitespace checks passed.
- A targeted upgrade and runtime language/browser checks were unavailable because the local PostgreSQL socket did not respond. The running site's state was not verified.
