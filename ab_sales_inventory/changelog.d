Current changes before commit:

- Serialize branch configuration, cashier projections and native unit inputs against concurrent snapshots.
- Add an explicit per-store native sales backend while retaining the existing POS and cashier interfaces.
- Post immutable sales through scoped stock reservations and restore original allocations for returns, including authorized shortage reconciliation.
- Settle native payments and refunds exactly once, record employee-authorized cash counts and prevent raw payment or cash-balance edits.
- Enforce branch/company and employee-session permissions, freeze service classifications and protect units used by posted sales.
- Preserve local promotion and contract pricing/refund calculations without external database access and supply both Arabic catalogs.

Files changed:

- ab_sales_inventory/README.md
- ab_sales_inventory/__init__.py
- ab_sales_inventory/__manifest__.py
- ab_sales_inventory/changelog.d
- ab_sales_inventory/i18n/ar.po
- ab_sales_inventory/i18n/ar_001.po
- ab_sales_inventory/models/__init__.py
- ab_sales_inventory/models/backend.py
- ab_sales_inventory/models/cashier.py
- ab_sales_inventory/models/pos.py
- ab_sales_inventory/models/returns.py
- ab_sales_inventory/models/sale.py
- ab_sales_inventory/security/ir.model.access.csv
- ab_sales_inventory/security/record_rules.xml
- ab_sales_inventory/security/security_groups.xml
- ab_sales_inventory/static/src/returns/native_return.js
- ab_sales_inventory/static/src/returns/native_return.xml
- ab_sales_inventory/views/native_sales.xml

Validation:

- Fresh isolated installation, targeted upgrades, behavior/security checks, translation validation and operational evidence are recorded in `ab_independence_dev_plans/13_phase_1_6_execution.md`.
