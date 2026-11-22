# HR changes

## Current changes before commit:

- Refresh the employee’s stored department and job when the occupied assignment changes. The selected primary job continues to determine the profile when an employee holds multiple jobs.

- Restrict employee ID and birth-date exports for users whose sole HR role is Basic Data, including related cost-center columns and grouped Excel labels. Higher HR roles retain access with the standard Odoo export permission.

Files changed:

- `ab_hr/__init__.py`
- `ab_hr/__manifest__.py`
- `ab_hr/controllers/__init__.py`
- `ab_hr/controllers/export.py`
- `ab_hr/i18n/ar.po`
- `ab_hr/i18n/ar_001.po`
- `ab_hr/models/__init__.py`
- `ab_hr/models/ab_hr_employee.py`
- `ab_hr/models/costcenter.py`
- `ab_hr/changelog.d`

## Recent commit

- Commit: `52396002594a49a2d9aaff151e333ba02f896734`
- Author: Hossam Elsheikh
- Date: 2026-11-17T15:16:31+02:00
- Original commit subject: ab_hr/FIX: repair employee forms, history dates and manpower searches
- Repaired employee forms, history dates and manpower searches, and restored the original access rules and job-action authorization.

Files changed:

- `ab_hr/changelog.d`
- `ab_hr/i18n/ar.po`
- `ab_hr/i18n/ar_001.po`
- `ab_hr/models/ab_hr_employee.py`
- `ab_hr/models/history.py`
- `ab_hr/models/job_wizard.py`
- `ab_hr/models/manpower.py`
- `ab_hr/models/report_wizard.py`
- `ab_hr/views/ab_hr_employee.xml`
- `ab_hr/views/history.xml`
