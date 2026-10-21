Commit: c582ac4987c491bac8ca9dd0ea96e80ffc6cdf4b
Author: Hossam Elsheikh <hossam.m.elsheikh@gmail.com>
Date: 2026-10-20T15:32:23+03:00
Subject: ab_employee_access_sales/refactor: decouple callcenter employee PIN access from branch cashier

User-facing changes:
- Decouple callcenter employee PIN access from the branch cashier addon.

Files changed:
- ab_employee_access_sales/__manifest__.py
- ab_employee_access_sales/changelog.d/2026-10-20-callcenter-parity.md
- ab_employee_access_sales/i18n/ar.po
- ab_employee_access_sales/i18n/ar_001.po
- ab_employee_access_sales/models/__init__.py
- ab_employee_access_sales/models/ab_sales_cashier_api_inherit.py

Current changes before commit:
- Remove the cashier permission from role payloads and delete unused cashier frontend assets.
- Preserve employee sessions, shifts, audit logs, PIN login and branch checks.

Files changed:
- ab_employee_access_sales/__manifest__.py
- ab_employee_access_sales/changelog.d/2026-10-21-remove-callcenter-cashier.md
- ab_employee_access_sales/models/ab_employee_access_sales_role.py
- ab_employee_access_sales/static/src/cashier/ab_employee_access_sales_cashier.scss
- ab_employee_access_sales/static/src/cashier/ab_employee_access_sales_cashier_patch.js
- ab_employee_access_sales/static/src/cashier/ab_employee_access_sales_cashier_templates.xml
