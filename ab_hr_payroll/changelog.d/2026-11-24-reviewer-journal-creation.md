# Journal entry creation for reviewers

Commit: `7f212a51`
Author: Hossam Elsheikh
Date: 2026-11-17
Original commit subject: `ab_hr_payroll/FIX: protect salary journals and repair reports and filters`

- Introduced salary-specific journal form behavior to protect salary generation.

Files changed (relevant to this fix):
- `models/account_header_salaries_inherit.py`

## Current changes before commit:

- Restore regular journal entry creation for reviewers without granting payroll field access.
- Preserve salary journal behavior for Accounting Managers.

Files changed:
- `models/account_header_salaries_inherit.py`
- `changelog.d/2026-11-24-reviewer-journal-creation.md`
