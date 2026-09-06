Recent relevant commit:

- Commit: `3db5d596c9429ff082c3fe9b0466692b945f788f`
- Author: emadco88
- Date: 2026-07-28
- Original subject: INIT commit pos19
- User-facing changes:
  - Established the previous baseline for this module before the report-server passive cleanup.
- Files changed:
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

- User-facing changes:
  - Removed `required=True` from model field declarations so report sync loads can accept incomplete branch payloads.
- Files changed:
  - ab_employee_access/changelog.d/2026-09-03-report-server-passive-cleanup.md
  - ab_employee_access/models/ab_employee_access_sales_role.py
