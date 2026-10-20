# Scoped JIT control for storefront offers

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

- Disable PostgreSQL JIT for the current shop transaction when the recognized deal filter includes `discount` or `today`, including mixed deal filters. Execute `SET LOCAL jit = off` on `request.env.cr` before the parent product lookup.
- Keep the setting through native price-range aggregation, custom price-range aggregation, histogram calculation and response rendering. PostgreSQL restores the connection setting at commit or rollback.
- Preserve ordinary shop, search, category, coupon-only and unrelated requests. Preserve the existing queries, domains, ordering, availability, price logic and pagination.
- Preserve the pre-existing availability changes in this controller, documented in `2026-10-18-navigation-performance.md`. Other existing working-tree changes are outside this task.

Files changed:

- `ab_ecommerce_storefront/controllers/shop.py`
- `ab_ecommerce_storefront/changelog.d/2026-10-18-scoped-jit.md`

The isolated runtime diff is saved in `outputs/performance/scoped_jit/implementation.patch`. Development validation scripts and evidence live outside the runtime addon in `outputs/performance/scoped_jit/`: `validate.py`, `benchmark.py`, `tests.json`, `pagination.json`, `existing-tests.txt`, `languages.json`, `sql.json`, `http.json` and `validation.json`.

## Choice and request lifecycle

Option A (`SET LOCAL jit = off`) was selected. The threshold candidate (`SET LOCAL jit_above_cost = 3000000`) performs similarly on the current queries, but their estimated costs are approximately 2.75 million. A change in estimates could cross that threshold and bring back compilation overhead. These short, interactive offer calculations benefit from disabling JIT throughout their narrowly selected request transaction.

The Arabic `/ar/shop/category?deal=discount` request reaches `ab_storefront_category_listing`, then native `WebsiteSale.shop`, then the existing `_shop_lookup_products` override. `/shop/offers` redirects to this listing; native shop/category/search routes with the same offer filter reach the same override.

The four queries execute through these paths, in runtime order:

1. Offer candidates: `_shop_lookup_products` → native lookup → `website._search_with_fuzzy` → `_search_exact` → `website.searchable.mixin._search_fetch` → product search. `product.template._search_get_detail` appends `_ab_storefront_deal_candidate_domain`, which includes `_ab_storefront_offer_candidate_domain` for discount/today filters.
2. Native range: `WebsiteSale.shop` → `_get_shop_domain` → `Product._search` → `request.env.execute_query` for `MIN/MAX(list_price)`.
3. Custom range: `_get_additional_shop_values` → `_ab_storefront_price_range_values` → `_ab_storefront_available_price_range` → `request.env.execute_query`.
4. Histogram: `_ab_storefront_available_price_range` → `_ab_storefront_price_histogram` → `request.env.execute_query`.

The installed Odoo 19 source creates/selects the request cursor in `Request._serve_db` before dispatch. `service.model.retrying` invokes dispatch and commits afterward. `ir.http._dispatch` flattens QWeb responses before returning. No intervening commit, rollback or cursor replacement was found in these call paths. Runtime observations confirmed all four queries used one backend PID and transaction ID with `jit=off`, through rendering.

The code reapplies the setting on every lookup invocation, including after an Odoo transaction retry. Cursor close rolls back before returning its connection to the pool. Later savepoint rollbacks preserve the setting; rollback to a savepoint created before the setting cancels it, and re-entering the lookup reapplies it. There is no local catch/recovery across such an earlier savepoint in the inspected request path.

