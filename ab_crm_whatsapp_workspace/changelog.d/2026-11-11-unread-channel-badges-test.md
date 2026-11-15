# Shared unread badge and send icon test adaptation

## Committed baseline

- Commit: `2fd4a75487b54674044ed0de9918bcfe8f81fa9a`
- Author: `Alhassan Hossny`
- Date: `2026-11-11T11:52:09+02:00`
- Original subject: `ab_crm_whatsapp_workspace/docs: record reception and historical receipt updates`

## Current changes before commit:

- Update the grouped customer inbox test to expect one unread badge per channel and the selected stream’s channel highlight.
- Update the shared composer test to expect the restored paper-plane send icon.
- No WhatsApp runtime behaviour or manifest version changes.

Files changed:

- `static/tests/drafts.test.js`
- `changelog.d/2026-11-11-unread-channel-badges-test.md`
