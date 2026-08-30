## 3db5d59 - emadco88 - 2026-07-28

Original commit subject: INIT commit pos19

User-facing changes:
- Added contract configuration and contract-aware POS sales behavior.
- Added contract totals including total after discount, customer payment, and company payment.
- Added contract return handling and related validation coverage.

Files changed:
- ab_sales_contract/__init__.py
- ab_sales_contract/__manifest__.py
- ab_sales_contract/i18n/ar_001.po
- ab_sales_contract/models/__init__.py
- ab_sales_contract/models/ab_contract.py
- ab_sales_contract/models/ab_contract_product_origin.py
- ab_sales_contract/models/ab_customer_inherit.py
- ab_sales_contract/models/ab_sales_header_inherit.py
- ab_sales_contract/models/ab_sales_header_total_invoice_discount.py
- ab_sales_contract/models/ab_sales_line_inherit.py
- ab_sales_contract/models/ab_sales_pos_api_contract.py
- ab_sales_contract/models/ab_sales_return_header_inherit.py
- ab_sales_contract/security/ir.model.access.csv
- ab_sales_contract/static/src/pos/pos_action_contract.scss
- ab_sales_contract/static/src/pos/pos_action_contract_inherit.xml
- ab_sales_contract/static/src/pos/pos_action_contract_patch.js
- ab_sales_contract/tests/__init__.py
- ab_sales_contract/tests/test_ab_sales_contract_store_restriction.py
- ab_sales_contract/tests/test_ab_sales_return_contract.py
- ab_sales_contract/views/ab_customer_inherit.xml
- ab_sales_contract/views/ab_sales_contract_views.xml

## Current changes before commit

User-facing changes:
- Added the existing Total After Discount field as a visible column in the Sales > Bills list.
- Placed the column after Total Price and before Total Net Amount.
- Added the Arabic `ar` catalog entry for Total After Discount.

Files changed:
- ab_sales_contract/changelog.d/2026-08-30-total-after-discount-list-column.md
- ab_sales_contract/i18n/ar.po
- ab_sales_contract/views/ab_sales_contract_views.xml
