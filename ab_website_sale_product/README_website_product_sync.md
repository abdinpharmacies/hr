# Website Product Sync Performance

Measured on 2026-09-27 against an isolated copy of `ecom19`, using the installed
Odoo 19 ORM and addon overrides. The source database and its running jobs were
not upgraded or modified. Only the test database was upgraded.

## Root causes

The original cron ran ten batches in one transaction. Each queue line invoked
the product sync separately, which searched its template and repeatedly resolved
categories, Arabic languages, translations and tags. Existing templates and
variants were written even when their business values were unchanged. Missing
images reread the same placeholder. Recordset unions accumulated results inside
loops. Full-job preparation loaded the complete source selection and template
mapping into memory. The legacy periodic sync repeatedly selected the first
1,000 eligible products, without reliable change detection.

Python exception handling did not roll back failed SQL statements before
continuing. Manual processing could overlap cron processing, and progress was
not durable until the complete cron invocation committed.

## Implementation

- Read templates once per chunk and map by the existing unique `ab_product_id`.
- Bulk-create missing templates through the native ORM, preserving variant
  generation, mail behavior, constraints and installed overrides.
- Normalize scalar values using Odoo field conversion; compare many2many sets
  before writing. Preserve archived-template reuse and native variant recovery.
- Resolve canonical categories and relevant tags with bounded searches. Cache
  group mappings and language records within each chunk. Write Arabic category
  translations only when their current values differ.
- Check image presence with `bin_size=True`. Read the placeholder once per
  metadata chunk, apply it in groups of 25, flush image recomputations and release
  the corresponding binary field caches. Existing real images are preserved.
- Keep real image synchronization independent. Store source and applied image
  checksums only on image imports, so resized images can be recognized on later
  runs. A manual change to the destination image is still detected.
- Select pending queue lines through a partial index and checkpoint at most 250
  products. The legacy cron uses `ir.cron._commit_progress()` and respects its
  execution budget. The dedicated worker owns and commits a separate cursor for
  each checkpoint. Both release transaction caches after a commit.
- Attempt each chunk inside a savepoint. On failure, split the chunk and retry
  smaller groups until failing products are isolated. Record their error and
  attempt count. Serialization/deadlock exceptions propagate to Odoo's retry
  machinery rather than being misclassified as product failures.
- Keep completed job history. Retrying failures requeues only failed lines.
  Unchanged products have a separate counter. “Process All Remaining” schedules
  background work instead of holding an HTTP request open.
- Prepare full jobs using keyset pagination in groups of 2,000, without holding
  the entire catalog mapping in the ORM cache.

The original template matching, category classifier, tag ownership, publication,
prices, costs and stock-display initialization are preserved. No physical stock
quantity or external database write was introduced. There is no new queue
framework, cron record, hook or dependency.

## Delta synchronization

`website_sync_pending` is a stored dependency-driven flag, indexed only for
pending products. It tracks relevant source fields, delegated card fields,
category membership and ancestry, tag names/priorities, barcode names and stock
snapshot changes. The recursive stored group path propagates ancestor edits.
Successful synchronization clears the flag; failed products remain pending.

The existing `cron_sync_website_products(limit=1000)` now queues a bounded dirty
selection. Its scheduled action keeps its existing activation state and interval;
this change does not silently enable it. The console also has “Sync Changed
Products”. Each invocation examines at most the requested limit, capped at 5,000.
Dirty products that are ineligible and have no website template are acknowledged
without creating templates. Repeated scheduled invocations drain the backlog.

Delta jobs also update already-linked products that become inactive, unavailable
or unsaleable, using the same values as an explicit individual sync. Full sync
retains its original active/saleable/website-available selection.

The flag also tracks synchronized template/variant fields, category/tag metadata
and destination image changes. After changing classifier code or language
configuration, explicitly mark affected sources pending before reconciliation.
Dirty tracking relies on ORM dependency
notifications; SQL writers must explicitly notify Odoo of their changes. There
is no fragile timestamp watermark. The first upgrade marks existing sources
pending once so delta processing can establish its initial state.

