Recent relevant commit:

- Commit: b100723692337b2140efebb833a7a0ee40fd0156
- Author: Hossam Elsheikh
- Date: 2026-11-05T16:45:29+02:00
- Original subject: fix(ab_employee_access_sales): preserve employee session context in native returns
- Preserved employee context in native return entry points.

Files changed:

- ab_employee_access_sales/__manifest__.py
- ab_employee_access_sales/changelog.d/2026-11-05-role-split.md
- ab_employee_access_sales/models/ab_sales_return_ui_api_inherit.py
- ab_employee_access_sales/workflow.md

Current changes before commit:

- Remove activity and implicit branch writes from POS and return session validation; make heartbeat read-only.
- Preserve operation-branch audit attribution without mutating session selection.
- Prevent overlapping heartbeat calls and document timestamp semantics.

Files changed:

- ab_employee_access_sales/__manifest__.py
- ab_employee_access_sales/changelog.d/2026-11-08-read-only-pos-checks.md
- ab_employee_access_sales/models/ab_employee_access_sales_pos_api.py
- ab_employee_access_sales/models/ab_employee_access_sales_pos_session.py
- ab_employee_access_sales/models/ab_sales_pos_api.py
- ab_employee_access_sales/models/ab_sales_return_ui_api_inherit.py
- ab_employee_access_sales/static/src/pos/ab_employee_access_sales_pos_patch.js
- ab_employee_access_sales/workflow.md

Validation:

- Isolated local database: focused read-only validation, live balances/prices, fallback, and audit attribution checks passed.
- Six concurrent clients / 54 operations: no protected-table SQL writes; search p95 0.304 seconds with mocked branch API responses.
- Headless Chromium harness: heartbeat overlap/cleanup, stale response ordering, zero balance and offline retention passed.
- Targeted module upgrade completed; existing regression suite had 42 replication-policy fixture errors, identical on unchanged HEAD.
- No new user-facing strings; existing Arabic translations retained. Production was not upgraded.
