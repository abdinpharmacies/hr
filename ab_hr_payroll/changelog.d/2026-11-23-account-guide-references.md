# Payroll accounting catalog references — 2026-11-23

## Recent commit

- Commit: `7f212a51761c356a7f476a37377e8a047403cdb9`
- Author: Hossam Elsheikh
- Date: 2026-11-17T15:16:46+02:00
- Original commit subject: ab_hr_payroll/FIX: protect salary journals and repair reports and filters
- Protected salary journal operations and repaired payroll reports and filters.

Files changed:

- `ab_hr_payroll/changelog.d/2026-11-15-checklist-repair.md`
- `ab_hr_payroll/changelog.d/2026-11-17-access-rollback.md`
- `ab_hr_payroll/i18n/ar.po`
- `ab_hr_payroll/i18n/ar_001.po`
- `ab_hr_payroll/models/account_header_salaries_inherit.py`
- `ab_hr_payroll/models/action_wizard.py`
- `ab_hr_payroll/views/action_wizard.xml`

## Current changes before commit:

- Update all 14 legacy account-guide references to `ab_accounting_base`, including the commented example.
- Use the current firing-parent, due-salaries, and cash due-salaries XML IDs in payroll logic, reports, the salary record rule, and the salary journal action.
- Preserve existing workflow logic and access domains apart from the XML-ID namespace correction.
- No user-facing strings changed; Arabic and English translations require no updates.
- No tests, database upgrades, backups, or test databases were run or created, as requested.

Files changed:

- `ab_hr_payroll/models/ab_due_salaries_qry.py`
- `ab_hr_payroll/models/account_header_salaries_inherit.py`
- `ab_hr_payroll/security/record_rules_due_salaries.xml`
- `ab_hr_payroll/views/account_header_salaries_inherit.xml`
- `ab_hr_payroll/changelog.d/2026-11-23-account-guide-references.md`
