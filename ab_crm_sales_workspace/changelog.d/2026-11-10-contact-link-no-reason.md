# Contact linking without a mandatory reason

## Committed baseline

- Commit: `2702b7f16d06c516db1ae66d7d8f592432396edd`
- Author: `Alhassan Hossny`
- Date: `2026-11-09T14:05:37+02:00`
- Original subject: `ab_crm_sales_workspace/docs: record grouped chatter and menu fixes`

## Changes included in implementation commit `77209fcb`

- Version 19.0.1.22.0 removes the review-reason input and minimum-length validation when linking a conversation to an existing contact.
- Move the chain-link icon into the Contacts toolbar beside Add, Edit and Archive. Enable it for a selected conversation and keep the toolbar accessible on mobile.
- Scope the existing-contact picker to the current conversation branch. Replace its generic matching-customer error with specific missing-record or scope errors; accept active contacts without a phone match using explicit confirmation.
- Keep the optional RPC argument compatible; record supplied text or a default association description in the audit. Preserve same-person confirmation, manager conflict resolution, scope checks, locking and fingerprints.
- Keep phone-edit and duplicate-consolidation reasons separate. Preserve existing English and Arabic message entries used by those workflows.
- Verify manual linking without a reason, unchanged message identifiers/destination, audit attribution, stale previews, unauthorized RPC calls and direct ORM writes.

Files changed for this increment:
- `__manifest__.py`
- `models/customer_streams.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `static/src/contacts.js`
- `static/src/contacts.xml`
- `static/src/workspace.js`
- `static/src/workspace.xml`
- `static/src/workspace.scss`
- `static/tests/contact_phones.test.js`
- `tests/test_workspace.py`
- `changelog.d/2026-11-10-contact-link-no-reason.md`
