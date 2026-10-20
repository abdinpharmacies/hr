Commit: 42b13eaf32fa5dafbe2e16bb9e0e266e5ba570a0
Author: Hossam Elsheikh
Date: 2026-09-17T16:33:15+03:00
Subject: ab_sales: persist callcenter bills locally and improve branch submission recovery

User-facing changes relevant to this update:
- Retain local return records and their return form workflow.

Files changed (relevant view):
- ab_sales/views/ab_sales_return.xml

Current changes before commit:
- Rename all three callcenter return action labels from Push to E-Plus to Commit.
- Update the confirmation and success/failure messages to use commit terminology.
- Add Arabic translations in both catalogs using exported Odoo references; preserve existing translation entries.
- Verify XML/JavaScript syntax, PO format, targeted installation update in the isolated database and English/Arabic return form labels.

Files changed:
- ab_sales/changelog.d/2026-10-20-commit-return-labels.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/static/src/pos/return_form_buttons.xml
- ab_sales/static/src/sales_return/ab_sales_return_ui_api.js
- ab_sales/static/src/sales_return/ab_sales_return_ui_api.xml
- ab_sales/views/ab_sales_return.xml
