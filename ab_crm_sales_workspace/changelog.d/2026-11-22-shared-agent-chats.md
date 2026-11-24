# Shared callcenter conversations

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
- Remove exclusive reservations, claims on reply, heartbeat/release requests, owner popups and transfer controls.
- Allow all authorized agents to work in the same open chats while preserving verified employee audit and branch/company checks.
- Retry brief website reply transaction contention so independent agents can submit concurrently.

Files changed:
- `ab_crm_sales_workspace/README.md`
- `ab_crm_sales_workspace/__manifest__.py`
- `ab_crm_sales_workspace/models/__init__.py`
- `ab_crm_sales_workspace/models/reservation.py (removed)`
- `ab_crm_sales_workspace/models/workspace.py`
- `ab_crm_sales_workspace/static/src/chat_controls.js`
- `ab_crm_sales_workspace/static/src/chat_controls.xml`
