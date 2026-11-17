# Checklist repairs — 2026-11-15

## Recent commit

- Commit: `c8f8f07257c7d134485eae7bceb5561d519618fb`
- Author: hager yasser
- Date: 2026-11-12 16:23:03 +0200
- Original commit subject: ab_custody_reconciliation/FIX: repair form layouts and contain detail table scrolling

Established the module baseline before the current checklist repairs.

## Current changes before commit:

- Restrict the journal custody field to custody users so unrelated payroll journal forms load.
- Keep custody consistency validation as a bounded internal read without exposing custody data or granting broader business roles.

Files changed:

- `ab_custody_reconciliation/models/ab_accounting_je_header_inherit.py`
- `ab_custody_reconciliation/views/ab_accounting_je_header_inherit.xml`
