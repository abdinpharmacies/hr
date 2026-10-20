Commit: 4bdbc7d4a375490f886634351da30df94aaa24b0
Author: emadco88 <emadco88@gmail.com>
Date: 2026-10-01T18:30:10+03:00
Subject: ab_sales_delivery_tracking/ FIX Refresh message

User-facing changes:
- Refresh delivery messages on pos19.

Files changed:
- ab_sales_delivery_tracking/__manifest__.py
- ab_sales_delivery_tracking/changelog.d/2026-09-01-initial-delivery-requests.md
- ab_sales_delivery_tracking/static/src/pos/restore_delivery_action_service.js

Current changes before commit:
- Add optional callcenter delivery consent and instructions through the branch API.
- Negotiate branch delivery capability; ordinary sales omit unsupported optional fields.
- Keep submitted payloads frozen and leave notification sending on the branch; maintain both Arabic catalogs.

Files changed:
- ab_sales_delivery_tracking/__init__.py
- ab_sales_delivery_tracking/__manifest__.py
- ab_sales_delivery_tracking/changelog.d/2026-10-20-callcenter-parity.md
- ab_sales_delivery_tracking/i18n/ar.po
- ab_sales_delivery_tracking/i18n/ar_001.po
- ab_sales_delivery_tracking/models/__init__.py
- ab_sales_delivery_tracking/models/ab_sales_pos_api.py
- ab_sales_delivery_tracking/models/delivery_fields.py
- ab_sales_delivery_tracking/static/src/pos/delivery_notification.js
- ab_sales_delivery_tracking/static/src/pos/delivery_notification.xml
- ab_sales_delivery_tracking/views/pos_action.xml
