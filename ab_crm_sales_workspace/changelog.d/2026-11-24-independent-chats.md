# Independent chats

Commit: `f0533de921d699fef304c882290613170b7304b6`
Author: Alhassan Hossny
Date: 2026-11-17
Original commit subject: ab_crm_sales_workspace/feat: add provider-specific reply hooks

- Preserve the existing provider transport and employee preference behavior.

Files changed in that commit:
- `ab_crm_sales_workspace/changelog.d/2026-11-16-website-reply-destination.md`
- `ab_crm_sales_workspace/static/src/workspace.js`

Current changes before commit:
- Show independent chat entries, messages, drafts, read positions and exact notification targets.
- Disable chat joining without changing customer ownership evidence or delivery envelopes.
- Preserve lifecycle closure, retryable delivery and branch/company/customer checks.
- Maintain English/Arabic text, release versions, focused regressions and manual rollback instructions.

Files changed by this task:
- `ab_crm_sales_workspace/README.md`
- `ab_crm_sales_workspace/RELEASE.md`
- `ab_crm_sales_workspace/__manifest__.py`
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
