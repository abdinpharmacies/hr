# Inbox targets and archive table

> Historical development note. This captures earlier work and is not the current runtime specification; later independent-chat and 2026-11-24 changelogs supersede conflicting controls or deployment details.

Commit: `f0533de921d699fef304c882290613170b7304b6`
Author: Alhassan Hossny
Date: 2026-11-17
Original commit subject: ab_crm_sales_workspace/feat: add provider-specific reply hooks

- Preserve existing provider ownership and reply behavior.

Changes recorded during that development session:
- Render Select chats and Archive selected as accessible icon buttons matching the inbox actions.
- Replace the archived chatter workspace with a table and read-only history, with View and Restore actions.
- Keep archive refresh independent of active-conversation selection and read acknowledgements.
- Include website aliases in reviewed unlink previews through a module extension point.
- Preserve Arabic translations and add Actions/View terms in both catalogs.

Files changed:
- `ab_crm_sales_workspace/__manifest__.py`
- `ab_crm_sales_workspace/models/customer_streams.py`
- `ab_crm_sales_workspace/static/src/chat_controls.js`
- `ab_crm_sales_workspace/static/src/chat_controls.xml`
- `ab_crm_sales_workspace/static/src/chat_controls.scss`
- `ab_crm_sales_workspace/i18n/ar.po`
- `ab_crm_sales_workspace/i18n/ar_001.po`
- `ab_crm_sales_workspace/changelog.d/2026-11-22-inbox-targets-and-archive-table.md`
