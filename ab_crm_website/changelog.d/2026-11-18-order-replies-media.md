# Order replies, live updates and attachments

Recent relevant commit:

- Commit: `149fb44eebf01cf47e9abe39fc9fa6e6b26e1bfe`
- Author: Alhassan Hossny
- Date: 2026-11-17
- Original subject: `ab_crm_website/feat: group orders into receive-only customer conversations`
- Previous change: Group received website orders into customer conversations.

Current changes before commit:

- Route selected order cards and website messages through reply arrows and the cancellable quote; validate membership, destination and scope on the server.
- Keep explicit targets and stable submission UUIDs through retries, reject changed submissions, and retain the latest eligible incoming default.
- Reuse conversation media components in a website-scoped composer, store complete multi-file messages atomically, and negotiate v4 private media delivery.
- Allow manager-reviewed same-token retries after media capability becomes available.
- Update both Arabic catalogs and cover forged targets, media staging, idempotency and English/Arabic workspace controls.

Files changed:

- __manifest__.py
- README.md
- protocol.py
- media_protocol.py
- models/__init__.py
- models/adapter.py
- models/media.py
- controllers/adapter.py
- views/views.xml
- static/src/reply.js
- static/src/order.xml
- i18n/ar.po
- i18n/ar_001.po
- tests/test_contact_groups.py
- changelog.d/2026-11-18-order-replies-media.md
