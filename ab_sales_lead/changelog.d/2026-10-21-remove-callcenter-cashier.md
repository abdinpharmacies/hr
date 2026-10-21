Commit: 3db5d596c9429ff082c3fe9b0466692b945f788f
Author: emadco88 <emadco88@gmail.com>
Date: 2026-07-28T15:21:42+03:00
Subject: INIT commit pos19

User-facing changes:
- Introduce sales leads and the POS lead workflow.

Files changed:
- ab_sales_lead/__init__.py
- ab_sales_lead/__manifest__.py
- ab_sales_lead/models/__init__.py
- ab_sales_lead/models/ab_sales_lead.py
- ab_sales_lead/security/ir.model.access.csv
- ab_sales_lead/security/rules_sales_lead.xml
- ab_sales_lead/static/src/pos/pos_lead.scss
- ab_sales_lead/static/src/pos/pos_lead_patch.js
- ab_sales_lead/static/src/pos/pos_lead_templates.xml
- ab_sales_lead/tests/__init__.py
- ab_sales_lead/tests/test_ab_sales_lead.py
- ab_sales_lead/views/ab_sales_lead_views.xml
- ab_sales_lead/views/menus.xml

Current changes before commit:
- Rename the user grouping filter from Cashier to User.
- Add the changed label to both Arabic translation catalogs.

Files changed:
- ab_sales_lead/__manifest__.py
- ab_sales_lead/changelog.d/2026-10-21-remove-callcenter-cashier.md
- ab_sales_lead/i18n/ar.po
- ab_sales_lead/i18n/ar_001.po
- ab_sales_lead/views/ab_sales_lead_views.xml
