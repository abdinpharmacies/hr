Commit: bbe8aec544b5ff1880957cb9c6aa2d83d9ae65c4
Author: Hossam Elsheikh <hossam.m.elsheikh@gmail.com>
Date: 2026-10-20T15:33:06+03:00
Subject: ab_sales_contract/feat: port contract promotion eligibility and payer validation to callcenter

User-facing changes:
- Add contract promotion eligibility and payer validation to callcenter bills.

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
- Complete missing Arabic labels and messages using Odoo-exported terms; preserve existing translations and keep ar/ar_001 coverage aligned.
- Translate dynamic screen labels, component properties and notifications at runtime, including interpolated values where applicable.
- Retain quantity and promotion correction support for rejected contract bills.

Files changed:
- ab_sales_contract/__manifest__.py
- ab_sales_contract/changelog.d/2026-10-21-arabic-completion.md
- ab_sales_contract/changelog.d/2026-10-21-rejected-bill-corrections.md
- ab_sales_contract/i18n/ar.po
- ab_sales_contract/i18n/ar_001.po
- ab_sales_contract/static/src/pos/pos_action_contract_inherit.xml
- ab_sales_contract/static/src/pos/pos_action_contract_patch.js
