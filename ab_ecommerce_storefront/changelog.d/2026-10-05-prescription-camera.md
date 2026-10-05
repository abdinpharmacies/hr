# Prescription camera capture

Commit: `04fc6d38c2ebaadb1f1256276747d603fd90b7d7`
Author: Mohamed Fawzy
Date: 2026-09-29
Original subject: `ab_ecommerce_storefront/feat: reuse saved prescription delivery address`

- Reuse saved delivery addresses for prescriptions.

Files changed:

- `ab_ecommerce_storefront/controllers/prescription_order.py`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/views/prescription_order_templates.xml`

## Current changes before commit:

- Open a live camera preview and capture a JPG into the prescription upload form.
- Explain permission and device failures, support retry, and release the camera on exit.
- Include camera controls and messages in both Arabic catalogs.

Files changed:

- `ab_ecommerce_storefront/static/src/js/prescription_order.js`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`
- `ab_ecommerce_storefront/views/prescription_order_templates.xml`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/changelog.d/2026-10-05-prescription-camera.md`

Validation during commit review:

- XML, JavaScript syntax where applicable, SCSS compilation, and Arabic PO format checks passed.
- Live camera and Odoo browser flows were not rerun during this Git organization task.
