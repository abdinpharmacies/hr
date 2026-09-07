Recent relevant commit:

- Commit: `d6761c2`
- Author: emadco88
- Date: 2026-09-06
- Original subject: ab_employee_access_sales: clean report sync fields
- User-facing changes:
  - Added report sync metadata to the module's high-value POS HR reporting records.
  - Removed required flags and report-side `res.users` relations from the synchronized model fields.
  - Prepared the module for report-server sync mapping without requiring live branch POS write flows.
- Files changed:
  - ab_employee_access_sales/__manifest__.py
  - ab_employee_access_sales/changelog.d/2026-09-03-report-server-passive-cleanup.md
  - ab_employee_access_sales/models/ab_employee_access_sales_operation_log.py
  - ab_employee_access_sales/models/ab_employee_access_sales_pos_api.py
  - ab_employee_access_sales/models/ab_employee_access_sales_pos_session.py
  - ab_employee_access_sales/models/ab_employee_access_sales_shift.py
  - ab_employee_access_sales/models/ab_sales_header.py
  - ab_employee_access_sales/models/ab_store.py

Current changes before commit:

- User-facing changes:
  - Converted `ab_employee_access_sales` into a passive report-server install target for the high-value POS HR sync facts.
  - Loaded only passive shift, POS session, operation log, and sales-header reporting fields on the report server.
  - Removed live branch POS API imports, cashier integration imports, frontend assets, the cashier dependency, and the store view from this install path.
  - Removed business write methods from passive shift/session records and removed the sales-header POS session lookup override.
  - Added archive support and unique source identity constraints for POS shifts, POS sessions, and operation logs.
  - Made passive security and views read-only while keeping archived rows visible in the reporting actions.
  - Anchored the POS HR report menu under the installed Sales Reporting root on report servers.
- Files changed:
  - ab_employee_access_sales/__manifest__.py
  - ab_employee_access_sales/changelog.d/2026-09-03-report-server-passive-cleanup.md
  - ab_employee_access_sales/models/__init__.py
  - ab_employee_access_sales/models/ab_employee_access_sales_operation_log.py
  - ab_employee_access_sales/models/ab_employee_access_sales_pos_session.py
  - ab_employee_access_sales/models/ab_employee_access_sales_shift.py
  - ab_employee_access_sales/models/ab_sales_header.py
  - ab_employee_access_sales/security/ir.model.access.csv
  - ab_employee_access_sales/security/record_rules.xml
  - ab_employee_access_sales/views/menus.xml
  - ab_employee_access_sales/views/ab_employee_access_sales_operation_log_views.xml
  - ab_employee_access_sales/views/ab_employee_access_sales_pos_session_views.xml
  - ab_employee_access_sales/views/ab_employee_access_sales_shift_views.xml
