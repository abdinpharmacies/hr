# Fixed inbox controls

> Historical development note. This captures earlier work and is not the current runtime specification; later independent-chat and 2026-11-24 changelogs supersede conflicting controls or deployment details.

Commit: `f0533de921d699fef304c882290613170b7304b6`
Author: Alhassan Hossny
Date: 2026-11-17
Original commit subject: ab_crm_sales_workspace/feat: add provider-specific reply hooks

- Preserve the existing provider integration and reply hooks.

Files changed:
- `ab_crm_sales_workspace/changelog.d/2026-11-16-website-reply-destination.md`
- `ab_crm_sales_workspace/static/src/workspace.js`

Changes recorded during that development session:
- Place Select chats and Archive selected beside the inbox action controls.
- Keep the inbox heading, action controls and search fixed while only saved contacts and chat rows scroll.
- Keep enough space for the chat list below the fixed controls on mobile.
- Preserve existing English source labels and both Arabic catalogs.
- Validate the local targeted upgrade and manual Brave desktop/mobile scrolling, guest departure and CRM / OMS archive/restore.

Files changed:
- `ab_crm_sales_workspace/__manifest__.py`
- `ab_crm_sales_workspace/static/src/chat_controls.xml`
- `ab_crm_sales_workspace/static/src/workspace.xml`
- `ab_crm_sales_workspace/static/src/workspace.scss`
