## fd23bb6eb9279731a740d93d397e293262f6bfad

- Author: emadco88 <emadco88@gmail.com>
- Date: 2026-10-01T09:19:12+03:00
- Subject: ab_sales_contract/ FIX passive module for contract

User-facing changes:

- Removed active contract operations from the reporting module.

Files changed:

- `ab_sales_contract/models/__init__.py`
- `ab_sales_contract/models/ab_contract_product_origin.py`
- `ab_sales_contract/models/ab_customer_inherit.py`
- `ab_sales_contract/models/ab_sales_header_inherit.py`
- `ab_sales_contract/models/ab_sales_header_total_invoice_discount.py`
- `ab_sales_contract/models/ab_sales_line_inherit.py`
- `ab_sales_contract/models/ab_sales_pos_api_contract.py`
- `ab_sales_contract/models/ab_sales_return_header_inherit.py`
- `ab_sales_contract/static/src/pos/pos_action_contract.scss`
- `ab_sales_contract/static/src/pos/pos_action_contract_inherit.xml`
- `ab_sales_contract/static/src/pos/pos_action_contract_patch.js`
- `ab_sales_contract/views/ab_customer_inherit.xml`
- `ab_sales_contract/views/ab_sales_contract_views.xml`

## Current changes before commit:

User-facing changes:

- Store two contract snapshot fields as open-ended keys and allow upload mapping while retaining read-only reporting views.
- Updated the module version.

Files changed:

- `ab_sales_contract/__manifest__.py`
- `ab_sales_contract/models/ab_sales_line_inherit.py`
- `ab_sales_contract/changelog.d/2026-11-02-open-source-keys.md`
