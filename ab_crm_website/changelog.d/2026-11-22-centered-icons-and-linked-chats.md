# Centered channel icons and combined histories

Commit: `149fb44eebf01cf47e9abe39fc9fa6e6b26e1bfe`
Author: Alhassan Hossny
Date: 2026-11-17
Original commit subject: ab_crm_website/feat: group orders into receive-only customer conversations

- Preserve existing provider ownership and reply hooks.

Current changes before commit:
- Center accessible Support and Orders icon buttons in the conversation header and remove the selector.
- Combine each channel’s messages while showing order references and cards in the timeline.
- Keep channel drafts separate and freeze replies/uploads to the selected message’s exact order or session.
- Preserve per-target read positions, archive preferences, pagination and branch/company isolation.
- Fix mixed-channel contact-link history: batched unread queries no longer assume a singleton channel.
- Preserve combined history when following a verified canonical conversation.
- Retry brief preference-lock conflicts and ignore read markers from a previous channel’s DOM.
- Verify a clean installation and six backend regressions; manually check Brave English desktop and Arabic mobile.

Files changed:
- `ab_crm_website/README.md`
- `ab_crm_website/__manifest__.py`
- `ab_crm_website/models/targets.py`
- `ab_crm_website/static/src/reply.js`
- `ab_crm_website/tests/test_chat_ux.py`
