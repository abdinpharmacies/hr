# Existing-contact linking without extra confirmation

## Committed baseline

- Commit: `2702b7f16d06c516db1ae66d7d8f592432396edd`
- Author: `Alhassan Hossny`
- Date: `2026-11-09T14:05:37+02:00`
- Original subject: `ab_crm_sales_workspace/docs: record grouped chatter and menu fixes`

## Changes included in implementation commit `77209fcb`

- Version 19.0.1.23.0 removes the same-person checkbox and server-side confirmation requirement for existing-contact linking. Keep the RPC argument compatible and retain accurate audit evidence without inventing customer confirmation.
- Preserve scope, permissions, stale-preview protection and manager conflict resolution. Phone maintenance and duplicate-record consolidation remain separate.

Files changed for this increment:
- `__manifest__.py`
- `models/customer_streams.py`
- `static/src/contacts.js`
- `static/src/contacts.xml`
- `static/tests/contact_phones.test.js`
- `tests/test_workspace.py`
- `changelog.d/2026-11-10-link-without-confirmation.md`
