# Website product replica integration change log

## Current changes before commit:

- Reconcile linked website base prices after each successful unrestricted ab_product replication, including runs with no new source rows.
- Scan linked templates in batches and write only price differences through Odoo, retaining the existing price audit messages.
- Respect caller permissions, company rules, and caller-controlled transactions; skip reconciliation for failed, scoped, or unrelated replication calls.

Files changed:

- `ab_website_sale_product_replication/models/__init__.py`
- `ab_website_sale_product_replication/models/replication.py`
- `ab_website_sale_product_replication/tests/test_replica_catalog_import.py`
- `ab_website_sale_product_replication/changelog.d/current.md`

Validation:

- Targeted upgrade on development database `codex_eplus_sync_20261104`, alternate ports `5069/5072`, HTTP and cron disabled: 11 tests passed, zero failures/errors; `/tmp/ab_replica_price_reconcile_test2.log`.
- Covered unchanged-source repair, audit creation, repeated no-op runs, caller transactions, skipped scopes, source failure, denied reader writes, and company isolation alongside the existing integration tests.
- The development database logged an existing missing filestore attachment; the price tests completed successfully.
- No new user-facing strings or translation entries are needed. Price changes use the existing bilingual audit message.
- Deployment requires reloading the Python integration; no schema, XML, or translation upgrade is needed.

## Recent commits

Commit: `05ba003d`
Author: Mohamed Fawzy
Date: 2026-11-15
Original subject: `ab_website_sale_product_replication/IMP: synchronize replicated website prices`

User-facing changes:

- Propagate replicated default-price changes to linked website products during replay.
- Cover replay of a source price change while the website price is stale.

Files changed:

- `ab_website_sale_product_replication/__init__.py`
- `ab_website_sale_product_replication/models/__init__.py`
- `ab_website_sale_product_replication/models/ab_product.py`
- `ab_website_sale_product_replication/tests/test_replica_catalog_import.py`
- `ab_website_sale_product_replication/changelog.d/current.md`

Commit: `450e6eef`
Author: Mohamed Fawzy
Date: 2026-11-11
Original subject: `ab_website_sale_product_replication/ADD: allow replica website sync bookkeeping`

User-facing changes:

- Install the optional integration when website product sync and Odoo replication are both installed.
- Allow Settings administrators to update only website sync bookkeeping on replicated products, preserving price and identifier restrictions.
- Cover replica catalog import and denied direct edits.

Files changed:

- `ab_website_sale_product_replication/__init__.py`
- `ab_website_sale_product_replication/__manifest__.py`
- `ab_website_sale_product_replication/changelog.d/current.md`
- `ab_website_sale_product_replication/security/website_sync_rule.xml`
- `ab_website_sale_product_replication/tests/__init__.py`
- `ab_website_sale_product_replication/tests/test_replica_catalog_import.py`
