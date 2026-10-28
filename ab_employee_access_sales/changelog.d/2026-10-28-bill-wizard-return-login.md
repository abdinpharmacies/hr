## 75d8eafec34564b77eb9ccfd339da2bfb275829e - Alhassan Hossny - 2026-10-28

Original commit subject: ab_employee_access_sales/feat: unify POS store scope and employee session enforcement

User-facing changes:
- Unified POS store visibility and employee-session enforcement across sales and return workflows.
- Kept branch connection readiness and employee store permissions enforced server-side.

Files changed:
- ab_employee_access_sales/__manifest__.py
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
- ab_employee_access_sales/changelog.d/2026-10-28-unified-pos-store-permissions.md

## Current changes before commit:

- Allow an authorized Bill Wizard invoice to open its return dialog before employee PIN login.
- Continue rejecting invalid supplied session tokens and requiring an active return-enabled employee session for every return read, edit, and submission operation.
- Preserve record-rule ownership so normal users cannot open another user's trusted Call Center invoice.
- Bump the module version to 19.0.2.0.4.

Files changed:
- ab_employee_access_sales/__manifest__.py
- ab_employee_access_sales/models/ab_sales_return_ui_api_inherit.py
- ab_employee_access_sales/tests/test_ab_employee_access_sales_api.py
- ab_employee_access_sales/changelog.d/2026-10-28-bill-wizard-return-login.md

Validation:
- Passed 20 focused employee-access tests across 18 test methods with zero failures and errors.
- Passed the focused full and partial return calculation tests in `ab_sales`.
- Passed targeted module upgrades on the `callcenter` database using isolated port 4192.
- No user-facing strings or translation catalogs changed.
