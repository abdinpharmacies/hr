# ab_ecommerce_storefront customer orders center

## Recent relevant commit

- `0296141` | Mohamed Fawzy | 2026-09-27 | `ab_ecommerce_storefront/ux: refine storefront product and portal experience`
  - Refined the storefront product and customer portal presentation.
  - Files changed: `static/src/scss/storefront.scss`.

## Current changes before commit

- Replace the My Orders tables with an RTL order center that distinguishes regular purchases from prescription requests, filters both types in the browser, sorts records by their existing dates, and animates the active filter indicator between tabs.
- Preserve existing references, computed status labels, detail routes, portal pagination, and the prescription workflow; add focused empty states and responsive, fully clickable order cards.
- Remove the order center supporting sentence and its unused Arabic translations.
- Keep the three order filters within a fixed responsive grid, place All first on the RTL start edge, and move the indicator by active tab without horizontal scrolling.
- Include eligible open storefront sales in the regular orders list, including draft, sent, and cancelled states, and exclude sale orders already linked to a prescription.
- Anchor the animated filter indicator to fixed right, center, and left positions so the active tab stays aligned in RTL at every viewport width.
- Display customer-facing tracking references from the prescription or its linked sale order instead of internal sequence names.
- Keep regular and prescription orders on one shared card surface, using the prescription icon tint and type label to distinguish them.
- Open the existing sale order tracking page from a prescription card when a sale order is linked, while retaining the existing prescription detail route as a fallback.
- Translate the remaining new order center labels into Arabic for both supported Arabic locales.
- Open the prescription order filter directly when customers select View all from recent prescription requests.

Files changed:

- `__manifest__.py`
- `controllers/portal.py`
- `i18n/ab_ecommerce_storefront.pot`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `static/src/js/portal_orders.js`
- `static/src/scss/storefront.scss`
- `views/prescription_order_templates.xml`
- `views/portal.xml`
