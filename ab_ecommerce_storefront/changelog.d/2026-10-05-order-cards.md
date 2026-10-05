# Customer order card alignment

Commit: `a4310ef2f4b73f7dc5b81d6a5c90d1a2c97c9975`
Author: Mohamed Fawzy
Date: 2026-09-29
Original subject: `ab_ecommerce_storefront/ux: add customer orders center`

- Add the customer orders center.

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

## Current changes before commit:

- Align regular and prescription order status badges and reserve equal action-button space.
- Use View progress for both order types while preserving existing destinations.
- Preserve the previous translation entries and add the new action in both Arabic catalogs.

Files changed:

- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/views/portal.xml`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/changelog.d/2026-10-05-order-cards.md`

Validation during commit review:

- XML, JavaScript syntax where applicable, SCSS compilation, and Arabic PO format checks passed.
- Live camera and Odoo browser flows were not rerun during this Git organization task.
