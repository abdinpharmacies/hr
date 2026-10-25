## a6851efd982ac4d2293997aeefcc9270ab5d2254 — Hossam Elsheikh — 2026-10-20

Original commit subject: ab_sales_delivery_tracking/feat: send delivery consent and instructions through supported branch APIs

User-facing changes:
- Send delivery consent and instructions through supported branch APIs.

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

## Source reference: 5532a237011d3e279035a5479687561dd44c0abe — emadco88 — 2026-10-22

Original commit subject: ab_sales_delivery_tracking/ UPD add the allowd fields via hook

User-facing changes:
- Preserve delivery consent and instructions through submission.

Files changed:
- ab_sales_delivery_tracking/changelog.d/2026-10-22-pos-field-allowlists.md
- ab_sales_delivery_tracking/models/ab_sales_pos_api.py

Adapted to the callcenter branch API workflow; not a whole-branch merge.

## Current changes before commit:

- Allow delivery_notify and delivery_instructions through shared submission filters.
- Retain the existing UI-version check, explicit boolean consent, and required-instructions validation.

Files changed:
- ab_sales_delivery_tracking/changelog.d/2026-10-25-callcenter-pos-field-allowlists.md
- ab_sales_delivery_tracking/models/ab_sales_pos_api.py
