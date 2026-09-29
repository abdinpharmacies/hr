# Website Product Sync Performance

## Recent relevant commit

- Commit: `feffc2532ca317e24f59c34b5a5179019b110388`
- Author: Mohamed Fawzy
- Date: 2026-09-27
- Original subject: `ab_website_sale_product/test: cover product image sync matching`
- Added coverage for matching, missing, ambiguous, invalid and unchanged images.

Files changed:

- `tests/test_website_category_mapping.py`

## Current changes before commit:

- Batch template lookup and creation, reuse taxonomy lookups, and skip unchanged
  metadata, translations and images.
- Add durable cron checkpoints, failure isolation, retry attempts, unchanged
  counts, atomic claiming and preservation of previous sync jobs.
- Add indexed dependency-driven delta selection and protect changes made while
  synchronization is running.
- Recognize already-applied resized images using source/destination checksums.
- Add English/Arabic controls, 28 passing tests and repeatable performance tools.
- Record measurements, index plans, concurrency checks and operational limits in
  `README_website_product_sync.md`.

Files changed for this optimization:

- `models/ab_product.py`
- `models/website_product_sync_job.py` (already present as untracked work)
- `models/product_template.py`
- `models/product_image_sync.py`
- `views/website_product_sync_job_views.xml` (already present as untracked work)
- `i18n/ar.po`
- `i18n/ar_001.po`
- `tests/__init__.py`
- `tests/test_website_product_sync.py`
- `tests/test_website_category_mapping.py`
- `tests/benchmark_website_sync.py`
- `tests/benchmark_website_sync_batches.py`
- `tests/check_website_sync_concurrency.py`
- `tests/check_website_sync_delta_race.py`
- `README_website_product_sync.md`
- `changelog.d/2026-09-27-website-product-sync-performance.md`

Pre-existing manifest, cron XML, menu, ACL, sale-order and other changelog edits
were inspected and preserved; they are not changes made by this optimization.
