# Preserve the legacy archived-chat action as a link to the active Inbox and keep its menu inactive.

Commit: `b4cf60e2dde1d3859dd582dd4f57895b32c89b31`
Author: Alhassan Hossny
Date: 2026-11-24
Original commit subject: ab_crm_sales_workspace/feat: separate chat entries and target notifications

Recent module change:
- separate chat entries and target notifications.

Files changed in that commit:
- `ab_crm_sales_workspace/README.md`
- `ab_crm_sales_workspace/RELEASE.md`
- `ab_crm_sales_workspace/__manifest__.py`
- `ab_crm_sales_workspace/changelog.d/2026-11-24-independent-chats.md`
- `ab_crm_sales_workspace/i18n/ar.po`
- `ab_crm_sales_workspace/i18n/ar_001.po`
- `ab_crm_sales_workspace/models/alerts.py`
- `ab_crm_sales_workspace/models/customer_streams.py`
- `ab_crm_sales_workspace/models/workspace.py`
- `ab_crm_sales_workspace/static/src/chat_controls.js`
- `ab_crm_sales_workspace/static/src/chat_controls.scss`
- `ab_crm_sales_workspace/static/src/chat_controls.xml`
- `ab_crm_sales_workspace/static/src/session_service.js`
- `ab_crm_sales_workspace/static/src/workspace.js`
- `ab_crm_sales_workspace/static/src/workspace.xml`
- `ab_crm_sales_workspace/static/tests/notifications.test.js`

Current changes before commit:
- Preserve the legacy archived-chat action as a link to the active Inbox and keep its menu inactive.
- Include both Arabic catalogs for existing chatter controls and the retained navigation records.
- Correct the README to describe independent website entries and the single header indicator.

Files changed:
- `ab_crm_sales_workspace/views/views.xml`
- `ab_crm_sales_workspace/i18n/ar.po`
- `ab_crm_sales_workspace/i18n/ar_001.po`
- `ab_crm_sales_workspace/README.md`
- `ab_crm_sales_workspace/changelog.d/2026-11-24-legacy-inbox-navigation.md`
