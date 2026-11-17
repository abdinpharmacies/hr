# Access rollback — 2026-11-17

## Recent commit

- Commit: `e728ae32b704a89cf9d694bf4840c3190ffb71f3`
- Author: hossam elsheikh
- Date: 2026-11-12T16:35:40+02:00
- Original commit subject: ab_hr_payroll/FIX: repair payroll action and salary journal layouts

## Current changes before commit:

- Restore original salary/report access scope and remove the added Accounting Manager generation requirement. Preserve journal locking, duplicate/posted protections and salary-comparison fixes.
- Fix the payroll criteria reset crash by clearing the actual Branch field (`store_ids`) together with the dates. Existing ownership and processed-action restrictions remain unchanged; isolated positive and denied-reset regressions pass. No user-facing strings changed.
- Access behavior restored to `82ea1dc7`; prior security-repair acceptance results are historical. No user memberships or passwords changed.

Files changed:

- `ab_hr_payroll/models/account_header_salaries_inherit.py`
- `ab_hr_payroll/models/action_wizard.py`
- `ab_hr_payroll/views/action_wizard.xml`
