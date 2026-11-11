# HR changes

## Current changes before commit:

- Align employee cards with the dev-central19 layout while retaining chat integration, workflow buttons, and existing access/editability.
- Display supervision badges in the employee list and maintain their Arabic labels for both language codes.
- Modernize employee, occupied-job, and history chatter without changing model definitions or business logic.

Files changed:
- `changelog.d`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `views/ab_hr_employee.xml`
- `views/ab_hr_job_occupied.xml`
- `views/history.xml`

## 43af83499 — emadco88 — 2026-11-09

Original commit subject: `migrate19 INIT`

- Initialize the Odoo 19 hr addon.

Files changed:
- `__manifest__.py`
- `models/`
- `views/`
- `security/`
