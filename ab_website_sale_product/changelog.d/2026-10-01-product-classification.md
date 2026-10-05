# Product classification

## Recent relevant commit

Commit: `083e324f3b56f0cf60f0064b3645d25e3743b3f0`
Author: Mohamed Fawzy
Date: 2026-09-29
Original commit subject: `ab_website_sale_product/docs: record website sync commits`

- Recorded the existing synchronization implementation and local commit history.

Files changed:

- `changelog.d/2026-09-29-website-sync-local-commits.md`

## Current changes before commit:

- Add selected suggestion application, automatic review assignment with a chosen fallback, and audited undo; see `2026-10-04-force-categorization.md`.

- Add an administrator classification console from the existing e-commerce categories list, with real scope counts, polling, primary-category totals and run history.
- Add persistent taxonomy, run, result, assignment, review and research-cache models, administrator ACLs and company rules.
- Reuse `integration_queue_job` for snapshot preparation, bounded checkpoints and queued controls. Recover interrupted classification jobs without changing unrelated queues.
- Replace the old keyword/fallback category assignment with shared deterministic rules; preserve manual and automatic assignments during synchronization.
- Bundle all historical reference files with source/join documentation and checksums. Use historical evidence without importing historical categories.
- Add explicit closed-taxonomy setup, ambiguous binding resolution, manual review, permanent ignore/reset decisions and optional cached Brave evidence.
- Maintain Arabic translations and add lifecycle, rule, security, synchronization and browser tests.
- Document configuration and validation. The 2026-10-04 targeted upgrade and taxonomy repair are recorded in `2026-10-04-taxonomy-shop-needs.md`; all 77 bindings are ready. The user-started live classification run is now processing through the activated local runner; see `2026-10-04-classification-runner.md`.
- Add editable category descriptions and main/subcategory shop needs, with ten approved choices and inherited product needs.

Validation:

- Fresh isolated installation succeeded.
- Full suite: 77 tests passed, zero failures/errors (`/tmp/ab_classification_final_verified.log`).
- Final lock-acquisition and browser checks: 2 tests passed, zero failures/errors (`/tmp/ab_classification_lock_verified.log`).
- Polling race checks cover stale successes and failures; the browser flow is rechecked after the polling guard (`/tmp/ab_classification_ui_verified.log`).
- Actual runner: 501 products classified, 501 unique results, four completed queue jobs, no review/failures (`/tmp/ab_classification_runner.log`).
- Runtime Arabic action/taxonomy/category labels verified. Both PO files passed `msgfmt --check-format`; Python/XML syntax, reference checksums and whitespace checks passed.
- Live external-provider credentials were unavailable; provider tests used explicit fixtures. Taxonomy resolution and local queue configuration are complete; web research additionally requires its key and trusted domains.

Files changed:

- `__manifest__.py`
- `models/__init__.py`
- `models/ab_product.py`
- `models/product_classification.py`
- `services/__init__.py`
- `services/classification.py`
- `services/historical.py`
- `services/web_research.py`
- `data/classification_taxonomy.xml`
- `data/classification_queue.xml`
- `security/ir.model.access.csv`
- `security/classification_rules.xml`
- `views/product_classification_views.xml`
- `static/src/js/product_classification.js`
- `static/src/xml/product_classification.xml`
- `static/src/scss/product_classification.scss`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `tests/__init__.py`
- `tests/test_product_classification.py`
- `tests/test_classification_ui.py`
- `tests/check_classification_polling.cjs`
- `tests/test_website_category_mapping.py`
- `tests/test_website_product_sync.py`
- `docs/classification_plan.md`
- `docs/classification.md`
- `docs/reference/website_ecommerce/categories/README.md`
- `docs/reference/website_ecommerce/categories/manifest.json`
- `docs/reference/website_ecommerce/categories/notes.md`
- `docs/reference/website_ecommerce/categories/ecommerce_products.csv`
- `docs/reference/website_ecommerce/categories/ecommerce_categories.csv`
- `docs/reference/website_ecommerce/categories/ecommerce_product_category_rel.csv`
- `changelog.d/2026-10-01-product-classification.md`
