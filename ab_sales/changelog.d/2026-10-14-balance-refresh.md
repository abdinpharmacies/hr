## b7584edd9e31bce6a1059665677c5cf62885e865 - emadco88 - 2026-10-12

Original commit subject: ab_sales/ fix multi-tab flickering with selective draft restoration

User-facing changes:
- Keep per-tab invoice workspaces and restore drafts selectively.

Files changed:
- ab_sales/changelog.d/2026-10-12-draft-slots.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/ab_sales_pos_draft_slots.py
- ab_sales/static/src/pos/pos_action.js
- ab_sales/static/src/pos/pos_action.xml

## Current changes before commit:

- Limit live branch balance refreshes to a 3-second connection timeout and a 5-second timeout per query without reconnect/replay.
- Preserve cached balances and prices when reads fail or return malformed/incomplete data; return an empty result on failure without replacing cached values.
- Keep the previous numeric balance in red after any refresh failure, with an English/Arabic explanation; never replace it with Unknown or a fabricated zero.
- Add a per-product branch refresh icon on POS/Add Products cards and invoice lines; disable it and show a spinner during the request, without triggering product selection.
- Ignore obsolete branch/search results and refresh responses and older overlapping refresh results; retain unavailable state in draft serialization.

Files changed:
- ab_sales/changelog.d/2026-10-14-balance-refresh.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/ab_sales_pos_balance_refresh.py
- ab_sales/static/src/add_products/add_products_action.js
- ab_sales/static/src/add_products/add_products_action.xml
- ab_sales/static/src/add_products/product_card.xml
- ab_sales/static/src/pos/pos_action.js
- ab_sales/static/src/pos/pos_action.xml
- ab_sales/static/src/pos/pos_action_sales_line_balance.xml
- ab_sales/static/src/pos/pos_balance_refresh.js