## Concurrency and indexes

Execution deliberately remains single-writer. Job rows use Odoo 19
`try_lock_for_update()` (`FOR UPDATE SKIP LOCKED`). A database-local transaction
advisory lock, key `(190019, 731)`, also covers direct product sync calls, because
category/tag creation is shared across jobs. These two isolated SQL lock calls
do not change business data. A partial unique index enforces the existing rule
of one running job. The inspected database had one running job before upgrade.

Multiple worker processes can invoke the runner safely, but they will serialize
at chunk boundaries. This is concurrency safety, not parallel throughput.
Removing that serialization would require separating shared taxonomy writes and
partitioning products; no multiprocessing was added.

| Index | Query supported | Trade-off |
| --- | --- | --- |
| Existing template `ab_product_id` indexes, including uniqueness | Batch template lookup and one source-to-template mapping | Reused without adding a redundant index |
| `ab_product_website_sync_pending_idx` | Dirty products ordered by ID | Index maintenance when dirty state changes |
| `ab_website_product_sync_job_line_pending_job_idx` | Pending lines for one job ordered by ID | Entries removed as lines complete |
| `ab_website_product_sync_job_one_running_job` | Atomic enforcement of one running job | Intentional single active-job restriction |

PostgreSQL `EXPLAIN` selected index-only scans for both the dirty-product and
pending-line queries on the copied database.

## Measurements

The five scenarios use the same deterministic 250-product fixture, shared
categories/tags, prices and images. Every measured phase flushes ORM writes and
starts with an invalidated record cache. Setup is excluded. All phases completed
with zero exceptions. Query counts come from the Odoo cursor. The initial
baseline was captured before editing; the table below uses a verification run
of the preserved original methods against the same upgraded test schema and
the final implementation. This avoids mixing datasets or storage configurations.

| Scenario | Before seconds | After seconds | Before products/s | After products/s | Queries before / after |
| --- | ---: | ---: | ---: | ---: | ---: |
| Initial import, placeholder images | 49.586 | 26.223 | 5.04 | 9.53 | 22,542 / 4,640 |
| Existing products, changed price | 5.696 | 0.417 | 43.89 | 599.48 | 5,028 / 282 |
| Unchanged metadata | 5.826 | 0.171 | 42.91 | 1,464.45 | 5,025 / 25 |
| Existing real images, metadata sync | 4.433 | 0.171 | 56.40 | 1,461.96 | 5,025 / 25 |
| Repeat with unchanged real images | 4.461 | 0.172 | 56.04 | 1,453.39 | 5,025 / 25 |

Creation produced 250 templates in both implementations. Price updates touched
250 templates in both. Each unchanged scenario previously wrote 250 templates;
the final implementation skipped all 250 template writes. The image scenarios
measure metadata sync with real images already present, not file-directory scan
or image-upload throughput.

CPU time for creation fell from 36.595 to 19.346 seconds. Price-update CPU fell
from 3.699 to 0.301 seconds; unchanged metadata CPU fell from 3.805 to 0.147
seconds. The remaining creation cost is substantially CPU/ORM/image processing;
wall time minus process CPU is not a measurement of PostgreSQL time alone.

Peak process RSS across the five scenarios was 470.4 MB before and 459.4 MB
after. Initial creation alone used more peak memory after bulk creation
(459.4 MB versus 202.2 MB); memory improvement is not claimed for that phase.
This is why the default checkpoint remains bounded at 250 and image subgroups
at 25. RSS high-water marks include registry and fixture memory and are not
per-operation allocation measurements.

