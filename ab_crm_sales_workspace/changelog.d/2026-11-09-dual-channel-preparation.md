# Dual-channel preparation

Previous module commit: `d5d7bd8fa7febb0defe905e9670dfb1b86415cfb`
Author: Alhassan Hossny
Date: 2026-11-09T10:41:10+02:00
Original subject: ab_crm_sales_workspace/docs: document chatter updates and validation

Changes included in implementation commit `9dc09536`:

- Group the inbox by scoped customer and retain independent streams, unread counts and employee drafts.
- Provide manager preview/confirm customer linking with conflict review and protected audit.
- Show authorized orders across linked streams without changing their origin or snapshots.
- Exclude historical imports from new alerts and unread counts; preserve chronological paging.
- Preserve the existing composer, location-language and latest-message changes recorded separately.

Verification: see `docs/omnichannel-callcenter-validation.md` in the checkout. Live deployment is gated separately.

Files changed:
- `__manifest__.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `models/__init__.py`
- `models/alerts.py`
- `models/customer_streams.py`
- `models/workspace.py`
- `static/src/composer.js`
- `static/src/composer.xml`
- `static/src/location.scss`
- `static/src/workspace.js`
- `static/src/workspace.xml`
- `static/tests/composer.test.js`
- `static/tests/message.test.js`
- `tests/test_workspace.py`
- `changelog.d/2026-11-09-dual-channel-preparation.md`
