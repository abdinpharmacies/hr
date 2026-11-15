# Per-channel unread badges and reliable read acknowledgement

## Committed baseline

- Commit: `6bb6760bad1da89ccae11122949d0d4d38299bf4`
- Author: `Alhassan Hossny`
- Date: `2026-11-11T11:52:03+02:00`
- Original subject: `ab_crm_sales_workspace/docs: record inbox sales and archive updates`

## Current changes before commit:

- Restore the shared composer send button to the previous paper-plane icon and remove the SVG-only RTL flip rule.
- Show one inbox unread badge per linked channel stream, coloured with the channel palette, with the aggregate row badge kept only as a fallback.
- Prefer the stored stream when it has unread messages, otherwise the first unread stream; highlight the selected stream’s channel icon and row border instead of the row’s representative provider.
- Acknowledge partially visible messages, allow acknowledgement while viewing history, and advance the workspace read position when jumping to the latest message or opening an alert.
- Refresh the unread divider and per-stream badge after acknowledgement without moving a read position backwards.
- Preserve the existing uncommitted contact, notification, read-receipt and branch-location changes recorded in their separate entries.

Files changed:

- `__manifest__.py`
- `static/src/message.js`
- `static/src/workspace.js`
- `static/src/workspace.xml`
- `static/src/workspace.scss`
- `static/tests/chatter_ui.test.js`
- `static/tests/message.test.js`
- `changelog.d/2026-11-11-unread-channel-badges.md`
