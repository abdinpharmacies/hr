Commit: b4ffe24e4c92c092e91a8788a08a2ab155762249
Author: Alhassan Hossny <alhassan.hossny@gmail.com>
Date: 2026-08-26T16:05:03+03:00
Subject: ab_employee_access_sales/fix: omit local POS HR relations from remote branch submits

User-facing changes:
- Exclude local employee-session relations from remote branch submissions.

Files changed:
- ab_employee_access_sales/changelog.d/2026-08-26-callcenter-pos-hr-metadata.md
- ab_employee_access_sales/models/ab_sales_pos_api.py

Current changes before commit:
- Remove the cashier dependency and its model import so employee PIN access installs without E-Plus.
- Keep existing POS employee sessions, roles, shifts and audit behavior.
- Add both Arabic catalogs for the dedicated callcenter installation.

Files changed:
- ab_employee_access_sales/__manifest__.py
- ab_employee_access_sales/changelog.d/2026-10-20-callcenter-parity.md
- ab_employee_access_sales/i18n/ar.po
- ab_employee_access_sales/i18n/ar_001.po
- ab_employee_access_sales/models/__init__.py
- ab_employee_access_sales/models/ab_sales_cashier_api_inherit.py
