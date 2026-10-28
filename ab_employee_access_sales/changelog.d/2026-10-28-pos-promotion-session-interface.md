Commit: 75d8eafec34564b77eb9ccfd339da2bfb275829e
Author: Alhassan Hossny
Date: 2026-10-28T13:13:49+03:00
Subject: ab_employee_access_sales/feat: unify POS store scope and employee session enforcement

User-facing changes:
- Require an active employee session for POS operations and limit store access.

Files changed:
- ab_employee_access_sales/__manifest__.py
- ab_employee_access_sales/changelog.d/2026-10-28-unified-pos-store-permissions.md
- ab_employee_access_sales/i18n/ar.po
- ab_employee_access_sales/i18n/ar_001.po
- ab_employee_access_sales/models/__init__.py
- ab_employee_access_sales/models/ab_employee_access_sales_pos_api.py
- ab_employee_access_sales/models/ab_employee_access_sales_pos_session.py
- ab_employee_access_sales/models/ab_sales_header.py
- ab_employee_access_sales/models/ab_sales_pos_api.py
- ab_employee_access_sales/models/ab_sales_return_ui_api_inherit.py
- ab_employee_access_sales/models/ab_sales_ui_api.py
- ab_employee_access_sales/static/src/pos/ab_employee_access_sales_pos_patch.js
- ab_employee_access_sales/tests/test_ab_employee_access_sales_api.py

Current changes before commit:
- Forward customer and contract promotion inputs through the employee-session POS wrapper.

Files changed:
- ab_employee_access_sales/changelog.d/2026-10-28-pos-promotion-session-interface.md
- ab_employee_access_sales/models/ab_sales_pos_api.py
