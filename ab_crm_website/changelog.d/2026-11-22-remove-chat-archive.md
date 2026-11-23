# Keep all chats in received-message order

Commit: `149fb44eebf01cf47e9abe39fc9fa6e6b26e1bfe`
Author: Alhassan Hossny
Date: 2026-11-17
Original commit subject: ab_crm_website/feat: group orders into receive-only customer conversations

- Preserve provider reply hooks and historical evidence.

Current changes before commit:
- Remove archive/restore ORM methods, preference fields and target visibility filters.
- Keep all targets and ended guest history in normal channel timelines, with private read positions preserved.
- Sort website inbox activity by received messages across canonical aliases, excluding lifecycle notices and outgoing replies.
- Replace archive regressions with all-history visibility, removed-API, permission and received-order tests.

Files changed:
- `ab_crm_website/README.md`
- `ab_crm_website/__manifest__.py`
- `ab_crm_website/changelog.d/2026-11-22-remove-chat-archive.md`
- `ab_crm_website/models/targets.py`
- `ab_crm_website/tests/test_chat_ux.py`
