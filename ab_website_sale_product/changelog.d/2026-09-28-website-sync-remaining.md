# Website Product Sync Remaining Products

## Recent relevant commit

- Commit: `feffc2532ca317e24f59c34b5a5179019b110388`
- Author: Mohamed Fawzy
- Date: 2026-09-27
- Original subject: `ab_website_sale_product/test: cover product image sync matching`
- Added regression coverage for product image matching.
- Files changed: `tests/test_website_category_mapping.py`

## Current changes before commit:

- Resume running/interrupted synchronization without resetting completed lines.
- Queue only missing or dirty products and skip clean linked products.
- Add Check Remaining and Show Remaining with separate missing/review counts.
- Include already-synchronized products in completion percentages; keep failures
  outstanding instead of displaying 100% prematurely.
- Track destination template/variant edits so changed website fields are reviewed.
- Preserve English/Arabic labels and module-only background processing.
- Validate 48 functional regressions on an isolated database.
- Verify browser preview at 33.33%, two remaining rows and one-click completion
  at 100%, with no JavaScript errors or Process Next Batch calls.
- Normalize empty progress values to avoid unchanged form reloads while polling.
- Activate on ecom19 after a dedicated backup and targeted module upgrade;
  verify the worker, HTTP response and Arabic labels with global cron disabled.

Files changed:

- `models/ab_product.py`
- `models/website_product_sync_job.py`
- `views/website_product_sync_job_views.xml`
- `static/src/js/website_sync_form.js`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `tests/test_website_product_sync.py`
- `README_website_product_sync.md`
- `changelog.d/2026-09-28-website-sync-remaining.md`
