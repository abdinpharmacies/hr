# Website product replica integration change log

## Current changes before commit:

- Apply linked website base-price synchronization when a replicated `ab_product.default_price` change is replayed.
- Keep the integration scoped to replicated price changes and preserve replica write restrictions.
- Cover the replication callback with a test that starts from a stale linked website price.

Files changed:

- `ab_website_sale_product_replication/__init__.py`
- `ab_website_sale_product_replication/models/__init__.py`
- `ab_website_sale_product_replication/models/ab_product.py`
- `ab_website_sale_product_replication/tests/test_replica_catalog_import.py`
- `ab_website_sale_product_replication/changelog.d/current.md`

Validation:

- Targeted install and upgrade on development database `codex_eplus_sync_20261104`, ports `5069/5072`: all five replica integration tests passed, zero failures/errors; `/tmp/ab_price_replication_suite.log`.
- No user-facing strings, security records, or external database writes were added.

## Recent commits

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
