## 75d8eafec - Alhassan Hossny - 2026-10-28

Original commit subject: ab_employee_access_sales/feat: unify POS store scope and employee session enforcement

User-facing changes:
- Added employee session checks to customer lookup, validation, and creation in the callcenter POS.

Files changed:
- ab_employee_access_sales/models/ab_sales_pos_api.py
- ab_employee_access_sales/static/src/pos/ab_employee_access_sales_pos_patch.js

## Current changes before commit:

- Let customer lookup, validation, and creation use the existing callcenter customer API without an employee POS session token, as in pos19.
- Keep session enforcement for sales and other protected POS operations.

Files changed:
- ab_employee_access_sales/models/ab_sales_pos_api.py
- ab_employee_access_sales/static/src/pos/ab_employee_access_sales_pos_patch.js
- ab_employee_access_sales/changelog.d/2026-10-28-customer-without-pos-session.md
