# Website Product Sync Dedicated Background Worker

## Recent relevant commit

- Commit: `feffc2532ca317e24f59c34b5a5179019b110388`
- Author: Mohamed Fawzy
- Date: 2026-09-27
- Original subject: `ab_website_sale_product/test: cover product image sync matching`
- Added coverage for product image matching and replacement behavior.
- Files changed: `tests/test_website_category_mapping.py`

## Current changes before commit:

- Make Process All Remaining submit a durable asynchronous request independent
  of Products Per Batch, with full preparation deferred for draft jobs.
- Add a module-only, supervised worker with 250-product transactions, exclusive
  ownership, requester checks, failure recovery, cancellation and restart resume.
- Refresh the sync form's progress automatically without driving synchronization
  from the browser or overwriting unsaved form edits.
- Preserve the legacy cron path, but exclude background-owned jobs from it.
- Add English/Arabic messages and offline-worker/error feedback.
- Validate 41 regression tests, separate-process recovery/concurrency tests, and
  desktop/mobile browser completion of a 10,001-line synthetic queue.
- Activate the dedicated user service on ecom19 after backup and targeted module
  upgrade; preserve the existing 30,000/31,253 job without auto-starting it.
- Keep global cron disabled and leave its configuration unchanged.

Files changed:

- `__manifest__.py`
- `models/website_product_sync_job.py`
- `services/__init__.py`
- `services/website_sync_worker.py`
- `worker.py`
- `deploy/website-product-sync.service`
- `static/src/js/website_sync_form.js`
- `views/website_product_sync_job_views.xml`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `tests/test_website_product_sync.py`
- `tests/check_website_sync_background_worker.py`
- `README_website_product_sync.md`
- `changelog.d/2026-09-28-website-sync-background-worker.md`

Earlier uncommitted optimizations and manual batch-selection fixes remain
documented in their own dated changelog entries.
