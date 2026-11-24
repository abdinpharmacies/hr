# Website order staff links

Recent relevant commit: `ef86d19a71baefcb3149a7e2fb6f9ed87444c1a4`
Author: Alhassan Hossny
Date: 2026-11-23
Original subject: `ab_storefront_callcenter_adapter/fix: isolate delivery from bridge health`

- Kept accepted website exchanges independent of bridge availability.

Files changed:
- `__manifest__.py`
- `changelog.d/2026-11-23-bridge-delivery-isolation.md`
- `controllers/media.py`
- `models/adapter.py`
- `models/chat.py`
- `tests/test_adapter.py`

Current changes before commit:
- Add an authenticated source/order UUID route to the website Ecommerce Orders screen for the exact order.
- Add an `/odoo/` integration route so existing backend login preserves the order destination; keep the previous route as an alias.
- Preserve staff sales access and record rules; deny portal users and inaccessible orders.
- Validate login return, exact orders, staff access and company isolation.
- Release version 19.0.1.5.4. No new source UI strings require translations.

Files changed:
- `__manifest__.py`
- `controllers/portal.py`
- `changelog.d/2026-11-24-backend-order-links.md`
