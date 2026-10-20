# Stop persistent catalog loading feedback

## Recent relevant commit

Commit: `06583a36a73e5f53841405a9205c4212912c6710`
Author: Mohamed Fawzy
Date: 2026-10-15
Original subject: `ab_ecommerce_storefront/IMP: show loading feedback when applying shop filters`

User-facing changes:

- Show delayed loading feedback while shop filters navigate to new results.

Files changed (relevant to this update):

- `ab_ecommerce_storefront/static/src/js/shop_filter_loading.js`
- `ab_ecommerce_storefront/static/src/scss/storefront.scss`

## Current changes before commit:

- Stop displaying and locking the catalog for automatic tab-focus refreshes. Coalesce focus/visibility requests and allow at most one such refresh attempt per thirty seconds.
- Release request-owned loading classes, busy state and interaction locks after success, errors, timeout, cancellation, pagehide and teardown. Preserve pre-existing busy/inert state and prevent older requests from clearing a newer request's state.
- Keep the existing page usable after a failed background refresh; retain native page navigation as the fallback for explicit pagination and changed commerce context.
- Delay the pagination indicator by 180 ms to avoid flashing it for fast responses. Preserve quantity/unit choices made while a background request is in flight.
- Retain normal pagination, history, current prices/availability, cache reconstruction and interaction restart behavior.

Files changed:

- `ab_ecommerce_storefront/static/src/js/catalog_navigation.js`
- `ab_ecommerce_storefront/tests/test_catalog_cache.py`
- `ab_ecommerce_storefront/changelog.d/2026-10-19-catalog-loading-lifecycle.md`

## Validation

- Nine JavaScript lifecycle checks reproduce failures against the saved previous implementation and pass against the fix. They cover focus throttling, request coalescing, nonblocking background errors/timeouts, teardown, pagehide, foreground fallback, superseded requests, delayed feedback and original accessibility state.
- Two headless Chrome tests passed on neutralized database `ecom19_cart_hold_20261018`, using this checkout and ports 5769/5772 with workers/cron disabled. The new test exercises real interaction registration, background failure/recovery, in-flight quantity edits and cancelled pagination. The existing test verifies pagination, browser Back, static cache reconstruction and current commerce data.
- Targeted `-u ab_ecommerce_storefront`, Odoo JavaScript transpilation, JavaScript syntax, Python parsing, both Arabic catalogs and whitespace checks passed. This change introduces no user-facing strings.
- The isolated database has existing missing product images that generate image-request errors; both browser assertions completed with zero test failures/errors. No image records were modified for this fix.
- No primary database upgrade or server restart was performed. Existing browser documents require a reload to replace their already-running interaction instances.
- Read-only HTTP verification on port 4092 confirms that the page references frontend bundle `0ea8641` and that this served bundle contains the new refresh throttle and loading cleanup methods. The served source also matches the edited file.
- Development test scripts/results are under `outputs/validation/catalog_loading_20261019/`; Odoo's browser log is `/tmp/ab-catalog-loading-browser-20261019.log`. Exclude development tests from runtime addon packages.
