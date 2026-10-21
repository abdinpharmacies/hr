Commit: 8989e09279b0cc23a0acf57c2843d9446503ffbe
Author: Hossam Elsheikh <hossam.m.elsheikh@gmail.com>
Date: 2026-10-21T12:32:51+03:00
Subject: ab_employee_access_sales/refactor: remove cashier assets and payload

User-facing changes:
- Remove cashier assets and employee-session payload fields.

Files changed:
- ab_employee_access_sales/__manifest__.py
- ab_employee_access_sales/changelog.d/2026-10-21-remove-callcenter-cashier.md
- ab_employee_access_sales/models/ab_employee_access_sales_role.py
- ab_employee_access_sales/static/src/cashier/ab_employee_access_sales_cashier.scss
- ab_employee_access_sales/static/src/cashier/ab_employee_access_sales_cashier_patch.js
- ab_employee_access_sales/static/src/cashier/ab_employee_access_sales_cashier_templates.xml

Current changes before commit:
- Complete missing Arabic labels and messages using Odoo-exported terms; preserve existing translations and keep ar/ar_001 coverage aligned.
- Translate dynamic screen labels, component properties and notifications at runtime, including interpolated values where applicable.

Files changed:
- ab_employee_access_sales/__manifest__.py
- ab_employee_access_sales/changelog.d/2026-10-21-arabic-completion.md
- ab_employee_access_sales/i18n/ar.po
- ab_employee_access_sales/i18n/ar_001.po
- ab_employee_access_sales/static/src/pos/ab_employee_access_sales_pos_patch.js
- ab_employee_access_sales/static/src/pos/ab_employee_access_sales_pos_templates.xml
- ab_employee_access_sales/static/src/sales_return/ab_employee_access_sales_return_patch.js
- ab_employee_access_sales/static/src/sales_return/ab_employee_access_sales_return_templates.xml
