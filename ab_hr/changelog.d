# Access rollback — 2026-11-17

## Recent commit

- Commit: `0b7577161d98cc21c1c21a410f10dae3ec398df1`
- Author: hossam elsheikh
- Date: 2026-11-12T16:35:39+02:00
- Original commit subject: ab_hr/FIX: repair HR forms and job wizard layouts

## Current changes before commit:

- Restore original employee, history and manpower access rules and job-action authorization. Preserve date, display, form/sidebar and export fixes; the cost-center selector remains repaired.
- Access behavior restored to `82ea1dc7`; prior security-repair acceptance results are historical. No user memberships or passwords changed.

Files changed:

- `ab_hr/i18n/ar.po`
- `ab_hr/i18n/ar_001.po`
- `ab_hr/models/ab_hr_employee.py`
- `ab_hr/models/history.py`
- `ab_hr/models/job_wizard.py`
- `ab_hr/models/manpower.py`
- `ab_hr/models/report_wizard.py`
- `ab_hr/views/ab_hr_employee.xml`
- `ab_hr/views/history.xml`