A separate 500-product job committed two 250-product chunks. RSS after the
checkpoints was 411.9 MB and 420.9 MB; process peaks were 455.1 MB and 464.1 MB.
The chunks took 26.001 and 40.709 seconds. This verifies cache release/resume
over two commits, not a long-duration memory or latency guarantee.

Full-job preparation queued 31,255 eligible products in 4.231 seconds with
384 queries and 171.8 MB peak RSS. It did not synchronize that full catalog.

### Batch-size experiment

A separate 5,000-product fixture with small existing images tested actual
metadata chunk sizes by overriding the development-only chunk limit. Each
measurement rolls back its price changes. The process peak was 292.9 MB,
including fixture preparation; all scenarios had zero failures.

| Chunk size | Unchanged seconds | Unchanged products/s | Price update seconds | Price update products/s |
| ---: | ---: | ---: | ---: | ---: |
| 250 | 0.105 | 2,383.64 | 0.326 | 766.23 |
| 500 | 0.195 | 2,568.55 | 0.636 | 785.88 |
| 1,000 | 0.363 | 2,754.06 | 1.262 | 792.66 |
| 2,000 | 0.709 | 2,821.31 | 2.516 | 794.97 |
| 5,000 | 1.749 | 2,858.90 | 6.377 | 784.09 |

Larger chunks modestly improved unchanged throughput but gave little additional
price-update throughput. These results do not establish that large image-heavy
creation chunks are safe. Process Next Batch honors the selected product count
using internal chunks of at most 250. The manual action uses one request
transaction, so larger selections can take longer and risk HTTP timeouts.
Process All Remaining runs in the background and commits after each chunk of
at most 250, independent of the dropdown and global cron execution budgets.

## Dedicated background worker

The installed `integration_queue_job` addon provides a shared queue runner, but
no active runner was found on this server. Activating that shared runner would
also make unrelated integration jobs eligible for execution. The existing
Website Product Sync job and line records already supply the durable queue,
so the module now provides a small dedicated worker instead of another queue
framework, shared runner activation, or HTTP-owned background threads.

Process All Remaining checks that the dedicated worker is online, persists the
requester/company and a background request flag, and returns immediately. Full
queue preparation for a draft job also happens in the worker. No products are
processed by the button request. Existing running jobs keep their checkpoints.

The worker:

- Selects only explicitly requested Website Product Sync jobs in this database.
- Holds session advisory lock `(190019, 732)` to exclude duplicate workers.
- Rechecks the requester's permissions and company before each checkpoint.
- Reuses the existing row/catalog locks, ORM sync and per-product recovery.
- Commits at most 250 products per cursor regardless of Products Per Batch.
- Rolls back serialization/deadlock failures and retries after a bounded wait.
- Stores unexpected errors after rollback and pauses the request for inspection.
- Stops at cancellation/completion; gracefully finishes a checkpoint on SIGTERM.
- Resumes committed requests after process restart without browser involvement.

Global cron excludes jobs owned by this background mechanism. The scoped form
controller polls read-only progress every two seconds and reloads changed
progress only when the form has no unsaved edits. Closing the browser does not
stop the worker. Failed product lines remain available for the existing explicit
retry action; after requeuing them, Process All Remaining resumes processing.

### Remaining products and resume

Check Remaining prepares a snapshot of eligible products that are missing a
linked template or marked pending. Clean linked products are counted as already
synchronized without creating queue lines or invoking product writes. Show
Remaining lists only pending/failed lines, separated into Missing on Website and
Needs Review. A pending marker means review is required, not that a write will
necessarily occur. The existing changed-value comparison makes that decision.

The percentage includes the already-synchronized baseline. A snapshot with one
clean, one changed and one missing product starts at 33.33%, not zero. Failed
products remain in the outstanding count. New changes after preparation belong
to a subsequent snapshot; progress is not a real-time catalog consistency audit.

