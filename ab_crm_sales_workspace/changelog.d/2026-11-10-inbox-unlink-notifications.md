# Inbox separation and native notifications

## Committed baseline

- Commit: `2702b7f16d06c516db1ae66d7d8f592432396edd`
- Author: `Alhassan Hossny`
- Date: `2026-11-09T14:05:37+02:00`
- Original subject: `ab_crm_sales_workspace/docs: record grouped chatter and menu fixes`

## Changes included in implementation commit `77209fcb`

- Version 19.0.1.24.0 adds Unlink for a selected customer with multiple grouped conversations. Atomically archive identity associations and separate every visible grouped conversation; retain customer, messages, orders, evidence and queued destinations. Archived identities prevent automatic relinking after refresh/incoming events.
- Enforce staff session, company/branch scope, current customer, locks and snapshot fingerprints; write protected employee-attributed unlink audits.
- Remove duplicate-consolidation entry points, the unlinked-review banner and redundant Create/Edit actions below the conversation header. Rename the sidebar heading Inbox.
- Replace the custom fixed alert stack with sticky native Odoo notifications, retaining customer grouping, individual conversation actions and exact-message dismissal. Wait for localization readiness before composing alert text. Silent refresh/session cleanup never acknowledges alerts; failed navigation keeps them available.
- Translate new labels in both Arabic catalogs and test grouping, unlinking, drafts, notification pagination, arrival races and authorization.

Files changed for this increment:
- `__manifest__.py`
- `models/customer_streams.py`
- `static/src/workspace.js`
- `static/src/workspace.xml`
- `static/src/workspace.scss`
- `static/src/contacts.xml`
- `static/src/session_service.js`
- `static/src/alerts.xml (removed)`
- `static/tests/notifications.test.js`
- `tests/test_workspace.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `changelog.d/2026-11-10-inbox-unlink-notifications.md`
