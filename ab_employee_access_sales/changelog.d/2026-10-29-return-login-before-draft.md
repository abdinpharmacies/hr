## d657f9d83dd58b5b8ef9fbe852c3529815231116 - hossam elsheikh - 2026-10-21

Original commit subject: ab_employee_access_sales:fix_translation

- Complete Arabic coverage for the employee PIN and return screens.

Files changed:
- ab_employee_access_sales/__manifest__.py
- ab_employee_access_sales/changelog.d/2026-10-21-arabic-completion.md
- ab_employee_access_sales/i18n/ar.po
- ab_employee_access_sales/i18n/ar_001.po
- ab_employee_access_sales/static/src/pos/ab_employee_access_sales_pos_patch.js
- ab_employee_access_sales/static/src/pos/ab_employee_access_sales_pos_templates.xml
- ab_employee_access_sales/static/src/sales_return/ab_employee_access_sales_return_patch.js
- ab_employee_access_sales/static/src/sales_return/ab_employee_access_sales_return_templates.xml

## Current changes before commit:

- Require an active employee session with return permission and branch access before opening a sales return.
- Prompt for employee code and PIN on each Bill Wizard return, then create or resume the return and load its lines.
- Discard late login/load responses after popup closure, log out late sessions, and clean up late return drafts through the shared cleanup guard.
- Update the existing return-opening test for login-first behavior.
- Bump the module version to 19.0.2.0.5.

Files changed:
- ab_employee_access_sales/__manifest__.py
- ab_employee_access_sales/models/ab_sales_return_ui_api_inherit.py
- ab_employee_access_sales/static/src/sales_return/ab_employee_access_sales_return_patch.js
- ab_employee_access_sales/tests/test_ab_employee_access_sales_api.py
- ab_employee_access_sales/changelog.d/2026-10-29-return-login-before-draft.md

Validation:
- Passed delayed-response checks against the actual frontend methods for late login, late draft creation, late record loading, normal opening, and preservation after a Commit attempt.
- The focused ORM test was attempted on local QA but blocked in fixture setup by the existing Store replication create restriction, before the return assertions.
- No server deployment or real branch return was performed.
