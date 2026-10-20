# Storefront navigation performance

## Recent relevant commit

Commit: `68f7d9ae1cb69fd7ce10436f2cef5614bd90ef29`
Author: Mohamed Fawzy
Date: 2026-10-13
Original subject: `ab_ecommerce_storefront/IMP: add brand deal and availability filters`

User-facing changes:

- Add storefront brand, promotion and stock availability filters.

Files changed (relevant to this update):

- `ab_ecommerce_storefront/controllers/shop.py`

## Current changes before commit:

- Add optional navigation diagnostics for storefront pages. Enable with `?ab_perf=1`; subsequent pages in the same tab retain recording. Use `window.abStorefrontPerformance.report()` in the browser console for a table, `.export()` for JSON, and `.stop()` or `?ab_perf=0` to stop and erase the local records.
- Record navigation TTFB, document download, DOM readiness, load, FCP, the latest observed LCP candidate, and the ten slowest buffered resources. Keep at most 100 page visits in session storage; send no telemetry requests. Strip query strings and fragments, redact long path segments, and label external resources without their URLs.
- Identify back/forward-cache restores separately without reusing the original page's navigation timings. These diagnostics do not measure INP, pre-navigation click delays, server-only execution time, or background AJAX rendering completion. Resource transfer sizes can be zero for cached or cross-origin responses. LCP is a candidate observation, not a complete Core Web Vitals aggregation.
- Select stock-filter candidates through ORM domains and fetch only the required stored fields, avoiding delegated-field evaluation for the entire catalog in Python. Aggregate existing local stock snapshots in one grouped query. Preserve candidate scope, order, availability semantics, and native warehouse stock checks; return the caller's original non-elevated recordset.
- Batch image-attachment metadata checks through non-stored computed flags. Preserve attachment selection order, placeholder detection and variant/template fallback; invalidate on normal product image writes.
- Add the computed field label to both Arabic catalogs. The console API uses technical metric keys and adds no customer-facing controls.
- Existing best-seller changes in `models/website.py` and `views/homepage.xml` are documented separately in `2026-10-18-best-sellers.md` and were not edited by this task.

Files changed:

- `ab_ecommerce_storefront/__manifest__.py`
- `ab_ecommerce_storefront/controllers/shop.py`
- `ab_ecommerce_storefront/models/product_template.py`
- `ab_ecommerce_storefront/static/src/js/navigation_performance.js`
- `ab_ecommerce_storefront/i18n/ar.po`
- `ab_ecommerce_storefront/i18n/ar_001.po`
- `ab_ecommerce_storefront/changelog.d/2026-10-18-navigation-performance.md`

## Measurement evidence

Read-only HTTP requests to the existing development server on port 4092, three runs per route, before activation:

| Route | TTFB range, seconds |
| --- | --- |
| `/` | 4.16–5.19 |
| `/shop` | 13.80–14.18 |
| `/shop/category` | 12.61–13.46 |
| `/shop/cart` | 2.90–3.26 |
| `/contactus` | 2.54–2.86 |

Matched in-process WSGI requests on the separate development database `ecom19_home_ux_20261015` measured `/shop` at 5.183 seconds before the availability change and 2.038 seconds after it, approximately 61% less time. These are individual local comparison runs, not browser paint measurements or production percentiles. They must not be directly compared with the separate server's 14-second baseline.

The profiled request fell from 5.965 to 2.616 seconds; the availability helper fell from 4.410 to 0.867 seconds. The before profile evaluated the Python eligibility predicate 31,255 times. The image check test decreased from 18 SQL queries to one for 12 products with mixed image presence.

## Validation

- Targeted storefront upgrades passed on `ecom19_home_ux_20261015` using the ecommerce checkout, no HTTP server, zero cron threads and ports 5369/5372 reserved in the command configuration. The existing server on 4092 was not restarted or upgraded.
- Ten rollback-only Odoo tests passed, including exact availability parity across 31,255 published products (23,832 retained), public caller scope/order, empty candidates, negative/inactive/hidden stock and service handling, image invalidation, variant fallback and image query count.
- Eight Node VM checks passed for opt-in, session persistence, navigation/resource metrics, query stripping, buffered LCP, cache restores, shutdown with a pending timer, malformed storage and bounded history. These are simulated browser API tests; real browser visual/navigation validation remains outstanding.
- Odoo POT export confirmed the new field references. Both catalogs passed `msgfmt --check-format`; the test database has `en_US` and `ar_001` installed, not `ar`.
- Runtime field labels were verified in English and Arabic after a one-term Arabic import with overwrite on the test database; its initial field creation had retained an English translation. The homepage view differs between English and Arabic. Six WSGI HTTP checks returned 200 for English/Arabic home and shop, cart and contact pages. Both generated frontend bundles returned 200, and the lazy bundle contains the navigation monitor.
- The test clone logs a missing filestore object (`e71bee214cb344b62dbe33f85f025f31ea197c80`), also present in the earlier best-seller validation log before this work. HTTP checks still pass; full visual/image verification is not claimed. Existing unrelated module/view warnings remain.
- Python/manifest parsing, JavaScript syntax and `git diff --check` passed. No runtime package was generated; test harnesses and profile evidence remain outside the addon under `/tmp/ab-storefront-*`.

Activation on port 4092 still requires the normal targeted module update and Python process reload. Updating the complete working tree will also activate the pre-existing best-seller work. The page loader's wait for `window.load` was observed but left unchanged pending browser measurements.
