Current changes before commit:

- Return the current pending-invoice list contract from the native cashier adapter, fixing tuple/list concatenation when sales and returns are combined.

- Accept and forward minimum/maximum product-search prices; reuse core price validation and rounded matching for native searches.
- Read native stock and balance metadata locally, including blank product searches.
- Permit native activation with historical legacy drafts while blocking their SQL reconnect/repost.
- Fix native cash-count views failing in XML development mode by preserving leading architecture whitespace.
- Keep draft and submitted sale lines out of inventory; allocate source stock only at cashier settlement.
- Use the current cumulative movement API with one immutable allocation per source, preserving source-price preference.
- Post stock and payment atomically; reject insufficient stock and prevent duplicate sale/refund effects.
- Connect native returns and pending cashier lists to the current sales workflow guards and inventory role.
- Add company/branch rules for allocations and both Arabic translations; update operator documentation.

Validation: Earlier isolated validation passed 59 workflow/security checks and 4 concurrency checks. The authorized live cutover on rip_bconnect activated stores 29 and 140 and passed 46 full-cycle checks, 4 local-lock concurrency checks, 48 English/Arabic view checks and 6 price-search cases. The live process was gracefully reloaded to activate the repair. Cash-count records remain separate from the pending shared-shift/treasury/handover workflow.

Files changed:

- ab_sales_inventory/README.md
- ab_sales_inventory/__manifest__.py
- ab_sales_inventory/changelog.d
- ab_sales_inventory/i18n/ar.po
- ab_sales_inventory/i18n/ar_001.po
- ab_sales_inventory/models/__init__.py
- ab_sales_inventory/models/allocation.py
- ab_sales_inventory/models/backend.py
- ab_sales_inventory/models/cashier.py
- ab_sales_inventory/models/pos.py
- ab_sales_inventory/models/returns.py
- ab_sales_inventory/models/sale.py
- ab_sales_inventory/security/ir.model.access.csv
- ab_sales_inventory/security/record_rules.xml
- ab_sales_inventory/security/security_groups.xml
- ab_sales_inventory/views/native_sales.xml

620bec92 | Alhassan Hossny | 2026-10-18 | feat(ab_sales_inventory): add native POS stock, cashier payments and refunds

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