All reuses a running or interrupted job, preserving successful line attempts.
Failed lines are requeued when resuming. Completed historical jobs are preserved;
another All prepares a fresh remaining-only snapshot. Old cancelled jobs older
than a completed full sync are not revived. Legacy full queues fast-forward
clean pending lines through bounded metadata updates without touching templates.
Metadata preparation can update more than 250 queue lines in a transaction;
actual product synchronization remains limited to 250 products per checkpoint.

The remaining-products update was activated on ecom19 on 2026-09-28 after backup
to `/tmp/ecom19_before_website_sync_remaining_20260928.backup`. The targeted module
upgrade, web/worker restart, HTTP health check and runtime Arabic labels passed.
No live catalog synchronization was submitted during verification.

The worker never starts an HTTP listener, global Odoo cron, or the shared queue
runner. It does not alter `max_cron_threads` in any configuration file.

Deployment uses a user-owned systemd service with automatic restart:

```bash
systemctl --user link /opt/odoo19/custom-addons-ecommerce/ab_website_sale_product/deploy/website-product-sync.service
systemctl --user enable --now website-product-sync.service
systemctl --user status website-product-sync.service
```

The supplied unit targets this repository's ecom19 configuration. Adjust paths
and database before using it elsewhere. User lingering must be enabled when the
worker should survive logout. Restart this service after Python code upgrades.
To run it directly for diagnosis, use the unit's `ExecStart` command. Do not run
the committed-fixture integration test against a production database.

On 2026-09-28 the ecom19 activation was approved and completed after a dedicated
PostgreSQL backup at `/tmp/ecom19_before_website_sync_background_20260928.backup`.
The target module was upgraded, the web server restarted with cron still
disabled, and the dedicated user service enabled with lingering. The existing
job remained at 30,000/31,253 and was not automatically opted into background
processing. Temporary `/tmp` backups should be moved to managed retention before
the next reboot or cleanup.

## Validation and reproduction

- 48 functional tests passed, covering creation, changed/no-op updates, categories,
  tags, translations, delegated/ancestor/barcode invalidation, archived templates,
  delta selection/unpublishing, partial SQL failure, retry, barcode conflict,
  duplicate execution, resume, cron budget, image replacement/resizing and access.
  The five batch-selection regressions cover every dropdown option, queue
  boundaries, selection changes, lock contention, and the background chunk cap.
- Seven remaining/resume regressions cover clean/changed/missing previews,
  all-clean completion without sync calls, cancelled-job continuation, legacy
  queue fast-forwarding, console reuse, destination edits and failed progress.
- The remaining-products browser test verified a three-product snapshot at
  33.33%, two outstanding rows, one creation and one update, then automatic 100%
  completion. Desktop/mobile screenshots were inspected with no JavaScript errors.
- Eight background regressions cover asynchronous submission, deferred draft
  preparation, worker availability, requester permissions, real product creation,
  cancellation, manual-size independence, and exclusion from global cron.
- The separate-process worker check verified checkpoint resume, duplicate-worker
  exclusion, transaction recovery and one-click completion without more HTTP
  calls. The measured button method took 0.0007 seconds on that test fixture.
- Headless Chrome verified automatic completion of a 10,001-line synthetic queue
  with no JavaScript errors or calls to Process Next Batch. Desktop and mobile
  screenshots were inspected. These intentionally skipped queue lines exercise
  orchestration, not product-import throughput.
- Two real PostgreSQL connections verified row-claim exclusion, catalog-lock
  exclusion, committed resume and duplicate execution without extra products.
- A separate two-transaction test confirmed that an ancestor/category edit racing
  with sync forces transaction retry and preserves the dirty marker.
- Original/final outputs matched for four products across creation, unchanged,
  changed and unpublished cases, including descriptions, categories, tags,
  prices, stock-display values, variant barcode and image checksum.
- Targeted module upgrades passed on the copy. Both Arabic catalogs passed
  `msgfmt --check-format`; the delta and retry button labels differed between
  `en_US` and `ar_001` at runtime.

