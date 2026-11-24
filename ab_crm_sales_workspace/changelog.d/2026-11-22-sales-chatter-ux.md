# Sales Chatter conversation UX

> Historical development note. This captures earlier work and is not the current runtime specification; later independent-chat and 2026-11-24 changelogs supersede conflicting controls or deployment details.

Commit: `f0533de921d699fef304c882290613170b7304b6`
Author: Alhassan Hossny
Date: 2026-11-17
Original commit subject: ab_crm_sales_workspace/feat: add provider-specific reply hooks

- Add provider-specific reply hooks to Sales Chatter.

Files changed:
- `ab_crm_sales_workspace/changelog.d/2026-11-16-website-reply-destination.md`
- `ab_crm_sales_workspace/static/src/workspace.js`

Changes recorded during that development session:
- Add Support/Orders controls, isolated drafts, personal archive selection and restore.
- Reserve website conversations on the first accepted reply; enforce shared-login employee ownership, versioned tab leases, expiry and audited manager transfers.
- Order the customer inbox by accepted message activity before stable cursor pagination; retain selection and scroll during refresh.
- Carry verified employee context through notifications and keep English/Arabic controls aligned.

Files changed:
- `ab_crm_sales_workspace/README.md`
- `ab_crm_sales_workspace/__manifest__.py`
- `ab_crm_sales_workspace/i18n/ar.po`
- `ab_crm_sales_workspace/i18n/ar_001.po`
- `ab_crm_sales_workspace/models/__init__.py`
- `ab_crm_sales_workspace/models/alerts.py`
- `ab_crm_sales_workspace/models/customer_streams.py`
- `ab_crm_sales_workspace/models/reservation.py`
- `ab_crm_sales_workspace/static/src/chat_controls.js`
- `ab_crm_sales_workspace/static/src/chat_controls.xml`
- `ab_crm_sales_workspace/static/src/workspace.js`
