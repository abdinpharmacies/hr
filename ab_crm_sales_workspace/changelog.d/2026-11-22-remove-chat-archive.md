# Keep all chats in received-message order

> Historical development note. This captures earlier work and is not the current runtime specification; later independent-chat and 2026-11-24 changelogs supersede conflicting controls or deployment details.

Commit: `f0533de921d699fef304c882290613170b7304b6`
Author: Alhassan Hossny
Date: 2026-11-17
Original commit subject: ab_crm_sales_workspace/feat: add provider-specific reply hooks

- Preserve provider reply hooks and historical evidence.

Changes recorded during that development session:
- Remove chat selection, archive/restore controls, archived table, archive state and styling.
- Disable the archived-chat menu and route its preserved action to the normal Inbox.
- Rank inbox rows by received-message time and ID before pagination; outgoing replies no longer promote rows.
- Retain stable cursor loading, access checks and all conversation histories.
- Update both Arabic catalogs for the preserved action now named Inbox.

Files changed:
- `ab_crm_sales_workspace/README.md`
- `ab_crm_sales_workspace/__manifest__.py`
- `ab_crm_sales_workspace/changelog.d/2026-11-22-remove-chat-archive.md`
- `ab_crm_sales_workspace/i18n/ar.po`
- `ab_crm_sales_workspace/i18n/ar_001.po`
- `ab_crm_sales_workspace/models/customer_streams.py`
- `ab_crm_sales_workspace/static/src/chat_controls.js`
- `ab_crm_sales_workspace/static/src/chat_controls.scss`
- `ab_crm_sales_workspace/static/src/chat_controls.xml`
- `ab_crm_sales_workspace/static/src/workspace.scss`
- `ab_crm_sales_workspace/static/src/workspace.xml`
- `ab_crm_sales_workspace/views/views.xml`
