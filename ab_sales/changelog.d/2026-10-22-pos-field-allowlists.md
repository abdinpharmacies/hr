## 44610544788824cda1ae98f2a4c777ea12563bc9 — emadco88 — 2026-10-18

Original commit subject: ab_sales/ FIX empty allowed stores

User-facing changes:
- Reject sales without an allowed store and improve POS store selection.

Files changed:
- ab_sales/changelog.d/2026-10-18-empty-sales-store-access.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/ab_sales_header.py
- ab_sales/models/ab_sales_pos_balance_refresh.py
- ab_sales/models/ab_sales_pos_draft_slots.py
- ab_sales/models/ab_sales_ui_api.py
- ab_sales/static/src/pos/pos_action.js

## Current changes before commit:

- Provide separate extensible allowlists for invoice headers and lines, shared by initial submissions and editable retries.
- Build line payloads through an extension method before saving retry snapshots; preserve server-controlled audit and submission fields.

Files changed:
- ab_sales/changelog.d/2026-10-22-pos-field-allowlists.md
- ab_sales/models/ab_sales_pos_api.py
- ab_sales/static/src/pos/pos_action.js
