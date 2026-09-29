# Website product sync change log

## Recent commits

Commit: `b430113`
Author: Mohamed Fawzy
Date: 2026-09-29
Original subject: `ab_website_sale_product/feat: run website product sync in background`

User-facing changes:

- Process requested full synchronization through a dedicated worker with automatic progress updates.

Files changed:

- `ab_website_sale_product/README_website_product_sync.md`
- `ab_website_sale_product/__manifest__.py`
- `ab_website_sale_product/changelog.d/2026-09-28-website-sync-background-worker.md`
- `ab_website_sale_product/deploy/website-product-sync.service`
- `ab_website_sale_product/services/__init__.py`
- `ab_website_sale_product/services/website_sync_worker.py`
- `ab_website_sale_product/static/src/js/website_sync_form.js`
- `ab_website_sale_product/tests/__init__.py`
- `ab_website_sale_product/tests/benchmark_website_sync.py`
- `ab_website_sale_product/tests/benchmark_website_sync_batches.py`
- `ab_website_sale_product/tests/check_website_sync_background_worker.py`
- `ab_website_sale_product/tests/check_website_sync_concurrency.py`
- `ab_website_sale_product/tests/check_website_sync_delta_race.py`
- `ab_website_sale_product/tests/test_website_product_sync.py`
- `ab_website_sale_product/worker.py`

Commit: `bb916e2`
Author: Mohamed Fawzy
Date: 2026-09-29
Original subject: `ab_website_sale_product/feat: add resumable website product sync`

User-facing changes:

- Add resumable batch and delta synchronization with remaining-product selection and Arabic UI.

Files changed:

- `ab_website_sale_product/__manifest__.py`
- `ab_website_sale_product/changelog.d/2026-09-27-website-product-sync-performance.md`
- `ab_website_sale_product/changelog.d/2026-09-28-website-sync-batch-selection.md`
- `ab_website_sale_product/changelog.d/2026-09-28-website-sync-remaining.md`
- `ab_website_sale_product/data/ir_cron.xml`
- `ab_website_sale_product/i18n/ar.po`
- `ab_website_sale_product/i18n/ar_001.po`
- `ab_website_sale_product/models/__init__.py`
- `ab_website_sale_product/models/ab_product.py`
- `ab_website_sale_product/models/website_product_sync_job.py`
- `ab_website_sale_product/security/ir.model.access.csv`
- `ab_website_sale_product/views/website_product_sync_job_views.xml`
- `ab_website_sale_product/views/website_sale_menus.xml`

Commit: `acbea2c`
Author: Mohamed Fawzy
Date: 2026-09-29
Original subject: `ab_website_sale_product/fix: preserve manually edited website images`

User-facing changes:

- Detect applied source images and preserve manually edited website images.

Files changed:

- `ab_website_sale_product/models/product_image_sync.py`
- `ab_website_sale_product/models/product_template.py`
- `ab_website_sale_product/tests/test_website_category_mapping.py`

Commit: `56e09e4`
Author: Mohamed Fawzy
Date: 2026-09-29
Original subject: `ab_website_sale_product/fix: enforce E-Plus stock limits in cart`

User-facing changes:

- Enforce E-Plus stock limits when cart quantities change.

Files changed:

- `ab_website_sale_product/models/sale_order.py`
