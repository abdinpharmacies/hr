# All-products availability performance

## Recent relevant commit

Commit: `68f7d9ae1cb69fd7ce10436f2cef5614bd90ef29`
Author: Mohamed Fawzy
Date: 2026-10-13
Original subject: `ab_ecommerce_storefront/IMP: add brand deal and availability filters`

User-facing changes:

- Add brand, deal and availability filters to the shop.

Files changed:

- `ab_ecommerce_storefront/controllers/shop.py`

## Current changes before commit:

- Reduce repeated stock computation when opening All products. Skip products already excluded by source quantity limits, resolve the warehouse/cart once, and combine the native stock checks into bounded batches of 5,000 templates.
- Fetch variants in the native model order and keep the first variant for each template, matching Odoo 19's `product_variant_id` selection, including inactive variants as before. Avoid computing that field and delegated product type for every catalogue item.
- Use Odoo's existing `_compute_quantities_dict` calculation, including installed expiry/manufacturing overrides and quantity context, without populating five computed quantity fields for every catalogue candidate. Keep service handling, unit rounding, physical reservations, live cart holds and warehouse/company scope.
- Preserve the caller's recordset, access environment and ordering. Keep the existing out-of-stock option, source availability caps, pagination, prices, offers, category cache and scoped JIT behavior.
- Add regressions for caller permissions/order, skipped computation for unavailable sources and native first-variant ordering.
- Preserve the other uncommitted stock, checkout, website and UI changes. No inventory quantity, persistent PostgreSQL setting, external database, index or schema change is introduced.

Files changed:

- `ab_ecommerce_storefront/controllers/shop.py`
- `ab_ecommerce_storefront/tests/test_stock_availability.py`
- `ab_ecommerce_storefront/changelog.d/2026-10-19-all-products-availability-performance.md`

## Diagnosis and validation

The primary service had already loaded the previous category/product cache: its response included the catalog scope and 61 static fragment keys. A public `/ar/shop` request took 7397 ms and 841 SQL queries. A separate diagnostic request with the existing `include_oos=1` option took 1075 ms and 367 queries. The latter returns different products and only isolates the cost of availability filtering; it is not the proposed fix.

Read-only, separate-transaction comparisons on `ecom19_cart_hold_20261018` evaluated 31,256 candidates. Both implementations retained the same 41 products in the same order, with identical result hashes across four alternating runs. The availability method used 453–454 queries before and 31 after. The development database's catalogue is not assumed to have the primary database's stock state.

All 36 stock/reservation test methods passed: the existing 33 methods and three new regressions. A targeted `-u ab_ecommerce_storefront` passed on that development database, with HTTP disabled, workers/cron disabled and alternate ports 5492/5494. This validation does not establish an external E-Plus reservation integration; the existing checkout gate remains unchanged.

Both Arabic catalogs passed `msgfmt --check-format`; no UI strings were added. Python parsing and `git diff --check` passed. Development tests must be excluded from runtime packaging.

Evidence and reproducible scripts are in `outputs/performance/all_products_20261019/`. The primary Odoo process and database were not restarted or upgraded. This Python-only change becomes active when the running Odoo workers reload the addon normally.

## HTTP comparison

Two temporary loopback processes used the same isolated database and public Arabic session, workers/cron disabled, development mode disabled, and ports 5492/5494. The baseline snapshot differs only in the availability method. One warm-up per route was excluded. Ten products requests per mode and three per control route were measured; these are local HTML TTFB measurements, excluding asset downloads and browser rendering. p95 uses nearest rank; the small control samples do not establish production percentiles.

| Route | Samples per mode | Before median / p95 | After median / p95 | Median SQL query count |
| --- | ---: | ---: | ---: | ---: |
| All products | 10 | 6497 / 8881 ms | 2544 / 4337 ms | 515 → 95 |
| Page two | 3 | 7231 / 7443 ms | 2207 / 2673 ms | 518 → 101 |
| Offers | 3 | 681 / 708 ms | 532 / 571 ms | 67 → 68 |
| Include unavailable | 3 | 1597 / 1612 ms | 1298 / 1472 ms | 282 → 282 |

All 38 measured requests returned 200. IDs/order and price hashes match, and the complete HTML matches after normalizing only the input and JavaScript CSRF tokens. The comparison initially normalized input tokens only; the corrected assertion also covers the existing JavaScript token and passes against the same saved responses, without rerunning or discarding samples. Both temporary processes are stopped.

This reduces All products median TTFB by approximately 61% in the measured development environment. The remaining cost still includes selecting the catalogue, current availability and rendering; no promise of instant navigation or equivalent production latency is made. Full Brave rendering and sustained concurrency were not measured. No new tests or overrides change the existing E-Plus checkout integration gate.
