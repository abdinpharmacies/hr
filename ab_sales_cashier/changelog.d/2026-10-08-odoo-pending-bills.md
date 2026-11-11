## Current changes before commit:

User-facing changes:
- Load pending cashier sales and returns only from Odoo for the selected store.
- Load sale details only from Odoo and report the existing Invoice not found error when no matching bill exists; remove the B-Connect fallback.
- Allow pending-list and detail reads without B-Connect connection settings while retaining cashier authentication, store authorization, invoice identifiers, sorting, limits, and duplicate handling.
- Preserve B-Connect bill saving, payment wallets, and cashier closing.
- Remove development test fixtures and generated Python caches from the runtime addon after validation; retain regression tests and results outside the addon.
- Identify the previously committed status synchronization changes by their actual commit metadata in the earlier changelog.

Validation:
- Targeted cashier upgrades passed in isolated database `codex_cashier_odoo_only_20261008`, cloned from a development validation database. Its sales dependency was also upgraded to align an outdated sales schema with the current code; no production database was modified.
- Nine cashier regression tests passed: Odoo pending sales and returns, Odoo sale lines, missing-bill errors, reads without B-Connect IP or store serial, branch isolation, denied cashier access, duplicate handling, sorting and limits, repeated saving, return details/saving, and wallet responses.
- Tests ran with Employee Access Sales, sales promotions, and contracts installed; external reads were blocked in the list/detail tests and external posting was mocked in save tests. Transactional test fixtures were rolled back.
- Regression artifacts: `/tmp/ab_sales_cashier_odoo_only_validation/tests/test_cashier_api.py` and `/tmp/ab_sales_cashier_odoo_only_validation/odoo-validation.log`.
- No new or updated user-facing source strings; checked the diff for translation changes. The module has no existing `i18n/ar.po` or `i18n/ar_001.po`, and this change requires no new entries.
- Python syntax and whitespace diff checks passed.

Files changed:
- ab_sales_cashier/models/ab_sales_cashier_api.py
- ab_sales_cashier/tests/__init__.py (removed from runtime addon)
- ab_sales_cashier/tests/test_cashier_api.py (removed from runtime addon after validation)
- ab_sales_cashier/changelog.d/2026-10-07-cashier-status-sync.md
- ab_sales_cashier/changelog.d/2026-10-08-odoo-pending-bills.md