[PostgreSQL SET documentation](https://www.postgresql.org/docs/16/sql-set.html) specifies transaction-end and savepoint reset behavior. [JIT decision documentation](https://www.postgresql.org/docs/16/jit-decision.html) explains the compilation overhead for short queries and dependence on estimated plan costs.

## Measurements

PostgreSQL 16.15, database `ecom19`. Original evidence was inspected in `outputs/performance/2026-10-18-jit-validation.json` and the saved four SQL statements under `/tmp/ab-storefront-sql-review-20261018/public-jit-on`.

SQL execute plus fetch, ten measured rounds per mode after excluded warmups, alternating mode order, read-only repeatable-read transactions with statement/lock timeouts:

| Configuration | Combined median | Combined p95 |
| --- | ---: | ---: |
| PostgreSQL defaults | 5863.972 ms | 6037.273 ms |
| Transaction-local JIT off | 91.859 ms | 123.479 ms |
| Transaction-local threshold 3000000 | 91.335 ms | 118.464 ms |

All query result hashes and row counts match: candidates 4, custom range 1, histogram 3, native range 1. Separate EXPLAIN ANALYZE runs retain identical plan structure, indexes, predicates, costs, estimates, actual rows and loop counts. Total JIT compilation time with defaults was 5864.659 ms; neither alternative produced a JIT section. EXPLAIN execution times are separate from execute/fetch timings.

HTTP used two unchanged-code snapshots differing only in the JIT patch, temporary loopback listener 5492/gevent 5494, `Host: 192.168.1.186:4092`, one public Arabic session/cookie jar, development mode disabled, zero cron threads, queue channels `root:0`, and tracking disabled. Warmup was excluded for each process and route. Order was defaults → scoped → scoped → defaults, five measured offers requests per process. No SQL instrumentation ran during HTTP timing.

| Route | Requests per mode | Default median / p95 | Scoped median / p95 |
| --- | ---: | ---: | ---: |
| Offers | 10 | 6799.549 / 9403.743 ms | 1062.433 / 1322.803 ms |
| Shop | 3 | 1607.682 / 1649.422 ms | 1567.576 / 1701.499 ms |
| Search | 3 | 969.156 / 978.889 ms | 986.904 / 1120.893 ms |
| Category | 3 | 1441.079 / 1651.743 ms | 1542.284 / 1571.054 ms |
| About | 3 | 376.695 / 431.423 ms | 420.812 / 443.251 ms |

All 44 measured requests returned 200 with no measured HTTP errors. Every route's HTML matched after normalizing only CSRF tokens. The numeric category URL redirected to its Arabic slug in an initial incomplete attempt; the final comparison used the canonical link and restarted all samples. Raw captures and process logs remain under `/tmp/ab-storefront-scoped-jit-20261018`.

These are local warm-cache HTML TTFB measurements, excluding browser rendering and asset downloads. p95 uses nearest rank, which is the largest sample for ten observations. The machine was shared and baseline timings varied. Three samples on each control route show overlapping timing ranges and identical output; they do not establish production latency percentiles or rule out small regressions under load.

## Validation results

- Seventeen distinct focused checks now pass: filter scope, pre-query setting, commit/rollback, failed SQL, savepoints, exact pooled-connection reuse, independent connection isolation, actual Odoo retry, all four query hashes/row counts, prices/offers, price filters, two-page pagination, ordinary shop/search/category and coupon-only defaults.
- The final broad run passed 16 of 17 checks. The pagination harness initially treated page 1 as the second page. Installed Odoo 19 uses one-based pagination. Correcting the input to page 2 passed the focused rerun, with distinct products on both pages. `tests.json` retains the initial result; `pagination.json` records the corrected passing rerun. No implementation change was needed.
- All ten existing storefront performance tests passed on `ecom19_home_ux_20261015`: full-catalog availability parity (31,255 candidates → 23,832 retained), public caller scope/order, empty candidates, snapshot/service behavior and image handling. The runner then failed a separate action-label assertion because the clone retains `Storefront Offers` in both language contexts; this is recorded in `existing-tests.txt` and `languages.json`.
- Targeted `-u ab_ecommerce_storefront --stop-after-init --no-http` completed with exit 0 on the idle existing development clone `ecom19_home_ux_20261015`, using this checkout, ports 5496/5498, zero cron threads and disabled queues. No `-u base` was run. Registry/view loading succeeded. Existing warnings and the clone's missing logo filestore object remain; no runtime package or browser image verification is claimed.
- Both Arabic catalogs passed `msgfmt --check-format`. A separate read-only runtime check confirmed different English/Arabic homepage view content (`en_US`/`ar_001`). This patch adds no UI strings and changes no translation files.
- Python parsing and `git diff --check` passed. No manifest, dependency, ACL, record rule, field, XML ID, business data operation or frontend behavior changed in this patch.
- Authentication, checkout and browser suites were not run because those paths are unchanged. A fresh installation of the entire dependency chain was not run; the focused upgrade was validated.

Reproduce the focused checks with:

```bash
/opt/odoo19/venv19/bin/python outputs/performance/scoped_jit/validate.py --config /opt/odoo19/custom-addons-ecommerce/odoo19.conf --database ecom19 --output /tmp/scoped-jit-tests.json
```

Run `benchmark.py` with the same config, `--queries-dir /tmp/ab-storefront-sql-review-20261018/public-jit-on`, `--samples 10`, an output JSON path, and `--phase sql` or `--phase http`. The HTTP harness uses port 5492 only if free and always stops its child processes.

## Scope and remaining work

No session-level JIT SET, persistent database/role setting, global PostgreSQL configuration, index or query-domain change was made. Effective JIT settings and database/role JIT overrides match before and after both benchmarks. The existing Odoo service was not stopped or restarted, and `ecom19` was not upgraded. Temporary servers are stopped. The normal deployment process must load the Python change into the running service.

The setting deliberately applies to the remainder of affected shop transactions, including rendering. Homepage offer calculations outside that controller remain unchanged. Future changes that introduce an intervening transaction boundary must rerun these checks.

Separate follow-ups: investigate the candidate estimate of 21,098 rows versus 4 actual rows; consider reusing native/custom price-range aggregation and batching category reads. No domain rewrite, statistics change or index was included here. The explicitly requested pg-graph skill was inspected; its graph-only workflow does not apply to this relational JIT issue, and no graph operation was performed.
