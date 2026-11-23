# Inbox targets and archive table

Commit: `149fb44eebf01cf47e9abe39fc9fa6e6b26e1bfe`
Author: Alhassan Hossny
Date: 2026-11-17
Original commit subject: ab_crm_website/feat: group orders into receive-only customer conversations

- Preserve existing provider ownership and reply behavior.

Current changes before commit:
- Clear open-history target filters from linked-stream inbox summaries to prevent Invalid website target errors.
- Include authorized customer-linked website aliases in reviewed unlinking, preserving immutable history and canonical references.
- Test distinct website streams, exact target isolation, link/unlink/relink, hidden aliases and unauthorized unlinking.

Files changed:
- `ab_crm_website/__manifest__.py`
- `ab_crm_website/models/targets.py`
- `ab_crm_website/models/adapter.py`
- `ab_crm_website/tests/test_chat_ux.py`
- `ab_crm_website/changelog.d/2026-11-22-inbox-targets-and-archive-table.md`
