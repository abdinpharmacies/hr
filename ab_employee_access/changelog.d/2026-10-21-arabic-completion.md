Commit: 5b77b1271d89e56fa896b683a6f7760305235cbd
Author: Hossam Elsheikh <hossam.m.elsheikh@gmail.com>
Date: 2026-10-21T12:32:29+03:00
Subject: ab_employee_access/refactor: remove cashier permissions

User-facing changes:
- Remove cashier-specific permissions from employee access profiles.

Files changed:
- ab_employee_access/__manifest__.py
- ab_employee_access/changelog.d/2026-10-21-remove-callcenter-cashier.md
- ab_employee_access/models/ab_employee_access.py
- ab_employee_access/models/ab_employee_access_sales_role.py
- ab_employee_access/views/ab_employee_access.xml
- ab_employee_access/views/ab_employee_access_sales_role_views.xml

Current changes before commit:
- Complete missing Arabic labels and messages using Odoo-exported terms; preserve existing translations and keep ar/ar_001 coverage aligned.

Files changed:
- ab_employee_access/__manifest__.py
- ab_employee_access/changelog.d/2026-10-21-arabic-completion.md
- ab_employee_access/i18n/ar.po
- ab_employee_access/i18n/ar_001.po
