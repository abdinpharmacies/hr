Commit: dc41274f6bbb7648052f3325abb13935363a5d12
Author: Hossam Elsheikh <hossam.m.elsheikh@gmail.com>
Date: 2026-10-13T14:10:12+03:00
Subject: ab_sales/disable editing bill after sending

User-facing changes:
- Keep submitted callcenter bills immutable, including failed submissions.

Files changed:
- ab_sales/changelog.d/2026-10-13-immutable-failed-bills.md
- ab_sales/models/local_bills.py
- ab_sales/static/src/pos/pos_action.js
- ab_sales/views/local_bill_views.xml

Current changes before commit:
- Add per-draft revisions, employee isolation, capacity admission and protected submission recovery.
- Port product and bill search filters, stock freshness and stale-response protection through the branch API.
- Add append-only branch-scoped bill annotations while retaining immutable retries and rejected bills.
- Document clean-install rollout and verification; maintain both Arabic catalogs.

Files changed:
- ab_sales/BRANCH_API_WORKFLOW.md
- ab_sales/__manifest__.py
- ab_sales/changelog.d/2026-10-20-callcenter-parity.md
- ab_sales/doc/CALLCENTER_PARITY_2026_10_20.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/__init__.py
- ab_sales/models/ab_sales_header.py
- ab_sales/models/ab_sales_pos_api.py
- ab_sales/models/ab_sales_pos_draft_cache.py
- ab_sales/models/ab_sales_pos_draft_slots.py
- ab_sales/models/ab_sales_ui_api.py
- ab_sales/models/ab_sales_ui_api_bill_wizard_inherit.py
- ab_sales/models/bill_annotations.py
- ab_sales/models/branch_bills.py
- ab_sales/models/branch_services.py
- ab_sales/security/annotation_rules.xml
- ab_sales/security/ir.model.access.csv
- ab_sales/static/src/add_products/add_products_action.js
- ab_sales/static/src/add_products/add_products_action.xml
- ab_sales/static/src/add_products/product_card.xml
- ab_sales/static/src/bill_wizard/bill_wizard_action.js
- ab_sales/static/src/bill_wizard/bill_wizard_action.scss
- ab_sales/static/src/bill_wizard/bill_wizard_action.xml
- ab_sales/static/src/pos/pos_action.js
- ab_sales/static/src/pos/pos_action.scss
- ab_sales/static/src/pos/pos_action.xml
- ab_sales/static/src/pos/pos_action_sales_line_balance.xml
- ab_sales/static/src/pos/pos_balance_refresh.js
- ab_sales/static/src/pos/pos_search_product_card.xml
- ab_sales/static/src/pos/zz_pos_unavailable_reason.xml
- ab_sales/static/src/pos/zz_pos_unavailable_reason_patch.js
- ab_sales/static/src/pos/zz_product_search_arabic_keymap_patch.js
- ab_sales/views/ab_product_inherit.xml
