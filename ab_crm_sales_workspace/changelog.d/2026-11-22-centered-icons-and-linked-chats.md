# Centered channel icons and combined histories

> Historical development note. This captures earlier work and is not the current runtime specification; later independent-chat and 2026-11-24 changelogs supersede conflicting controls or deployment details.

Commit: `f0533de921d699fef304c882290613170b7304b6`
Author: Alhassan Hossny
Date: 2026-11-17
Original commit subject: ab_crm_sales_workspace/feat: add provider-specific reply hooks

- Preserve existing provider ownership and reply hooks.

Changes recorded during that development session:
- Center accessible Support and Orders icon buttons in the conversation header and remove the selector.
- Combine each channel’s messages while showing order references and cards in the timeline.
- Keep channel drafts separate and freeze replies/uploads to the selected message’s exact order or session.
- Preserve per-target read positions, archive preferences, pagination and branch/company isolation.
- Fix mixed-channel contact-link history: batched unread queries no longer assume a singleton channel.
- Preserve combined history when following a verified canonical conversation.
- Retry brief preference-lock conflicts and ignore read markers from a previous channel’s DOM.
- Verify a clean installation and six backend regressions; manually check Brave English desktop and Arabic mobile.

Files changed:
- `ab_crm_sales_workspace/README.md`
- `ab_crm_sales_workspace/__manifest__.py`
- `ab_crm_sales_workspace/static/src/chat_controls.js`
- `ab_crm_sales_workspace/static/src/chat_controls.xml`
- `ab_crm_sales_workspace/static/src/chat_controls.scss`
