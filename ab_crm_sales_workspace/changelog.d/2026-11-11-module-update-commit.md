# Module update commit record

- Commit: `77209fcb65977441d975ea0b906b8b0fdf3b8f1b`
- Author: `Alhassan Hossny`
- Date: `2026-11-11T11:48:59+02:00`
- Original subject: `ab_crm_sales_workspace/feat: unify inbox contacts and route orders through sales`

## Changes

- Unify Inbox contact and phone management, activity and notification controls; retain native Sales POS handoff and make legacy orders a read-only archive.
- Detailed feature entries in this directory describe the constituent updates.

## Validation

Implementation and runtime evidence is recorded in [the retirement report](../../docs/messaging-legacy-retirement.md) and the feature-specific rollout reports in `docs/`. Commit preparation checked changed Python syntax, XML parsing, JavaScript syntax, Arabic catalog formats and whitespace. No additional runtime or database changes were made while preparing commits.

Files changed:

- `__manifest__.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `models/__init__.py`
- `models/alerts.py`
- `models/contact_phones.py`
- `models/customer_streams.py`
- `models/directory.py`
- `models/orders.py`
- `models/pos_handoff.py`
- `models/session.py`
- `models/workspace.py`
- `security/ir.model.access.csv`
- `security/record_rules.xml`
- `static/src/alerts.xml`
- `static/src/branch_widget.js`
- `static/src/branch_widget.xml`
- `static/src/composer.js`
- `static/src/composer.xml`
- `static/src/contacts.js`
- `static/src/contacts.xml`
- `static/src/feedback.js`
- `static/src/location.js`
- `static/src/location.xml`
- `static/src/login.js`
- `static/src/login.xml`
- `static/src/order_dialog.js`
- `static/src/order_dialog.scss`
- `static/src/order_dialog.xml`
- `static/src/pos_handoff.js`
- `static/src/session_service.js`
- `static/src/templates.js`
- `static/src/templates.xml`
- `static/src/workspace.js`
- `static/src/workspace.scss`
- `static/src/workspace.xml`
- `static/tests/chatter_ui.test.js`
- `static/tests/composer.test.js`
- `static/tests/contact_phones.test.js`
- `static/tests/feedback.test.js`
- `static/tests/location.test.js`
- `static/tests/message.test.js`
- `static/tests/notifications.test.js`
- `static/tests/pos_handoff.test.js`
- `tests/__init__.py`
- `tests/auto_link_concurrency.py`
- `tests/contact_concurrency.py`
- `tests/session_concurrency.py`
- `tests/test_pos_handoff.py`
- `tests/test_pos_runtime.py`
- `tests/test_workspace.py`
- `views/branch_location.xml`
- `views/views.xml`
