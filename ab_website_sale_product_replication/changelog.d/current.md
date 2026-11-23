# Website product replica integration change log

## Current changes before commit:

- Verify that archived duplicate codes do not block a linked active website product while active duplicates remain blocked.

Files changed:

- `ab_website_sale_product_replication/tests/test_replica_catalog_import.py`
- `ab_website_sale_product_replication/changelog.d/current.md`

Validation:

- Focused replica regression passed on `codex_eplus_sync_20261104` with alternate ports `5069/5072`; `/tmp/ecommerce_archived_duplicate_replica_validation_pass.log`.

## Recent commits

Commit: `ab1e15a5`
Author: Mohamed Fawzy
Date: 2026-11-23
Original subject: `ab_website_sale_product_replication/TEST: cover native branch stock read`

User-facing changes:

- Cover native, parameterized branch stock reads and optional store metadata fallback.

Files changed:

- `ab_website_sale_product_replication/changelog.d/current.md`
- `ab_website_sale_product_replication/tests/test_replica_catalog_import.py`

Commit: `152b71f6`
Author: Mohamed Fawzy
Date: 2026-11-23
Original subject: `ab_website_sale_product_replication/FIX: let cron pick up scheduled product sync`

User-facing changes:

- Store the background flag explicitly so the scheduled website product worker can finish its job.

Files changed:

- `ab_website_sale_product_replication/changelog.d/current.md`
- `ab_website_sale_product_replication/models/stock_sync.py`
- `ab_website_sale_product_replication/tests/test_replica_catalog_import.py`

Commit: `542d8518`
Author: Mohamed Fawzy
Date: 2026-11-23
Original subject: `ab_website_sale_product_replication/FIX: run website and stock sync after replication`

User-facing changes:

- Start the website product sync after replication and keep inventory sync independent of branch stock refresh failures.
- Translate the scheduled website sync messages into Arabic.

Files changed:

- `ab_website_sale_product_replication/changelog.d/current.md`
- `ab_website_sale_product_replication/i18n/ab_website_sale_product_replication.pot`
- `ab_website_sale_product_replication/i18n/ar.po`
- `ab_website_sale_product_replication/i18n/ar_001.po`
- `ab_website_sale_product_replication/models/replication.py`
- `ab_website_sale_product_replication/models/stock_sync.py`
- `ab_website_sale_product_replication/tests/test_replica_catalog_import.py`

Commit: `7e6ea239`
Author: Mohamed Fawzy
Date: 2026-11-22
Original subject: `ab_website_sale_product_replication/IMP: refresh stock after product replication`

User-facing changes:

- Queue Eplus aggregate and branch stock refreshes after product replication, followed by Odoo inventory sync.
- Check snapshot size before applying the scheduled inventory sync.

Files changed:

- `ab_website_sale_product_replication/__manifest__.py`
- `ab_website_sale_product_replication/changelog.d/current.md`
- `ab_website_sale_product_replication/i18n/ab_website_sale_product_replication.pot`
- `ab_website_sale_product_replication/i18n/ar.po`
- `ab_website_sale_product_replication/i18n/ar_001.po`
- `ab_website_sale_product_replication/models/__init__.py`
- `ab_website_sale_product_replication/models/replication.py`
- `ab_website_sale_product_replication/models/stock_sync.py`
- `ab_website_sale_product_replication/tests/test_replica_catalog_import.py`

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
