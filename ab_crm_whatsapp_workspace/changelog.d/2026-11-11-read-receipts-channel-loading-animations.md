# Read receipts, channel loading and animation attachments

## Committed baseline

- Commit: `2fd4a75487b54674044ed0de9918bcfe8f81fa9a`
- Author: `Alhassan Hossny`
- Date: `2026-11-11T11:52:09+02:00`
- Original subject: `ab_crm_whatsapp_workspace/docs: record reception and historical receipt updates`

## Current changes before commit:

- Accept GIF inputs up to 10 MB for gateway video conversion while preserving stored originals.
- Use the shared MP4 validator and keep the composer disabled throughout navigation.
- Use prefetched authorized message history for reaction eligibility instead of one lookup per displayed message.
- Test receipt settings, deduplication, expiry, account/employee isolation and both channel-switch directions.
- Preserve the existing uncommitted contact, notification and branch-location changes recorded in their separate entries.

Files changed:

- `__manifest__.py`
- `changelog.d/2026-11-11-whatsapp-branch-locations.md`
- `models/account.py`
- `models/history.py`
- `models/media.py`
- `models/workspace.py`
- `static/src/templates.xml`
- `static/tests/drafts.test.js`
- `tests/test_bridge.py`
- `changelog.d/2026-11-11-read-receipts-channel-loading-animations.md`
