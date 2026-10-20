Commit: 34daa20b0ab166e8b2093c2859ba721287433b64
Author: hager yasser <hageryasser2002@gmail.com>
Date: 2026-09-23T10:45:00+03:00
Subject: ab_sales_printing/feat(#2289): add sales printing bridge module

User-facing changes:
- Introduce the sales printing bridge on pos19.

Files changed:
- ab_sales_printing/__init__.py
- ab_sales_printing/__manifest__.py
- ab_sales_printing/changelog.d/2026-09-23-sales-printing-bridge.md
- ab_sales_printing/i18n/ar.po
- ab_sales_printing/i18n/ar_001.po
- ab_sales_printing/models/__init__.py
- ab_sales_printing/models/ab_sales_ui_api.py
- ab_sales_printing/static/src/bill_wizard/bill_wizard_action.js
- ab_sales_printing/static/src/bill_wizard/cups_print_dialog.js
- ab_sales_printing/static/src/bill_wizard/cups_print_dialog.xml

Current changes before commit:
- Port the optional sales receipt printing bridge from pos19.
- Use authorized local sales/return data for preview and printing and maintain both Arabic catalogs.

Files changed:
- ab_sales_printing/__init__.py
- ab_sales_printing/__manifest__.py
- ab_sales_printing/changelog.d/2026-10-20-callcenter-parity.md
- ab_sales_printing/i18n/ar.po
- ab_sales_printing/i18n/ar_001.po
- ab_sales_printing/models/__init__.py
- ab_sales_printing/models/ab_sales_ui_api.py
- ab_sales_printing/static/src/bill_wizard/bill_wizard_action.js
- ab_sales_printing/static/src/bill_wizard/cups_print_dialog.js
- ab_sales_printing/static/src/bill_wizard/cups_print_dialog.xml
