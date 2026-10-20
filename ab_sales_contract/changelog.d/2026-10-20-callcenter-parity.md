Commit: 6de2acfe823015fc7902ac57be2df6e9b20e7ba3
Author: Alhassan Hossny <alhassan.hossny@gmail.com>
Date: 2026-08-26T15:47:00+03:00
Subject: ab_sales_contract/fix: support E-Plus header reuse flag in contract overrides

User-facing changes:
- Support reused branch headers in contract handling.

Files changed:
- ab_sales_contract/changelog.d/2026-08-26-eplus-header-reuse-compatibility.md
- ab_sales_contract/models/ab_sales_header_inherit.py
- ab_sales_contract/models/ab_sales_header_total_invoice_discount.py

Current changes before commit:
- Port customer eligibility, promotion selection, contract columns and payer/discount validation.
- Keep attempted and rejected callcenter invoices immutable and maintain both Arabic catalogs.

Files changed:
- ab_sales_contract/__manifest__.py
- ab_sales_contract/changelog.d/2026-10-20-callcenter-parity.md
- ab_sales_contract/i18n/ar.po
- ab_sales_contract/i18n/ar_001.po
- ab_sales_contract/models/__init__.py
- ab_sales_contract/models/ab_contract.py
- ab_sales_contract/models/ab_contract_product_origin.py
- ab_sales_contract/models/ab_sales_header_inherit.py
- ab_sales_contract/models/ab_sales_line_inherit.py
- ab_sales_contract/models/ab_sales_pos_api_contract.py
- ab_sales_contract/models/ab_sales_return_header_inherit.py
- ab_sales_contract/models/ab_sales_ui_api_contract.py
- ab_sales_contract/static/src/pos/pos_action_contract_inherit.xml
- ab_sales_contract/static/src/pos/pos_action_contract_patch.js
- ab_sales_contract/views/ab_sales_contract_views.xml
