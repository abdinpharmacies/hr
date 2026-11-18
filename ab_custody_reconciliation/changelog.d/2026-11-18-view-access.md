# Form access repair — 2026-11-18

## Recent relevant commit

- Commit: `2a94f93f40b2f24fb649c2cfc5c725326d15a3bf`
- Author: Hossam Elsheikh
- Date: 2026-11-17 15:17:26 +0200
- Original commit subject: `ab_custody_reconciliation/DOCS: document custody access rollback`
- Documented the rollback of added custody access grants.

Files changed:

- `ab_custody_reconciliation/changelog.d/2026-11-15-checklist-repair.md`
- `ab_custody_reconciliation/changelog.d/2026-11-17-access-rollback.md`

## Current changes before commit:

- Omit the custody relation from journal forms for users without existing custody read permission. Authorized custody readers retain the field.
- Filter each returned form architecture after the shared cache; preserve ACLs, groups, memberships, record rules and business operations.
- Verification: Payroll payment, settlement and cleanup browser checks; mixed-role view-cache checks; direct custody reads remain denied.
- No new or changed user-facing strings; both Arabic translation files remain unchanged. Existing English/Arabic form differences verified.

Files changed:

- `ab_custody_reconciliation/models/ab_accounting_je_header_inherit.py`
- `ab_custody_reconciliation/changelog.d/2026-11-18-view-access.md`
