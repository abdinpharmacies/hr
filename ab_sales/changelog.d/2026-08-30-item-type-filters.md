## ce0201f - emadco88 - 2026-08-03

Original commit subject: ab_sales/ UPD add only_default_sales_uom logic

User-facing changes:
- Added default-sales-UoM handling to POS product search and price display flows.
- Added coverage for POS price badge behavior with default sales UoM products.

Files changed:
- ab_sales/models/ab_sales_pos_api.py
- ab_sales/models/ab_sales_ui_api.py
- ab_sales/static/src/pos/pos_action.js
- ab_sales/static/src/pos/pos_action.xml
- ab_sales/tests/test_pos_price_badges.py
- ab_sales/views/ab_product_inherit.xml

## Current changes before commit

User-facing changes:
- Added All, Medicine, and Non-medicine filters to the Bill Wizard without changing fixed 20-record pagination.
- Added the same session-local item-type filter to the POS product search row.
- Applied item-type filtering to Bill Wizard sales/return searches, POS code/name searches, partial barcode fallback, customer recommendations, and balance-filtered product searches.
- Preserved the raw SQL product-search fast path when item type is All.
- Added Arabic translation entries for the new item-type labels.
- Added backend regression tests for item-type filtering.
- Improved the Bill Wizard filter bar wrapping so Search and Reset stay inside the header.
- Added titles to icon-only balance buttons to satisfy Odoo 19 view validation.

Files changed:
- ab_sales/changelog.d/2026-08-30-item-type-filters.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/ab_sales_ui_api.py
- ab_sales/models/ab_sales_ui_api_bill_wizard_inherit.py
- ab_sales/static/src/bill_wizard/bill_wizard_action.js
- ab_sales/static/src/bill_wizard/bill_wizard_action.scss
- ab_sales/static/src/bill_wizard/bill_wizard_action.xml
- ab_sales/static/src/pos/pos_action.js
- ab_sales/static/src/pos/pos_action.scss
- ab_sales/static/src/pos/pos_action.xml
- ab_sales/static/src/pos/zz_product_search_arabic_keymap_patch.js
- ab_sales/tests/__init__.py
- ab_sales/tests/test_item_type_filters.py
- ab_sales/views/ab_product_inherit.xml
- ab_sales/views/sales_header.xml
