# ab_branch_api: respect read-only posted bills during recovery

## Recent commit

Commit: `679ef27bf7c47edec06143502864a9288caf1c9d`

Author: Hossam Elsheikh

Date: 2026-09-17T15:57:05+03:00

Original commit subject: ab_branch_api/ fix bug in my last edit: a draft without an E-Plus serial could match an unrelated invoice ID 0, causing a false conflict. The error wrapper also hid the original submission failure.

- Exclude zero-ID invoice fallback matches and report specific recovery conflicts.

Files changed:

- `ab_branch_api/README.md`
- `ab_branch_api/__manifest__.py`
- `ab_branch_api/changelog.d/2026-09-17-recovery-zero-serial.md`
- `ab_branch_api/i18n/ar.po`
- `ab_branch_api/i18n/ar_001.po`
- `ab_branch_api/models/reconciliation.py`

## Current changes before commit:

- Fix the journal checkpoint requesting write access after posting has changed the sale to Pending. Read transaction identifiers with normal header/line read access.
- Validate operation owner and store before recovery; finalize or restore only generated lifecycle fields through the private recovery workflow.
- Preserve normal draft write checks and Pending/Saved header/line edit restrictions. No security configuration or user memberships change.
- Document the fix and bump to 19.0.5.3.2. No new or changed user-facing strings; existing translated errors are reused.

Files changed:

- `ab_branch_api/README.md`
- `ab_branch_api/__manifest__.py`
- `ab_branch_api/changelog.d/2026-09-17-recovery-readonly-access.md`
- `ab_branch_api/models/reconciliation.py`

Validation:

- Reproduced the exact ab_sales_header write denial with a non-admin cashier on the disposable database before applying the fix.
- Real ORM/record-rule tests with mocked external SQL: successful posting, completed replay, rejected commit recovery, lost-response recovery with a Saved bill, preserved lines/prices, continued denial of ordinary posted-bill edits, operation-owner isolation, branch isolation and enforced current read restrictions.
- Existing recovery suite passes, including duplicate/conflicting evidence and atomic return replication/repricing failure cases.
- Targeted disposable branch upgrade, Python syntax and diff checks; no deployed database or external stock writes.
- Test scripts and results: `/tmp/branch_recovery_access_validation`.
