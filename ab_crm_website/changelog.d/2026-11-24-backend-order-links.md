# Website order staff links

Recent relevant commit: `ced30e39bdfd5a0a9aa400f0523d587a7a3fb490`
Author: Alhassan Hossny
Date: 2026-11-24
Original subject: `ab_crm_website/feat: isolate website order and support targets`

- Separated website order and Support targets while retaining existing mappings.

Files changed:
- `README.md`
- `RELEASE.md`
- `__manifest__.py`
- `changelog.d/2026-11-24-independent-chats.md`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `models/adapter.py`
- `models/targets.py`
- `tests/__init__.py`
- `tests/test_chat_ux.py`
- `tests/test_independent_chats.py`

Current changes before commit:
- Add a manager-configured website origin with server-side write checks and origin validation.
- Add a per-order status link after the collapsed incoming invoice, opening Website Odoo in a new tab.
- Show the footer as a prominent button with bold text: “View Order Status” (Arabic: “عرض حالة الطلب”).
- Use the backend integration route to retain the exact destination across website login.
- Keep stored transport snapshots and historical events unchanged.
- Translate the setting, validation messages and footer into both Arabic catalogs.
- Validate exact-order targeting, configuration access and the Arabic Owl footer.
- Release version 19.0.1.16.1.

Files changed:
- `__manifest__.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `models/__init__.py`
- `models/adapter.py`
- `models/order_link.py`
- `static/src/order.xml`
- `views/views.xml`
- `changelog.d/2026-11-24-backend-order-links.md`
