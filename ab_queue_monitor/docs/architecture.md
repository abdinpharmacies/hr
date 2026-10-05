# Queue Monitor

## Inspected Installation

The installed provider is VentorTech `integration_queue_job` 19.0.1.0.3,
an OCA-derived implementation. The separate `queue_job` addon is present on disk
but uninstalled. Both use the model name `queue.job`; the monitor deliberately
depends on the installed provider, not on the other addon.

The provider stores UUID, model/method, channel, priority, retry, ETA, creation,
enqueue/start/completion/cancellation timestamps, execution time, worker PID,
exception fields, serialized recordsets, arguments, results and dependency UUIDs.
The state selection is read from the running registry. This version exposes
`wait_dependencies`, `pending`, `enqueued`, `started`, `done`, `failed`, and
`cancelled`. A postponed retry remains pending with its retry counter retained.
An unrecognized future state is displayed as Unknown.

`with_delay().method()` enqueues immediately. `delayable()` builds a graph and
`delay()` schedules it. Function/channel declarations live in
`queue.job.function` and `queue.job.channel`. UUIDs identify executions;
model/method/backend/module identify definitions. Identity keys deduplicate
enqueuing, and `dependencies` carries parent/child UUIDs.

The runner holds database advisory lock `2293787760715711918`, listens for queue
notifications, and dispatches HTTP requests to `/queue_job/runjob`. That route
executes work and is never used as a health probe. Queue Monitor reads
`pg_locks` in the current database without acquiring a runner lock. ONLINE means
the runner lease is held, not that HTTP dispatch has been proven responsive.
Absence of the lease means UNKNOWN. The displayed last activity is the most
recent retained completion, not a fabricated heartbeat.

Classification lives in `ab_website_sale_product`, model
`ab_product_classification_run`. Its `_process_checkpoint` and `_apply_control`
methods have explicit queue function declarations. The queue's recordset field
provides the run relation; no single run ID or product count is hard-coded.
Only stored run counters are read, under the viewer's business-model ACLs.

Website sync also has a distinct `ab_website_product_sync_job` store and a
dedicated worker calling `_process_background_checkpoint`. Its adapter reads
the inspected fields directly. The monitor does not start that worker or invoke
its lock-taking health method. No standalone `ab_product_classification` or
`ab_stock_sync` addon is installed in the inspected database.

## Manual Discovery

Only the administrator's Discover/Resume button calls `start_scan` and then
`scan_step`. Every step is a separate HTTP request and transaction. A partial
unique index and row lock prevent overlapping sessions/steps. Closing the
dashboard stops requesting steps. Resuming requires another explicit click.
Pausing waits for the in-flight request; cancellation discards only staging
metadata. Completed results remain intact until the next scan finishes.

Installed module names come from `ir.module.module`; paths use Odoo's module
resolver and configured addon search path. The scanner uses `ast`, never
imports addon source or evaluates it. It detects delay calls and aliases,
legacy job decorators, automatic delay patches, and thread targets. Registered
queue function declarations, existing scheduled-action model calls, and the
inspected website worker add evidence for idle definitions. It does not create
or execute any scheduled action.

The scan processes at most 30 files or approximately 1.5 seconds per request.
Python files over 2 MiB and addon trees exceeding 20,000 Python files produce
warnings. Directory symlinks, tests, migrations, demo data and static asset
trees are excluded. Bad syntax, encoding and inaccessible files are recorded
without aborting the scan. Incomplete modules are not marked removed. Limits
bound ordinary trees; a single slow filesystem read cannot be preempted by the
Python request time budget.

Definitions merge by addon, backend, model and method. Source ownership is
resolved from already-loaded registry methods, including inherited methods.
There is no source scan during dashboard loads, runtime refresh, model reads,
installation or startup. Discovery writes only monitor metadata.

## Runtime And Security

Execution rows are not copied into another model. The dashboard uses indexed
domains, aggregate counts, field prefetching and paginated queries against the
two inspected stores. There is no product, order, or catalog scan. Definition
status describes its latest retained execution; KPI counts describe all current
executions. Execution history follows the underlying framework's retention.

The technical monitoring roles intentionally have installation-wide visibility
of technical metadata. They do not confer business-record access. Ordinary
internal users have no monitor access. Readers cannot create or edit discovery
records; administrators invoke guarded workflow methods which write only the
monitor's own records. Detailed traceback frame locations are administrator-only.
Exception messages, source lines in tracebacks, argument values and result
payloads are withheld because they can contain arbitrary secrets. No queue
mutation action, code execution, source editor, shell command or config editor
is exposed. Source links open the definition's metadata view, not local files.

## Extension Points And Limits

Add a service adapter to `adapters()` for another known runtime store. Override
an adapter's `context()` for another reliable business relation, and preserve
the viewer's ACL checks. Arbitrary custom schedulers cannot be discovered with
certainty from naming conventions alone. Dynamic method names and dynamically
generated code may be missed; thread and scheduled-action definitions show
Unknown because those systems provide no retained execution history to this
adapter. Unknown ownership is not guessed.

No queue configuration, running service, product record or classification
behavior is changed. Existing jobs may continue to progress while monitoring.
The module includes no cron, lifecycle hook, recurring scan, polling timer,
new runner, demo data or migration.

## Verification

Use targeted Odoo tests (`--test-tags /ab_queue_monitor`) on an unused HTTP
port, with `--workers=0 --max-cron-threads=0 --load=base,web,rpc`, to avoid
starting another runner. Transaction tests cover isolation, permissions,
deduplication, malformed/large sources, state mapping, differential discovery,
health evidence, and classification context. HttpCase tests click Discover,
inspect idle/executed jobs and business context, and render Arabic mobile RTL.
All test-created records are rolled back. Test code is retained in the source
repository as explicitly requested; exclude `tests/` and bytecode when building
a runtime-only production addon archive.
