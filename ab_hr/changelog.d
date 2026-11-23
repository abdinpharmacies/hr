Current changes before commit:

- Limit replica HR to employees, departments, and jobs. Store copied employee values independently of cost centers and assignments.
- Open Employees in kanban by default, retaining list and form views.
- Restore the employee kanban card layout with colored codes, centered identity and assignment, colored employment dates, and the department search sidebar.
- Simplify HR navigation, retain read-only access, and maintain Arabic translations for the reduced interface.

- Preserve the HR Coordinator role used by the installed Announcements ACL and its inheritance by HR Manager.

Files changed:

- ab_hr/__manifest__.py
- ab_hr/changelog.d
- ab_hr/data/data.xml
- ab_hr/i18n/ab_hr.pot
- ab_hr/i18n/ar.po
- ab_hr/i18n/ar_001.po
- ab_hr/models/__init__.py
- ab_hr/models/ab_hr_department.py
- ab_hr/models/ab_hr_employee.py
- ab_hr/models/ab_hr_job.py
- ab_hr/models/ab_hr_job_occupied.py
- ab_hr/models/ab_hr_region.py
- ab_hr/models/constants.py
- ab_hr/models/extra_functions.py
- ab_hr/models/history.py
- ab_hr/models/history_report.py
- ab_hr/models/history_type.py
- ab_hr/models/hris.py
- ab_hr/models/last_day_of_month.py
- ab_hr/models/manpower.py
- ab_hr/models/res_users_inherit.py
- ab_hr/report/__init__.py
- ab_hr/report/export_xlsx.py
- ab_hr/report/report_xlsx.xml
- ab_hr/report/templates/pdf_salaries.xml
- ab_hr/report/templates/pdf_salaries_compare.xml
- ab_hr/report/templates/template_salaries.xml
- ab_hr/report/templates/template_salaries_compare.xml
- ab_hr/report/templates/xlsx_account_statement.xml
- ab_hr/report/templates/xlsx_salaries.xml
- ab_hr/security/ir.model.access.csv
- ab_hr/security/record_rules.xml
- ab_hr/security/security_groups.xml
- ab_hr/views/00_menus.xml
- ab_hr/views/ab_hr_department.xml
- ab_hr/views/ab_hr_employee.xml
- ab_hr/views/ab_hr_job.xml
- ab_hr/views/ab_hr_job_occupied.xml
- ab_hr/views/history.xml
- ab_hr/views/history_action_type.xml
- ab_hr/views/history_report.xml
- ab_hr/views/hris.xml
- ab_hr/views/manpower.xml

commit 3db5d596c9429ff082c3fe9b0466692b945f788f
Author: emadco88 <emadco88@gmail.com>
Date:   2026-07-28T15:21:42+03:00

    INIT commit pos19

- Introduce employee records, job assignments, departments, and HR reporting on the POS branch.

Files changed:

- ab_hr/__init__.py
- ab_hr/__manifest__.py
- ab_hr/data/data.xml
- ab_hr/i18n/ar_001.po
- ab_hr/models/__init__.py
- ab_hr/models/ab_hr_department.py
- ab_hr/models/ab_hr_employee.py
- ab_hr/models/ab_hr_job.py
- ab_hr/models/ab_hr_job_occupied.py
- ab_hr/models/ab_hr_region.py
- ab_hr/models/constants.py
- ab_hr/models/extra_functions.py
- ab_hr/models/history.py
- ab_hr/models/history_report.py
- ab_hr/models/history_type.py
- ab_hr/models/hris.py
- ab_hr/models/last_day_of_month.py
- ab_hr/models/manpower.py
- ab_hr/models/res_users_inherit.py
- ab_hr/report/__init__.py
- ab_hr/report/export_xlsx.py
- ab_hr/report/report_xlsx.xml
- ab_hr/report/templates/pdf_salaries.xml
- ab_hr/report/templates/pdf_salaries_compare.xml
- ab_hr/report/templates/template_salaries.xml
- ab_hr/report/templates/template_salaries_compare.xml
- ab_hr/report/templates/xlsx_account_statement.xml
- ab_hr/report/templates/xlsx_salaries.xml
- ab_hr/security/ir.model.access.csv
- ab_hr/security/record_rules.xml
- ab_hr/security/security_groups.xml
- ab_hr/static/description/icon.png
- ab_hr/static/description/icon.svg
- ab_hr/views/00_menus.xml
- ab_hr/views/ab_hr_department.xml
- ab_hr/views/ab_hr_employee.xml
- ab_hr/views/ab_hr_job.xml
- ab_hr/views/ab_hr_job_occupied.xml
- ab_hr/views/history.xml
- ab_hr/views/history_action_type.xml
- ab_hr/views/history_report.xml
- ab_hr/views/hris.xml
- ab_hr/views/manpower.xml
