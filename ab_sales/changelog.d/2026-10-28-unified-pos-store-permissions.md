## 989570f81a2812a631d1b239e4de5de8b19507d5 - Hossam Elsheikh - 2026-10-27

Original commit subject: ab_sales/update stock

User-facing changes:
- Added central multi-store balance support and refreshed POS stock integrations.
- Updated branch services and POS balance behavior without external database writes.

Files changed:
- ab_sales/BRANCH_API_WORKFLOW.md
- ab_sales/__manifest__.py
- ab_sales/changelog.d/2026-10-27-central-transfer-balances.md
- ab_sales/data/ir_cron.xml
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/__init__.py
- ab_sales/models/ab_product_balance_wizard.py
- ab_sales/models/ab_product_inherit.py
- ab_sales/models/ab_sales_all_store_balance.py
- ab_sales/models/ab_sales_branch_api_client.py
- ab_sales/models/ab_sales_pos_api.py
- ab_sales/models/ab_sales_pos_draft_slots.py
- ab_sales/models/ab_sales_ui_api.py
- ab_sales/models/branch_services.py
- ab_sales/static/src/pos/pos_action.js
- ab_sales/static/src/pos/pos_action_sales_line_balance.xml
- ab_sales/static/src/pos/pos_balance_refresh.js
- ab_sales/static/src/pos/pos_search_product_card.xml
- ab_sales/static/src/pos/store_balance_rows.js
- ab_sales/static/src/pos/store_balance_rows.xml
- ab_sales/views/ab_product_balance_wizard.xml
- ab_sales/views/ab_product_inherit.xml

## Current changes before commit:

- Display every POS-scope store in the store dialog while disabling stores whose branch RPC connection cannot post.
- Preserve connectable-only IDs for selling, drafts, store switching, barcode work, customer operations, returns, and final submission.
- Allow users to recover only their own server-stamped Call Center bills without broadening unrelated branch or bill visibility.
- Show translated permission and connection empty states in the POS store dialog.

Files changed:
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/ab_sales_pos_api.py
- ab_sales/models/ab_sales_pos_draft_slots.py
- ab_sales/models/local_bills.py
- ab_sales/static/src/pos/pos_action.js
- ab_sales/static/src/pos/pos_action.xml
- ab_sales/static/src/pos/pos_barcode_link.js
- ab_sales/changelog.d/2026-10-28-unified-pos-store-permissions.md

Validation:
- Passed the focused employee POS Odoo suite and targeted module upgrade on isolated port 4192.
- Passed Python compilation, XML parsing, JavaScript syntax, both Arabic PO format checks, exported POT coverage, and whitespace checks.
- Preserved the unrelated in-progress central transfer balance changes in this worktree.
