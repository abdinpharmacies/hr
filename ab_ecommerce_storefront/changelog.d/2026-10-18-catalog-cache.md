# Storefront category and visited-product caching

## Recent relevant commit

Commit: `3fd4af85dd0733a8598055ba2aaf9956a72258df`
Author: Mohamed Fawzy
Date: 2026-10-15
Original subject: `ab_ecommerce_storefront/IMP: animate sidebar category expansion`

User-facing changes:

- Animate category expansion in the storefront sidebar.

Files changed (relevant to this update):

- `ab_ecommerce_storefront/static/src/js/shop_category_accordion.js`
- `ab_ecommerce_storefront/changelog.d/2026-10-15-sidebar-category-motion.md`

## Current changes before commit:

- Cache category labels, hierarchy, links and icon presentation by website, language, user, privilege and allowed companies. Batch category reads and reuse the same data in the header and sidebar.
- Invalidate category data after name, translation, order, parent, website, membership and product publication changes. Keep uncommitted writer results out of the shared cache; clear it after commit or rollback using the cursor callbacks and Odoo's registry signaling.
- Keep the initial product page, filters, category links and search server rendered. Enhance pagination and history navigation with one fresh page request using the native product selection, pricing, offers, availability and pagination logic.
- Store only visited product names, category labels and image markup in bounded tab-session storage. Limit it to 160 fragments and 256,000 UTF-16 code units. Content hashes detect edits; prices, availability, offers, purchase controls, wishlist state and CSRF tokens are never retained in this cache.
- Partition cached fragments by the server's website, company, warehouse, user, language, pricelist, fiscal position and cart delivery context. Revalidate after navigation, return to the tab, BFCache restoration and commerce-context notifications; reload the full page if its server context changed.
- Preserve quantity and purchase-unit selections during a same-page refresh. Restart the existing Odoo interactions on the updated grid. Fall back to full navigation on errors, missing cached fragments or incompatible responses.
- Preserve all earlier uncommitted work, including scoped JIT control. No global PostgreSQL configuration, indexes, offers domains, inventory quantities or external database records are changed.

Files changed:

- `ab_ecommerce_storefront/__manifest__.py`
- `ab_ecommerce_storefront/controllers/__init__.py`
- `ab_ecommerce_storefront/controllers/catalog.py`
- `ab_ecommerce_storefront/models/__init__.py`
- `ab_ecommerce_storefront/models/catalog_cache.py`
- `ab_ecommerce_storefront/static/src/js/catalog_cache.js`
- `ab_ecommerce_storefront/static/src/js/catalog_navigation.js`
- `ab_ecommerce_storefront/views/catalog.xml`
- `ab_ecommerce_storefront/views/homepage.xml`
- `ab_ecommerce_storefront/views/shop.xml`
- `ab_ecommerce_storefront/tests/__init__.py`
- `ab_ecommerce_storefront/tests/test_catalog_cache.py`
- `ab_ecommerce_storefront/changelog.d/2026-10-18-catalog-cache.md`

## Validation and operating limits

- Fourteen catalog tests passed, including an isolated Chrome browser workflow, cache reuse/invalidation, Arabic and website isolation, denied public writes, savepoint rollback, live price changes, availability, context changes, pagination, offers and SSR/fragment parity.
- Eight JavaScript cache tests passed, including bounded eviction, corrupt storage, disabled storage and commerce-context changes.
- Two existing tests passed: Arabic view translation and recovery-route CSRF/generic responses. The existing authenticated-account test was blocked before requesting the page by `ab_store`'s IP login guard (`Login not allowed from this IP: unknown`). That security restriction was not bypassed.
- The targeted module upgrade passed on `ecom19_home_ux_20261015`, with HTTP/gevent ports 5492/5494, workers and cron disabled. Both Arabic catalogs passed `msgfmt --check-format`; Python/XML parsing and `git diff --check` passed. No new storefront UI strings were added.
- Test fixtures are rolled back. Development tests remain in the checkout and must be excluded from a production runtime package. A fresh install of the entire dependency chain and multi-worker/load tests were not run.
- Storage contains presentation fragments, not an offline catalogue. Search, category and filter changes still use normal server navigation. The fragment response still renders current product cards on the server, so it reduces transferred/repeated page content without removing all database or template work.
- Availability remains as current as Odoo's existing inventory/snapshot source. The browser-only delivery location picker does not select a server warehouse; this change does not introduce a new branch-to-stock mapping. Actual server warehouse, user or pricelist changes invalidate the page context when revalidated.
- The user's running PyCharm process, development flags and primary `ecom19` database were not restarted or upgraded. Loading these Python/XML changes in that process requires its normal targeted addon upgrade and restart.

Benchmark scripts, raw result hashes, test evidence and an isolated implementation patch are under `outputs/performance/catalog_cache/`. Timings are local HTTP TTFB with development mode disabled, not full browser-load measurements. The prior offers row-estimate discrepancy remains a separate investigation.

## Measured results

One excluded warm-up and ten measured requests per route/mode, same public Arabic session and development database, sequential baseline then optimized runs. The baseline already includes the earlier scoped JIT fix. p95 uses nearest rank and is the maximum of ten samples; these are development-machine measurements, not production percentiles.

| Route | Before median / p95 | After median / p95 |
| --- | ---: | ---: |
| Products | 1936.2 / 2654.9 ms | 1175.1 / 1559.4 ms |
| Second product page | 1739.8 / 2053.0 ms | 1179.1 / 1277.9 ms |
| Category | 1429.5 / 1622.5 ms | 828.3 / 895.0 ms |
| Offers | 1304.8 / 1454.0 ms | 466.5 / 539.6 ms |
| Search | 1211.3 / 1260.3 ms | 533.4 / 586.2 ms |

All 130 measured requests returned HTTP 200: 50 baseline, 50 optimized full-page requests and 30 optimized fragment requests. Product IDs/order, prices, offer and stock text hashes match. The normalized product grid and sidebar also match after accounting for whitespace, new cache metadata, CSRF values, equivalent URL percent encoding and image write-date cache keys refreshed by addon upgrades. This is semantic DOM equivalence, not byte-identical HTML.

Cached-fragment requests restored all 61/63/6 static fragments on products/page two/offers respectively. Their hydrated grids match the corresponding fresh server grids. Products' cached-fragment response was 113,334 bytes and 1096.2 / 1188.0 ms median/p95; offers were 17,140 bytes and 413.8 / 615.9 ms. The second-page fragment median was 1236.7 ms, slightly slower than its optimized full-page median in this sample; reduced transfer size is not a guarantee of lower server time on every request.

Full-page product HTML grew from 299,821 to 327,736 bytes because of cache metadata and serializer URL encoding; the fragment response is about 65% smaller than the optimized full page. Category caching reduced product-request SQL time from 1334.0 to 715.5 ms and queries from 153 to 130 (medians). These are rounded aggregate request SQL timings from Odoo logs, not isolated measurements of the four original JIT queries.

Temporary benchmark processes are stopped. Detailed samples and assertions are in `baseline.json`, `optimized.json` and `comparison.json` under the evidence directory.
