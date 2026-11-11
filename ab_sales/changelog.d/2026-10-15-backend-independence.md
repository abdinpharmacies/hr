## b84b51e96616b2b6f20482e207fdbf78686e41ba — emadco88 — 2026-10-14

Original commit subject: ab_sales/ FIX preserve balances on refresh failure and add per-product retry controls

User-facing changes:
- Preserve cached balances on refresh failure and add per-product retry controls.

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

## Current changes before commit:

- Own backend reads, routing, customer operations, native submission delegation and reconciliation in five inherited helper files.
- Reuse native POS balance refresh/cache with explicit committed API reads; retain cache values on failure.
- Share branch-filtered invoice-status and daily-sales query execution with existing scheduled callers.
- Preserve ordinary POS dispatch and add Arabic translations for moved/new backend messages.

Files changed:
- ab_sales/changelog.d/2026-10-15-backend-independence.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/__init__.py
- ab_sales/models/ab_sales_header.py
- ab_sales/models/ab_sales_header_backend.py
- ab_sales/models/ab_sales_inventory_backend.py
- ab_sales/models/ab_sales_per_day.py
- ab_sales/models/ab_sales_per_day_backend.py
- ab_sales/models/ab_sales_pos_backend.py
- ab_sales/models/ab_sales_pos_balance_refresh.py
- ab_sales/models/ab_sales_return_backend.py

Validation:
- 27 mocked backend/transport checks passed outside production addon packages.
- Development database `abdin_old_pos19`: targeted sales upgrade followed by Branch API upgrade passed.
- Python registry loading, Arabic runtime menu rendering and translation format checks passed.
- External posting was mocked; live end-to-end posting remains deployment acceptance work.
