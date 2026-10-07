## 3db5d596c9429ff082c3fe9b0466692b945f788f - emadco88 - 2026-07-28

Original commit subject: INIT commit pos19

User-facing changes:
- Added the cashier window for pending sales and returns, invoice details, and saving bills to E-Plus.
- Added cashier closing and payment-wallet handling.

Files changed:
- ab_sales_cashier/__init__.py
- ab_sales_cashier/__manifest__.py
- ab_sales_cashier/models/__init__.py
- ab_sales_cashier/models/ab_sales_cashier_api.py
- ab_sales_cashier/models/ab_sales_cashier_close_wizard.py
- ab_sales_cashier/security/ir.model.access.csv
- ab_sales_cashier/static/src/cashier/cashier_action.js
- ab_sales_cashier/static/src/cashier/cashier_action.scss
- ab_sales_cashier/static/src/cashier/cashier_action.xml
- ab_sales_cashier/tests/__init__.py
- ab_sales_cashier/tests/test_cashier_api.py
- ab_sales_cashier/views/cashier_action.xml
- ab_sales_cashier/views/cashier_close_wizard.xml

## Current changes before commit:

User-facing changes:
- Mark Odoo bills Saved through the protected sales submission workflow after successful cashier saves, preventing them from remaining Pending on refresh.
- Reconcile Odoo when E-Plus reports an invoice already saved, allowing retries to repair local Pending status without changing E-Plus posting logic.
- Preserve store and invoice filters, cashier API responses, and existing return behavior.

Validation:
- Targeted cashier install/upgrade passed in isolated database `codex_sales_recovery_20261007` with promo, contract, and employee-access extensions installed.
- External connections were blocked in the regression harness; mocked Saved and Already Saved responses reconciled real token-protected Odoo bills and removed them from subsequent Pending queries.
- Repeated saves, cross-branch invoice isolation, legacy invoices, missing invoices, preserved Unknown status, failed/invalid saves, return response compatibility, cashier access denial, and manual status-write protection passed.
- Test fixtures were rolled back. No production or E-Plus transactions were posted.
- No user-facing strings changed; both Arabic catalogs require no additions.
- Python syntax and whitespace diff checks passed.

Files changed:
- ab_sales_cashier/models/ab_sales_cashier_api.py
- ab_sales_cashier/changelog.d/2026-10-07-cashier-status-sync.md
