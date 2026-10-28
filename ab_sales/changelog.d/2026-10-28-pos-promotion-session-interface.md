Commit: c08f019c1f82391c2c984bae8421af83d7bb748c
Author: Alhassan Hossny
Date: 2026-10-28T13:14:09+03:00
Subject: ab_sales/feat: enforce POS store scope across sales workflows

User-facing changes:
- Restrict POS sales workflows to stores allowed for the employee session.

Files changed:
- ab_sales/__manifest__.py
- ab_sales/changelog.d/2026-10-27-central-transfer-balances.md
- ab_sales/changelog.d/2026-10-28-unified-pos-store-permissions.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/ab_sales_all_store_balance.py
- ab_sales/models/ab_sales_branch_rpc_config.py
- ab_sales/models/ab_sales_per_day.py
- ab_sales/models/ab_sales_per_day_sync_wizard.py
- ab_sales/models/ab_sales_pos_api.py
- ab_sales/models/ab_sales_pos_draft_slots.py
- ab_sales/models/branch_services.py
- ab_sales/models/local_bills.py
- ab_sales/static/src/pos/pos_action.js
- ab_sales/static/src/pos/pos_action.xml
- ab_sales/static/src/pos/pos_barcode_link.js

Current changes before commit:
- Accept the shared promotion preview arguments in the base POS fallback.

Files changed:
- ab_sales/changelog.d/2026-10-28-pos-promotion-session-interface.md
- ab_sales/models/ab_sales_pos_api.py