Development tools live in `tests/`; exclude development tests and generated
bytecode from production addon packaging. The benchmark can be run in an Odoo
shell configured for an isolated database with this checkout in `addons_path`:

```python
from odoo.addons.ab_website_sale_product.tests.benchmark_website_sync import run_benchmark
try:
    results = run_benchmark(env, label="after", size=250)
finally:
    env.cr.rollback()
```

`benchmark_website_sync_batches.py` runs the size sweep when executed with the
shell's `env`. The three `check_website_sync_*.py` scripts test real transactions
and intentionally commit test fixtures; they refuse databases whose names do
not start with `codex_website_sync_`. Run them only on a disposable copy.

## Files changed

| File | Purpose |
| --- | --- |
| `__manifest__.py` | Register the module-scoped background progress form controller |
| `models/ab_product.py` | Bulk synchronization, changed-value comparison, shared lookups and dirty dependencies |
| `models/website_product_sync_job.py` | Checkpoints, claiming, bounded selection, delta jobs, recovery and counters |
| `models/product_template.py` | Source/applied image checksum storage and idempotent image application |
| `models/product_image_sync.py` | Reuse image checksums and recover image-write failures through savepoints |
| `views/website_product_sync_job_views.xml` | Delta/retry buttons, unchanged counts and attempt visibility |
| `i18n/ar.po` | Arabic labels and help with exported references |
| `i18n/ar_001.po` | Equivalent Arabic labels for the second supported locale |
| `tests/__init__.py` | Register the new functional tests |
| `tests/test_website_product_sync.py` | Product, job, delta, failure and access regression coverage |
| `tests/test_website_category_mapping.py` | Changed/resized images and manual replacement coverage |
| `tests/benchmark_website_sync.py` | Repeatable five-scenario benchmark |
| `tests/benchmark_website_sync_batches.py` | Actual metadata chunk-size experiment |
| `tests/check_website_sync_concurrency.py` | Real PostgreSQL claiming/checkpoint checks |
| `tests/check_website_sync_delta_race.py` | Concurrent related-source edit check |
| `tests/check_website_sync_background_worker.py` | Separate-process resume, transaction recovery and one-click completion checks |
| `services/__init__.py` | Worker service package |
| `services/website_sync_worker.py` | Dedicated database-scoped checkpoint loop and recovery |
| `worker.py` | Standalone worker entry point without HTTP or global cron |
| `deploy/website-product-sync.service` | User-owned service supervision and restart |
| `static/src/js/website_sync_form.js` | Read-only automatic progress refresh scoped to this form |
| `README_website_product_sync.md` | Findings, measurements, reproduction and limits |
| `changelog.d/2026-09-27-website-product-sync-performance.md` | Commit reference and current change record |
| `changelog.d/2026-09-28-website-sync-batch-selection.md` | Manual batch-size correction |
| `changelog.d/2026-09-28-website-sync-background-worker.md` | Asynchronous worker and activation record |

The job model and job view already existed as untracked work when this task
started. Other pre-existing working-tree edits were preserved.

## Limitations and next step

Live website latency under customer load was not measured. These are local
benchmarks, not production SLAs. Per-product updates with different values still
use ORM writes; image resizing and native variant/attachment work remain costly.
A chunk can exceed a very small configured cron time budget before its next
checkpoint. Large direct, synchronous callers still own their transaction; use
the background job for large catalogs.

The next optimization should profile initial image creation with native Odoo
SQL and periodic collectors, then evaluate a separate image-processing queue.
Creation is now much slower than metadata updates, and its CPU/memory cost is
measured. Additional parallel metadata workers are not the next justified step.

The initial performance work was tested without deployment. The subsequent
2026-09-28 asynchronous-worker change was explicitly approved for activation:
ecom19 was backed up and upgraded, its web server restarted, and the dedicated
worker enabled. Global cron remains disabled. No Git commit was made.
