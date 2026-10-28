## d657f9d83dd58b5b8ef9fbe852c3529815231116 - hossam elsheikh - 2026-10-21

Original commit subject: ab_employee_access_sales:fix_translation

User-facing changes:
- Completed Arabic coverage for the employee-authenticated POS and return workflow.
- Kept translated frontend messages aligned with the employee PIN session flow.

Files changed:
- ab_employee_access_sales/__manifest__.py
- ab_employee_access_sales/i18n/ar.po
- ab_employee_access_sales/i18n/ar_001.po
- ab_employee_access_sales/static/src/pos/ab_employee_access_sales_pos_patch.js
- ab_employee_access_sales/static/src/pos/ab_employee_access_sales_pos_templates.xml
- ab_employee_access_sales/static/src/sales_return/ab_employee_access_sales_return_patch.js
- ab_employee_access_sales/static/src/sales_return/ab_employee_access_sales_return_templates.xml
- ab_employee_access_sales/changelog.d/2026-10-21-arabic-completion.md

## Current changes before commit:

- Resolve POS stores from active sale-enabled stores, intersecting non-empty Replica DB and employee-profile restrictions.
- Require an employee PIN session owned by the current internal Odoo user for store-scoped POS, customer, draft, return, and submission operations.
- Keep permitted stores visible when their branch connection is unavailable while preventing selection and direct RPC use.
- Remove administrator, manager, Call Center group, HR department, and service-user shortcuts from POS eligibility.
- Provide compatible visible, available, default, connection-state, and translated empty-state payload fields.
- Bump the module version to 19.0.2.0.3.

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

Validation:
- Passed 17 focused Odoo tests covering 15 test methods and the POS store-scope and tamper-resistance matrix.
- Passed targeted `ab_sales,ab_employee_access_sales` upgrade on the `callcenter` database using isolated port 4192.
- Confirmed the installed runtime exposes three eligible stores, one ready store, a connectable default, and distinct English and Arabic connection messages.
- Passed Python compilation, XML parsing, JavaScript syntax, PO format, POT coverage, and whitespace checks.
