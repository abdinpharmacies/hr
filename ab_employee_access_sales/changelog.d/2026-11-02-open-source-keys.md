## 94dacb538e05f698675d773d9e0af1b4a775f498

- Author: Alhassan Hossny <alhassan.hossny@gmail.com>
- Date: 2026-09-07T17:03:22+03:00
- Subject: ab_employee_access_sales: convert POS HR sync to passive reports

User-facing changes:

- Converted POS HR sync into passive reporting.

Files changed:

- `ab_employee_access_sales/__manifest__.py`
- `ab_employee_access_sales/changelog.d/2026-09-03-report-server-passive-cleanup.md`
- `ab_employee_access_sales/models/__init__.py`
- `ab_employee_access_sales/models/ab_employee_access_sales_operation_log.py`
- `ab_employee_access_sales/models/ab_employee_access_sales_pos_session.py`
- `ab_employee_access_sales/models/ab_employee_access_sales_shift.py`
- `ab_employee_access_sales/models/ab_sales_header.py`
- `ab_employee_access_sales/security/ir.model.access.csv`
- `ab_employee_access_sales/security/record_rules.xml`
- `ab_employee_access_sales/views/ab_employee_access_sales_operation_log_views.xml`
- `ab_employee_access_sales/views/ab_employee_access_sales_pos_session_views.xml`
- `ab_employee_access_sales/views/ab_employee_access_sales_shift_views.xml`
- `ab_employee_access_sales/views/menus.xml`

## Current changes before commit:

User-facing changes:

- Store four source-owned shift, session, and operation fields as open-ended keys.
- Updated the module version.

Files changed:

- `ab_employee_access_sales/__manifest__.py`
- `ab_employee_access_sales/models/ab_employee_access_sales_operation_log.py`
- `ab_employee_access_sales/models/ab_employee_access_sales_pos_session.py`
- `ab_employee_access_sales/models/ab_employee_access_sales_shift.py`
- `ab_employee_access_sales/changelog.d/2026-11-02-open-source-keys.md`
