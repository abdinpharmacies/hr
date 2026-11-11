# Egyptian phone display and customer channel alerts

## Committed baseline

- Commit: `2702b7f16d06c516db1ae66d7d8f592432396edd`
- Author: `Alhassan Hossny`
- Date: `2026-11-09T14:05:37+02:00`
- Original subject: `ab_crm_sales_workspace/docs: record grouped chatter and menu fixes`

## Changes included in implementation commit `77209fcb`

- Build on the existing unified-contact and reception changes; version 19.0.1.18.0.
- Add national Egyptian display fields while preserving canonical phone and destination values; normalize legacy effective-number searches and partial matches.
- Offer Create new / Use existing, preserve proposed numbers for explicit review, preselect editing and archival, and expose reviewed channel links and manager duplicate merging.
- Preview both contacts, their primary/additional phones, channel identities and conversations while preserving fingerprints, scope checks and audit evidence.
- Share employee/company-scoped unread calculation across customer rows, channels, detail and popup eligibility. Reads remove alert eligibility; dismissal acknowledges captured message IDs only.
- Group notifications across response pages by customer with an action per conversation. Keep unlinked conversations separate and broadcast read/acknowledgment refreshes only within employee/company scope.
- Use shared conversation selection for alert navigation; preserve drafts/attachments, exact destination, selected stream and message focus. Add chooser selection, keyboard navigation and dismissal.
- Suppress automatic reads in hidden/unfocused tabs, search, older history and alert navigation.
- Add English/Arabic controls and focused ORM, browser, security, concurrency and runtime-language checks. Retain earlier reception/dispatch fixes.

Validation and maintenance-window procedure: `docs/phone-display-alerts-rollout.md`.

Files changed for this increment:
- `__manifest__.py`
- `changelog.d/2026-11-10-phone-display-alerts.md`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `models/alerts.py`
- `models/contact_phones.py`
- `models/customer_streams.py`
- `models/directory.py`
- `models/orders.py`
- `models/workspace.py`
- `static/src/alerts.xml`
- `static/src/contacts.js`
- `static/src/contacts.xml`
- `static/src/order_dialog.xml`
- `static/src/session_service.js`
- `static/src/workspace.js`
- `static/src/workspace.xml`
- `static/tests/contact_phones.test.js`
- `static/tests/message.test.js`
- `static/tests/notifications.test.js`
- `tests/test_workspace.py`
