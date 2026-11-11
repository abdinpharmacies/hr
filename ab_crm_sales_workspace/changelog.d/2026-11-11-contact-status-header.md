# Keep POS customer status in contact operations

## Committed baseline

- Commit: `2702b7f16d06c516db1ae66d7d8f592432396edd`
- Author: `Alhassan Hossny`
- Date: `2026-11-09T14:05:37+02:00`
- Original subject: `ab_crm_sales_workspace/docs: record grouped chatter and menu fixes`

## Changes included in implementation commit `77209fcb`

- Version 19.0.1.26.1 removes the Is POS customer checkbox from the conversation heading and the contact-only conversation panel.
- Restore the single-row header layout: customer name and phone, centered channel buttons and the search toggle. Keep the contact-dialog checkbox and computed POS customer status for contact operations and audits.
- Remove only the obsolete workspace reference from both Arabic catalogs; preserve the contact-dialog label and its translation.
- Preserve the preceding Inbox, POS handoff and contact changes included in this update.
- Deactivate the three Sales Chatter submenu entries so its navigation tab directly opens Inbox. Preserve their XML IDs and actions, and keep the workspace's order and invoice buttons available.

Files changed for this increment:
- `__manifest__.py`
- `static/src/workspace.xml`
- `static/tests/message.test.js`
- `tests/test_workspace.py`
- `views/views.xml`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `changelog.d/2026-11-11-contact-status-header.md`
