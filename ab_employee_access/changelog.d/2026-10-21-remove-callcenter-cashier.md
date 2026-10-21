Commit: 3db5d596c9429ff082c3fe9b0466692b945f788f
Author: emadco88 <emadco88@gmail.com>
Date: 2026-07-28T15:21:42+03:00
Subject: INIT commit pos19

User-facing changes:
- Introduce employee PIN profiles, POS screen permissions and sales roles.

Files changed:
- ab_employee_access/__init__.py
- ab_employee_access/__manifest__.py
- ab_employee_access/models/__init__.py
- ab_employee_access/models/ab_employee_access.py
- ab_employee_access/models/ab_employee_access_sales_role.py
- ab_employee_access/security/ir.model.access.csv
- ab_employee_access/static/src/login/employee_login.js
- ab_employee_access/static/src/login/employee_login.scss
- ab_employee_access/static/src/login/employee_login.xml
- ab_employee_access/views/ab_employee_access.xml
- ab_employee_access/views/ab_employee_access_sales_role_views.xml

Current changes before commit:
- Remove cashier screen permissions from employee profiles, role defaults and configuration views.
- Preserve PIN validation, POS/return permissions, store restrictions and manager approval settings.

Files changed:
- ab_employee_access/__manifest__.py
- ab_employee_access/changelog.d/2026-10-21-remove-callcenter-cashier.md
- ab_employee_access/models/ab_employee_access.py
- ab_employee_access/models/ab_employee_access_sales_role.py
- ab_employee_access/views/ab_employee_access.xml
- ab_employee_access/views/ab_employee_access_sales_role_views.xml
