# Checklist repairs — 2026-11-15

## Recent commit

- Commit: `e728ae32b704a89cf9d694bf4840c3190ffb71f3`
- Author: hossam elsheikh
- Date: 2026-11-12 16:35:40 +0200
- Original commit subject: ab_hr_payroll/FIX: repair payroll action and salary journal layouts

Established the module baseline before the current checklist repairs.

## Current changes before commit:

- Enforce branch scope on payroll and report rows, and scope report SQL and counters to records accessible to the caller.
- Serialize payment generation, reject repeats and preserve populated/posted journals; avoid the general form’s empty placeholder in salary journals.
- Repair Paid navigation, missing-month and zero-baseline comparisons, Excel exports and Arabic validation.

Files changed:

- `ab_hr_payroll/i18n/ar.po`
- `ab_hr_payroll/i18n/ar_001.po`
- `ab_hr_payroll/models/account_header_salaries_inherit.py`
- `ab_hr_payroll/models/action_wizard.py`
- `ab_hr_payroll/security/record_rules_payroll.xml`
- `ab_hr_payroll/views/action_wizard.xml`
