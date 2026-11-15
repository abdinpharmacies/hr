# Read receipts, channel loading and animation attachments

## Committed baseline

- Commit: `6bb6760bad1da89ccae11122949d0d4d38299bf4`
- Author: `Alhassan Hossny`
- Date: `2026-11-11T11:52:03+02:00`
- Original subject: `ab_crm_sales_workspace/docs: record inbox sales and archive updates`

## Current changes before commit:

- Queue provider read receipts only after the existing employee-scoped read acknowledgement; retry concurrent read transactions.
- Separate channel navigation from other actions, preserve drafts and reject superseded/session-stale responses. Block composition and acknowledgements while switching.
- Avoid duplicate initial/unchanged refresh requests and lazy-load quoted images without blocking conversation rendering.
- Support GIF selection, private previews and shared MP4 validation, with both Arabic catalogs and navigation tests.
- Preserve the existing uncommitted contact, notification and branch-location changes recorded in their separate entries.

Files changed:

- `README.md`
- `__manifest__.py`
- `changelog.d/2026-11-11-simple-notifications.md`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `models/branch_location.py`
- `models/media.py`
- `models/workspace.py`
- `static/src/composer.xml`
- `static/src/location.scss`
- `static/src/location.xml`
- `static/src/message.js`
- `static/src/message.xml`
- `static/src/session_service.js`
- `static/src/workspace.js`
- `static/src/workspace.xml`
- `static/tests/composer.test.js`
- `static/tests/location.test.js`
- `static/tests/navigation.test.js`
- `static/tests/notifications.test.js`
- `tests/test_workspace.py`
- `views/branch_location.xml`
- `changelog.d/2026-11-11-read-receipts-channel-loading-animations.md`
