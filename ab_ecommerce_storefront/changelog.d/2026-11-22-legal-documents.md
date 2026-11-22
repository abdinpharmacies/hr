# Storefront legal documents

## Recent relevant commit

Commit: `e2f74cc90d0d2a22758b3527c18d605452c5562a`
Author: Mohamed Fawzy
Date: 2026-10-15
Original subject: `ab_ecommerce_storefront/IMP: add draft terms page and product policy links`

- Add the original public terms page and product policy links.

Files changed:

- `ab_ecommerce_storefront/controllers/contact.py`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/static/src/scss/contact.scss`
- `ab_ecommerce_storefront/views/legal_templates.xml`

## Current changes before commit:

- Replace the public terms draft with the full general terms document supplied in Arabic.
- Show the general terms document at `/terms`, including links from the storefront footer and return policy, and redirect the old terms URL there.
- Keep the full order and delivery terms available without requiring checkout agreement.
- Point standard storefront order terms cards and sales order reports to the order and delivery document, including existing orders with saved standard terms notes.
- Keep custom order notes visible in the order details.
- Preserve every Arabic paragraph from both Word documents and add English translations for review.
- Keep the existing return-policy page unchanged.
- Make the 49-article index collapsible and readable on desktop and mobile.

Files changed:

- `ab_ecommerce_storefront/changelog.d/2026-11-22-legal-documents.md`
- `ab_ecommerce_storefront/__manifest__.py`
- `ab_ecommerce_storefront/controllers/contact.py`
- `ab_ecommerce_storefront/i18n/ab_ecommerce_storefront.pot`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/models/sale_order.py`
- `ab_ecommerce_storefront/static/src/scss/contact.scss`
- `ab_ecommerce_storefront/views/layout.xml`
- `ab_ecommerce_storefront/views/legal_templates.xml`
- `ab_ecommerce_storefront/views/portal.xml`

Validation:

- The isolated `codex_ecom_translation_20261012` database completed a targeted storefront upgrade.
- English and Arabic public and checkout terms routes returned HTTP 200.
- The Arabic pages matched all 280 general and 353 order document body paragraphs exactly.
- XML parsing, both gettext format checks, desktop and narrow-screen screenshots, and diff checks passed.
- The user approved both documents for publication on 2026-11-22.
- A targeted `ecom19` storefront upgrade passed; a separate Odoo process returned the general document at `/terms` in English and Arabic, redirected `/terms-and-conditions` to `/terms`, and returned the Arabic order and delivery document.
- A targeted `ecom19` storefront upgrade passed after the order-link change; the supplied Arabic order preview opened `/order-delivery-terms`, and both Arabic catalogs passed `msgfmt --check-format`.
- After reloading the storefront workers, the Arabic order card linked to the Arabic order and delivery document, while `/ar/terms` continued to show the general document and the footer link.
- The checkout template XML parsed, both Arabic catalogs passed `msgfmt --check-format`, and `git diff --check` passed after removing the agreement checkbox.
