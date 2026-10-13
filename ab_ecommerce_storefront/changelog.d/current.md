# Storefront change log

## Recent commits

Commit: `deea566`
Author: Mohamed Fawzy
Date: 2026-09-29
Original subject: `ab_ecommerce_storefront/feat: retire seeded storefront products`

User-facing changes:

- Unpublish and disable sales for the 16 original seed products while retaining product records and stock data.

Files changed:

- `ab_ecommerce_storefront/__manifest__.py`
- `ab_ecommerce_storefront/data/storefront_catalog_cleanup.xml`

Commit: `94abdb9`
Author: Mohamed Fawzy
Date: 2026-09-29
Original subject: `ab_ecommerce_storefront/fix: align account password mask in RTL layout`

User-facing changes:

- Align the account password mask with the RTL layout.

Files changed:

- `ab_ecommerce_storefront/static/src/scss/storefront.scss`

Commit: `1d33b31`
Author: Mohamed Fawzy
Date: 2026-09-29
Original subject: `ab_ecommerce_storefront/feat: add return policy page`

User-facing changes:

- Add the public return-policy page and Arabic translations for its content.

Files changed:

- `ab_ecommerce_storefront/__manifest__.py`
- `ab_ecommerce_storefront/controllers/contact.py`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/static/src/scss/contact.scss`
- `ab_ecommerce_storefront/views/legal_templates.xml`

Commit: `a4310ef`
Author: Mohamed Fawzy
Date: 2026-09-29
Original subject: `ab_ecommerce_storefront/ux: add customer orders center`

User-facing changes:

- Combine regular orders and prescription requests in a filterable customer order center.

Files changed:

- `ab_ecommerce_storefront/__manifest__.py`
- `ab_ecommerce_storefront/changelog.d/2026-09-29-customer-orders-center.md`
- `ab_ecommerce_storefront/controllers/portal.py`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/static/src/js/portal_orders.js`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/views/portal.xml`
- `ab_ecommerce_storefront/views/prescription_order_templates.xml`

Commit: `04fc6d3`
Author: Mohamed Fawzy
Date: 2026-09-29
Original subject: `ab_ecommerce_storefront/feat: reuse saved prescription delivery address`

User-facing changes:

- Reuse a complete saved delivery address for signed-in prescription customers.

Files changed:

- `ab_ecommerce_storefront/controllers/prescription_order.py`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/views/prescription_order_templates.xml`

Commit: `a6f2b99`
Author: Mohamed Fawzy
Date: 2026-09-29
Original subject: `ab_ecommerce_storefront/feat: build category menu from published catalog`

User-facing changes:

- Build the header category menu from published catalog categories.

Files changed:

- `ab_ecommerce_storefront/models/website.py`

Commit: `b639838`
Author: Mohamed Fawzy
Date: 2026-09-29
Original subject: `ab_ecommerce_storefront/fix: limit purchase options to supported units`

User-facing changes:

- Limit product-card purchase options to the supported largest unit.

Files changed:

- `ab_ecommerce_storefront/models/product_template.py`


## Commits reviewed on 2026-10-05

See [the commit review](2026-10-05-commit-review.md) for commit hashes, authors, subjects, affected files, and validation. Detailed feature records remain in this folder.

## Current changes before commit:

- Keep the Shop by Category and Shop by Need buttons unchanged when the active Home link is hovered.
- Add brand, discount, coupon, current deal, and availability filters beneath shop categories on desktop and mobile.
- Limit coupon results to products targeted by active website coupon discounts, and translate the new filter labels in both Arabic catalogs.
- Batch storefront availability checks for E-Plus snapshots and warehouse stock, and map new shop labels to their view translations.
- Show discount options as checkboxes and allow shoppers to combine multiple deal filters.
- Let shoppers stage mobile shop filters and apply them together with Save at widths below 992 px.
- Open the filtered product catalog from the offers links, replace selected deal choices with a translated Clear control, and render checkmarks correctly in RTL.
- Align the Remove button at the bottom of recently viewed product cards regardless of title length.

Files changed:

- `ab_ecommerce_storefront/__manifest__.py`
- `ab_ecommerce_storefront/changelog.d/current.md`
- `ab_ecommerce_storefront/controllers/shop.py`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/models/product_template.py`
- `ab_ecommerce_storefront/models/website.py`
- `ab_ecommerce_storefront/static/src/js/shop_filter_draft.js`
- `ab_ecommerce_storefront/static/src/js/product_image_zoom.js`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/views/shop.xml`
