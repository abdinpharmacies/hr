# Order replies, live updates and attachments

Recent relevant commit:

- Commit: `b0095b6521105f026f3de12e4283d402255f28c3`
- Author: Alhassan Hossny
- Date: 2026-11-17
- Original subject: `ab_storefront_callcenter_adapter/fix: allow website selection on new endpoints`
- Previous change: Allow website selection when configuring new endpoints.

Current changes before commit:

- Preserve native attachment ownership tokens and voice metadata through attachment-only sends, history and uncertain retries.
- Add negotiated v4 descriptors, bounded authenticated binary transfers and immutable attachment evidence; keep activation off by default.
- Add five-second tracking chatter updates, manual refresh, owner-only guest tracking capabilities and media rendering without clearing drafts.
- Update both Arabic catalogs and add backend, guest/customer HTTP and polling browser regressions.

Files changed:

- __manifest__.py
- README.md
- media_protocol.py
- models/__init__.py
- models/adapter.py
- models/chat.py
- models/media.py
- controllers/__init__.py
- controllers/chat.py
- controllers/media.py
- controllers/portal.py
- static/src/chat.js
- static/src/native.js
- static/src/native_history.js
- static/src/native_history.xml
- static/src/portal_refresh.js
- static/src/portal_refresh.xml
- views/views.xml
- i18n/ar.po
- i18n/ar_001.po
- tests/test_adapter.py
- changelog.d/2026-11-18-order-replies-media.md
