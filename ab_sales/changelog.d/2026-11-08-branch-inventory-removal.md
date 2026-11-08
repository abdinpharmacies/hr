Current changes before commit:

- Remove the branch sales module's installation dependency on the local inventory ledger.
- Preserve the pending sale-line product-UoM cleanup.

Files changed:

- ab_sales/__manifest__.py
- ab_sales/models/ab_sales_line.py
- ab_sales/changelog.d/2026-11-08-branch-inventory-removal.md

Recent relevant commit:

- Commit: aadda164
- Author: hossam elsheikh
- Date: 2026-11-01
- Original subject: ab_sales/fix: preserve branch store guard after POS sync
- User-facing change: keep branch store access checks after POS synchronization.

Files changed:

- ab_sales/changelog.d/2026-10-18-empty-sales-store-access.md
- ab_sales/models/ab_sales_pos_balance_refresh.py
