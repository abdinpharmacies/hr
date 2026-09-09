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

## e455a15 - hager yasser - 2026-08-30

Original commit subject: ab_sales/FEAT(#2418): Add doctor and item-type filters

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

## 0a157d1 - hager yasser - 2026-09-08

Original commit subject: ab_sales/FEAT(#19590): Fix Contract Bill Gross Total(part2)

User-facing changes:
- Calculate base bill Total Price from quantity times sell price, independently of discounted line net amounts.
- Refresh totals when line sell prices or net amounts change.
- Preserve the existing Net Amount and product-count calculations.

Files changed:
- ab_sales/models/ab_sales_header.py
- ab_sales/changelog.d/2026-08-30-item-type-filters.md

## Current changes before commit:

User-facing changes:
- Show the actual invoice salesperson and invoice type on a separate row below the branch in Bill Wizard details.
- Prioritize Contract, then Promo, then Delivery; leave ordinary cash invoices unlabelled.
- Translate the new labels in both Arabic catalogs, including Delivery as توصيل.
- Add focused payload, contract relation/name, promotion, translation, and Bills-column regression coverage.

Validation:
- All six focused invoice-info tests passed after module loading, with no skips or errors.
- Targeted Sales/Contracts upgrade, compilation, Arabic PO format checks, and whitespace checks passed.
- Source audit confirms that existing payload values, search/loading methods, JavaScript, and dependencies are unchanged.
- Full module run still reports 4 failures and 32 errors in existing replication/return tests.

Files changed:
- ab_sales/changelog.d/2026-08-30-item-type-filters.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/ab_sales_ui_api_bill_wizard_inherit.py
- ab_sales/static/src/bill_wizard/bill_wizard_action.xml
- ab_sales/tests/test_bill_wizard_product_filter.py
