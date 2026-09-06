Recent relevant commit:

- Commit: `738f1bc8f9606fddaa1a179fa76ec8e776999874`
- Author: Alhassan Hossny
- Date: 2026-08-25
- Original subject: ab_hr: relax employee master fields for report sync
- User-facing changes:
  - Established the previous baseline for this module before the report-server passive cleanup.
- Files changed:
  - ab_hr/changelog.d/2026-08-25-report-server-master-placeholders.md
  - ab_hr/models/ab_hr_employee.py

Current changes before commit:

- User-facing changes:
  - Replaced explicit report-side user relations with `ab_users` placeholders where this module declares user fields.
  - Removed `required=True` from model field declarations so report sync loads can accept incomplete branch payloads.
  - Declared new module dependencies required by the cleaned report-server model schema.
- Files changed:
  - ab_hr/changelog.d/2026-09-03-report-server-passive-cleanup.md
  - ab_hr/__manifest__.py
  - ab_hr/models/ab_hr_department.py
  - ab_hr/models/ab_hr_employee.py
  - ab_hr/models/ab_hr_job.py
  - ab_hr/models/ab_hr_job_occupied.py
  - ab_hr/models/ab_hr_region.py
  - ab_hr/models/history.py
  - ab_hr/models/history_report.py
  - ab_hr/models/history_type.py
  - ab_hr/models/hris.py
  - ab_hr/models/manpower.py
