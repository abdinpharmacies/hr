# Simple unread notifications and location links

## Committed baseline

- Commit: `6bb6760bad1da89ccae11122949d0d4d38299bf4`
- Author: `Alhassan Hossny`
- Date: `2026-11-11T11:52:03+02:00`
- Original subject: `ab_crm_sales_workspace/docs: record inbox sales and archive updates`

## Current changes before commit:

- Display only “You have n unread messages” in grouped notification popups, using the unread totals for their conversations.
- Remove customer names, destinations, channel labels and message previews from popup text; label each existing conversation action “Open”.
- Extend the reviewed branch picker to WhatsApp with the existing manager-controlled location gate and normal reply eligibility.
- Preserve conversation navigation, grouped alerts, message snapshots and dismissal behavior.
- Show the clickable Google Maps URL instead of raw coordinates on location cards for both channels, with left-to-right URL isolation and wrapping in Arabic layouts.
- Add both Arabic translations, update existing notification and runtime translation assertions, and increment Sales Chatter to 19.0.1.28.0.

Files changed:

- `__manifest__.py`
- `README.md`
- `static/src/session_service.js`
- `static/tests/notifications.test.js`
- `models/branch_location.py`
- `views/branch_location.xml`
- `static/src/workspace.xml`
- `static/src/composer.xml`
- `static/tests/composer.test.js`
- `static/src/location.xml`
- `static/src/location.scss`
- `static/tests/location.test.js`
- `tests/test_workspace.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `changelog.d/2026-11-11-simple-notifications.md`
