# Order replies, live updates and attachments

Recent relevant commit:

- Commit: `379f02d013d35e1912b24c3c45d69e06bad229a1`
- Author: Alhassan Hossny
- Date: 2026-11-16
- Original subject: `crm_messaging_gateway/feat: add isolated WhatsApp authentication delivery`
- Previous change: Add isolated WhatsApp authentication delivery.

Current changes before commit:

- Negotiate website v4 independently of v1 order, v2 text and v3 lifecycle exchanges.
- Transfer bounded binary media separately from JSON descriptors and acknowledge incoming events only after all media and the message reach durable callcenter storage.
- Retain immutable outgoing destinations and metadata through retries; report unsupported peers and rejected uploads for review.
- Cover supported media kinds, digests, malformed metadata, delivery failures and legacy exchanges with transport tests.

Files changed:

- README.md
- app/worker.py
- app/website.py
- app/website_media_protocol.py
- app/odoo.py
- tests/test_website_media.py
- changelog.d/2026-11-18-order-replies-media.md
