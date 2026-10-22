## 4bdbc7d4a375490f886634351da30df94aaa24b0 — emadco88 — 2026-10-01

Original commit subject: ab_sales_delivery_tracking/ FIX Refresh message

User-facing changes:
- Refresh delivery messages through the action service.

Files changed:
- ab_sales_delivery_tracking/__manifest__.py
- ab_sales_delivery_tracking/changelog.d/2026-09-01-initial-delivery-requests.md
- ab_sales_delivery_tracking/static/src/pos/restore_delivery_action_service.js

## Current changes before commit:

- Explicitly allow delivery notification consent and instructions through the shared POS header filter.

Files changed:
- ab_sales_delivery_tracking/changelog.d/2026-10-22-pos-field-allowlists.md
- ab_sales_delivery_tracking/models/ab_sales_pos_api.py
