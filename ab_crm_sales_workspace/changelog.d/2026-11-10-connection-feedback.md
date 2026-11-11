# Connection recovery and native feedback

## Committed baseline

- Commit: `2702b7f16d06c516db1ae66d7d8f592432396edd`
- Author: `Alhassan Hossny`
- Date: `2026-11-09T14:05:37+02:00`
- Original subject: `ab_crm_sales_workspace/docs: record grouped chatter and menu fixes`

## Changes included in implementation commit `77209fcb`

- Version 19.0.1.25.0 centralizes Sales Chatter feedback in sticky native Odoo notifications. Replace inline errors/info/warnings across the workspace, contacts, login, saved replies, branch/location and order dialogs; preserve interactive confirmation actions and form choices.
- Recognize Odoo connection-loss errors, hide technical RPC URLs, deduplicate outage warnings even after dismissal, and report recovery. Retain inbox, messages, drafts and attachments; background reads resume and interrupted sends/saves are never automatically retried.
- Restore cached employee sessions after startup connection failure. Share connection state with alert polling and branch sharing without changing global Odoo components.
- Verify outage/recovery, exact-message alerts, native confirmations, draft preservation, desktop/mobile behavior and both Arabic catalogs.

Files changed for this increment:
- `__manifest__.py`
- `static/src/feedback.js`
- `static/src/workspace.js`
- `static/src/workspace.xml`
- `static/src/session_service.js`
- `static/src/contacts.js`
- `static/src/contacts.xml`
- `static/src/login.js`
- `static/src/login.xml`
- `static/src/templates.js`
- `static/src/templates.xml`
- `static/src/composer.js`
- `static/src/composer.xml`
- `static/src/location.js`
- `static/src/location.xml`
- `static/src/order_dialog.js`
- `static/src/order_dialog.xml`
- `static/src/branch_widget.js`
- `static/src/branch_widget.xml`
- `static/tests/feedback.test.js`
- `static/tests/composer.test.js`
- `static/tests/location.test.js`
- `static/tests/chatter_ui.test.js`
- `static/tests/notifications.test.js`
- `tests/test_workspace.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `changelog.d/2026-11-10-connection-feedback.md`
