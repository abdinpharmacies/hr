## a394a6c0867d695ec54b2a0984a3b9342590ac8b - emadco88 - 2026-10-18

Original commit subject: ab_sales/ FIX empty allowed stores

User-facing changes:
- Permit active sales branches when no explicit Allowed Sales Stores restriction is configured; retain explicit branch restrictions.

Files changed:
- ab_sales/models/ab_sales_pos_balance_refresh.py

## Current changes before commit:

- Refresh inventory JSON and price/quantity badges through both automatic invoice-line inventory refresh and the small manual balance refresh button.
- Reuse the branch-filtered, committed batch-stock reader on the existing timeout-controlled connection and the existing badge-building rules.
- Preserve the cashier's selected selling price and quantity; convert refreshed base badges to the selected unit once.
- Retain previous badges on refresh failure and omit older detail snapshots when the balance cache has a newer timestamp.
- Replace depleted batch badges after successful empty-stock reads, retaining the default-price badge.
- Reject responses for removed lines, changed products/branches/bills, and superseded requests.
- Treat inventory JSON as transient display data in both browser and server draft comparisons, preventing refresh-only cashier revisions.
- Preserve numeric balance API compatibility. No new user-facing strings; Arabic translation files need no changes.

Files changed:
- ab_sales/models/ab_sales_pos_api.py
- ab_sales/models/ab_sales_pos_balance_refresh.py
- ab_sales/models/ab_sales_pos_draft_slots.py
- ab_sales/static/src/pos/pos_action.js
- ab_sales/static/src/pos/pos_balance_refresh.js
- ab_sales/changelog.d/2026-10-27-refresh-price-badges.md

Validation:
- Passed executable Node checks against production refresh/controller methods: automatic/manual paths, preserved selected price/quantity, single unit conversion, failures, empty stock, removed lines, branch/bill/product/request changes, overlapping responses, and unpriced products.
- Passed Python checks against production methods with stubbed ORM/SQL: grouped prices, empty inventory, cross-branch rejection before cache writes, numeric API compatibility, newer-cache preservation, connection failure, and quantity/priced rules.
- Passed Python AST parsing, JavaScript syntax checks, and git diff whitespace checks.
- Targeted Odoo upgrade/runtime verification could not run: local PostgreSQL peer authentication rejects odoo19, configured TCP password is absent, and sudo requires a password. No live branch or production database writes were performed.
- Development checks are outside the addon at /tmp/test_ab_sales_refresh_badges.py and /tmp/test_ab_sales_refresh_badges.mjs; no test scaffolding was added to the production package.
