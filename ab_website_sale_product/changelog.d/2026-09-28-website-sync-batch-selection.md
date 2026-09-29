# Website Product Sync Batch Selection

## Recent relevant commit

- Commit: `feffc2532ca317e24f59c34b5a5179019b110388`
- Author: Mohamed Fawzy
- Date: 2026-09-27
- Original subject: `ab_website_sale_product/test: cover product image sync matching`
- Added coverage for product image matching and replacement behavior.
- Files changed: `tests/test_website_category_mapping.py`

## Current changes before commit:

- Fix Process Next Batch silently limiting every dropdown selection to 250.
- Honor the selected product count with bounded internal chunks and stop when
  no progress is possible; retain background commits after at most 250 products.
- Preserve the selected size when preparing the existing full-sync job.
- Clarify English and Arabic field help and document manual-request timeout risk.
- Add five regression tests; all 33 sync/category/image tests passed on the
  isolated test database. No live database upgrade or server restart performed.

Files changed:

- `models/website_product_sync_job.py`
- `tests/test_website_product_sync.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `README_website_product_sync.md`
- `changelog.d/2026-09-28-website-sync-batch-selection.md`

Other uncommitted sync performance changes are documented separately in
`2026-09-27-website-product-sync-performance.md`.
