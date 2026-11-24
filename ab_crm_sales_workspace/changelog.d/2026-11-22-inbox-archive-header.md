# Inbox archives and header channels

> Historical development note. This captures earlier work and is not the current runtime specification; later independent-chat and 2026-11-24 changelogs supersede conflicting controls or deployment details.

Commit: `f0533de921d699fef304c882290613170b7304b6`
Author: Alhassan Hossny
Date: 2026-11-17
Original commit subject: ab_crm_sales_workspace/feat: add provider-specific reply hooks

- Preserve the existing provider and customer conversation integration.

Files changed:
- `ab_crm_sales_workspace/changelog.d/2026-11-16-website-reply-destination.md`
- `ab_crm_sales_workspace/static/src/workspace.js`

Changes recorded during that development session:
- Move Support and Orders into the Sales Chatter conversation header.
- Move selection and archive controls to inbox customer rows; remove the Archived inbox entry.
- Expose personal archived chats and restoration through CRM / OMS → Archived chats.
- Preserve draft and conversation selection during inbox archive operations; translate the new menu in both Arabic catalogs.

Files changed:
- `ab_crm_sales_workspace/README.md`
- `ab_crm_sales_workspace/__manifest__.py`
- `ab_crm_sales_workspace/i18n/ar.po`
- `ab_crm_sales_workspace/i18n/ar_001.po`
- `ab_crm_sales_workspace/static/src/chat_controls.js`
- `ab_crm_sales_workspace/static/src/chat_controls.scss`
- `ab_crm_sales_workspace/static/src/chat_controls.xml`
- `ab_crm_sales_workspace/static/src/workspace.xml`
- `ab_crm_sales_workspace/views/views.xml`
