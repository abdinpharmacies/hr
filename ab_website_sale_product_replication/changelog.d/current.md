# Website product replica integration change log

## Current changes before commit:

- Queue Eplus aggregate and branch stock refreshes after each successful unrestricted barcode replication, then start the Odoo inventory sync.
- Preserve the existing product replication flow and reject sharply reduced stock snapshots before inventory sync.
- Restrict scheduled refresh methods to administrators and retry transient source failures or concurrent inventory jobs.
- Cover queue triggering, excluded replication calls, and denied reader access in focused tests.
- Add English source strings and both Arabic catalogs for queue descriptions and errors.

Files changed:

- `ab_website_sale_product_replication/__manifest__.py`
- `ab_website_sale_product_replication/i18n/ab_website_sale_product_replication.pot`
- `ab_website_sale_product_replication/i18n/ar.po`
- `ab_website_sale_product_replication/i18n/ar_001.po`
- `ab_website_sale_product_replication/models/__init__.py`
- `ab_website_sale_product_replication/models/replication.py`
- `ab_website_sale_product_replication/models/stock_sync.py`
- `ab_website_sale_product_replication/tests/test_replica_catalog_import.py`
- `ab_website_sale_product_replication/changelog.d/current.md`

Validation:

- Targeted development upgrade on `codex_eplus_sync_20261104` with alternate ports `5069/5072`: four new replication tests passed; `/tmp/eplus_deploy_preflight_tests.log`.
- Both new Arabic catalogs pass `msgfmt --check-format`.
- Production upgrade and storefront verification are required after deployment.

## Recent commits

Commit: `bb979570`
Author: Mohamed Fawzy
Date: 2026-11-16
Original subject: `ab_website_sale_product_replication/FIX: reconcile website prices after replication`

User-facing changes:

- Reconcile linked website prices after product replication, including runs with no new source rows.

Files changed:

- `ab_website_sale_product_replication/changelog.d/current.md`
- `ab_website_sale_product_replication/models/__init__.py`
- `ab_website_sale_product_replication/models/replication.py`
- `ab_website_sale_product_replication/tests/test_replica_catalog_import.py`

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
