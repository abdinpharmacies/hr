Current changes before commit:

- Attribute every new local payment or refund to the employee authenticated by the PIN session while retaining the service user only for compatibility.
- Restore stock exactly once when an approved local return is sent to Cashier and reject refund settlement when that restoration is incomplete.
- Keep cashier settlement payment-only so sale approval is the sole sale deduction and refund collection never creates an additional stock movement.
- Show the operational employee in local payment history and maintain both Arabic catalogs from the exported Odoo template.
- Allow the cancellation wizard to open before its mandatory reason is entered, then validate the reason on confirmation.
- Permit audited cancellation of legacy pending native invoices only when no stock or payment activity exists; retain normal reversal for current approvals and reject ambiguous historical stock activity.

Validation: The targeted three-module upgrade passed. The 54-assertion rollback lifecycle verified one stock deduction on sale approval, no stock movement on collection, one restoration on return submission, no stock movement on refund settlement, PIN employee attribution, branch isolation and complete fingerprint restoration with every E-Plus connector blocked. A targeted `ab_sales_inventory` upgrade and rollback-only validation on legacy invoice N-18942 confirmed that the unsaved cancellation dialog keeps the reason mandatory, creates no stock or payment effect, and restores the original pending state after rollback. Python, XML, Arabic catalog and whitespace checks passed, and the running Odoo process was gracefully reloaded.

Files changed:

- ab_sales_inventory/README.md
- ab_sales_inventory/__manifest__.py
- ab_sales_inventory/changelog.d
- ab_sales_inventory/i18n/ar.po
- ab_sales_inventory/i18n/ar_001.po
- ab_sales_inventory/models/backend.py
- ab_sales_inventory/models/returns.py
- ab_sales_inventory/views/native_sales.xml

Earlier uncommitted changes:

- Deduct local stock during sale approval, using exact unit conversion, matching-price FEFO source allocation and one atomic pending transition.
- Record immutable allocations, sold-without-stock shortages and one-time cancellation reversals without company-based sales scope.
- Keep cashier settlement payment-only, reject incomplete legacy pending snapshots and preserve request/payment idempotency.
- Add administrator-only pending cancellation, branch-scoped shortage reporting and cancelled-state protections.
- Separate cashier cash-count models and employee cashier access into optional addons.
- Replace hardcoded cashier Arabic labels with English source strings and maintain both Arabic catalogs.
- Preserve the authenticated POS employee on sold-without-stock audit rows.
- Keep branch-assigned payment and cashier-balance access stable when ordinary users switch active companies, while retaining company scope for managers.
- Honor Sales Manager access before applying lower inventory-user store restrictions in native POS and cashier flows.

Validation: A fresh isolated installation passed with E-Plus and cashier modules absent, followed by successful optional cashier/employee-bridge installation and targeted upgrades. Rollback-only suites passed 33 core approval/inventory/cancellation checks and 27 cashier/refund/security checks. Six independent-cursor concurrency checks passed for oversell prevention, exact exhaustion, serialization retry, and settlement-versus-cancellation. Server validation compiled 122 English/Arabic views, resolved 23 actions, verified runtime translations, and compiled 24 target JavaScript files plus OWL templates. The named-user Cash Management Playwright suite passed ten allowed branch cases, five denied-store cases and one complete rollback-only native sale lifecycle.

Files changed:

- ab_sales_inventory/README.md
- ab_sales_inventory/__manifest__.py
- ab_sales_inventory/changelog.d
- ab_sales_inventory/i18n/ar.po
- ab_sales_inventory/i18n/ar_001.po
- ab_sales_inventory/models/__init__.py
- ab_sales_inventory/models/allocation.py
- ab_sales_inventory/models/backend.py
- ab_sales_inventory/models/cancel_wizard.py
- ab_sales_inventory/models/pos.py
- ab_sales_inventory/models/sale.py
- ab_sales_inventory/security/ir.model.access.csv
- ab_sales_inventory/security/record_rules.xml
- ab_sales_inventory/security/security_groups.xml
- ab_sales_inventory/views/native_cancel_wizard.xml
- ab_sales_inventory/views/native_sales.xml

836e082b | Alhassan Hossny | 2026-10-19 | ab_sales_inventory/fix: defer stock posting to cashier and repair native POS flows

- Deferred native stock posting to cashier settlement and repaired native POS, return and price-search flows.
- Added isolated and live validation evidence for the previous cashier-posting design.

Files changed:

- ab_sales_inventory/README.md
- ab_sales_inventory/changelog.d
- ab_sales_inventory/models/allocation.py
- ab_sales_inventory/models/backend.py
- ab_sales_inventory/models/cashier.py
- ab_sales_inventory/models/pos.py
- ab_sales_inventory/models/returns.py
- ab_sales_inventory/models/sale.py
- ab_sales_inventory/security/record_rules.xml
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
