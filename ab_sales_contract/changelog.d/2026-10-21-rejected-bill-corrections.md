Commit: bbe8aec544b5ff1880957cb9c6aa2d83d9ae65c4
Author: Hossam Elsheikh <hossam.m.elsheikh@gmail.com>
Date: 2026-10-20T15:33:06+03:00
Subject: ab_sales_contract/feat: port contract promotion eligibility and payer validation to callcenter

User-facing changes:
- Port contract promotion eligibility and payer validation to callcenter.

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

Current changes before commit:
- Carry promotion quantity errors through contract pricing previews and allow quantity/promotion corrections on rejected contract bills.
- Keep contract identity and invoice discount fixed during correction; ignore stale pricing callbacks during submission.

Files changed:
- ab_sales_contract/__manifest__.py
- ab_sales_contract/changelog.d/2026-10-21-rejected-bill-corrections.md
- ab_sales_contract/static/src/pos/pos_action_contract_patch.js
