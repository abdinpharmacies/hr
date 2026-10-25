## ea1778c8c03573db14b6d343382587a9fb0e3fdd — Hossam Elsheikh — 2026-10-22

Original commit subject: ui/ux improvments

User-facing changes:
- Improve callcenter submission feedback and expose bill return status.

Files changed:
- ab_sales/__manifest__.py
- ab_sales/changelog.d/2026-10-22-bill-return-status.md
- ab_sales/changelog.d/2026-10-22-callcenter-pos-feedback.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/__init__.py
- ab_sales/models/ab_sales_branch_api_client.py
- ab_sales/models/ab_sales_pos_draft_slots.py
- ab_sales/models/ab_sales_ui_api_bill_wizard_inherit.py
- ab_sales/models/bill_return_status.py
- ab_sales/static/src/bill_wizard/bill_wizard_action.xml
- ab_sales/static/src/bill_wizard/has_returns_badge.js
- ab_sales/static/src/bill_wizard/has_returns_badge.xml
- ab_sales/static/src/pos/pos_action.js
- ab_sales/static/src/pos/pos_action.scss
- ab_sales/static/src/pos/pos_action.xml
- ab_sales/static/src/pos/zz_pos_replication_manual.xml
- ab_sales/views/local_bill_views.xml

## Source reference: 13917dabcb39987ee42689f82b7b36852c73ca39 — emadco88 — 2026-10-22

Original commit subject: ab_sales/ UPD allowed fields hook

User-facing changes:
- Make POS invoice and line inputs explicitly extensible and build frontend submission lines through an extension method.

Files changed:
- ab_sales/changelog.d/2026-10-22-pos-field-allowlists.md
- ab_sales/models/ab_sales_pos_api.py
- ab_sales/static/src/pos/pos_action.js

Adapted to the callcenter branch API workflow; not a whole-branch merge.

## Current changes before commit:

- Adapt POS19 header and line allowlists to local invoice creation, pre-attempt replacement, and branch API serialization.
- Rebuild employee ownership and device audit fields from the validated session while retaining the selected salesperson separately.
- Keep existing frozen requests unchanged on retry, including administrator-form retries after the original employee session expires.
- Build submitted lines through an extension method, preserving shortage reasons and per-line addon values.
- Keep callcenter API-only: 370c33c3d90acba569dae8a79c4bbe73cb0b5ea9 (selected salesperson attribution) and d5b4f13a187ee4fa91f8480aa091da77489a400f (preserve original salesperson on return) remain branch-server prerequisites. No direct B-Connect posting code is imported.

Files changed:
- ab_sales/changelog.d/2026-10-25-callcenter-pos-field-allowlists.md
- ab_sales/models/ab_sales_branch_api_client.py
- ab_sales/models/ab_sales_pos_api.py
- ab_sales/models/local_bills.py
- ab_sales/static/src/pos/pos_action.js
