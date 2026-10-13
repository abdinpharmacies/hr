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
`pg_locks` in the current database without acquiring a runner lock. The UI says
Lease detected or No lease detected, and separately marks execution progress as
Unverified. A lease never produces a healthy/ONLINE badge. Last Completion is
the most recent retained queue completion, not a heartbeat or website-worker
health signal.

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
or execute any scheduled action. Aliases are scoped to individual functions
and nested functions, processed in statement order, and invalidated on unknown
reassignment. Conflicting aliases after conditional branches are not guessed.

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

Execution rows are not copied into another model. The dashboard uses aggregate
counts, field prefetching and paginated queries against the two inspected stores.
There is no product, order, or catalog scan. Definition status prioritizes running,
retrying, pending and failed executions, then falls back to the latest retained
execution. Current state counts and the latest execution are shown separately.
State filters match any retained execution of a definition, so a newer completed
execution cannot hide an older running or failed one. KPI counts are global.
Execution history follows the underlying framework's retention.

Review Required is an age warning, never a declaration that a worker is dead.
The viewer selects a threshold of 1–1440 minutes (default 30). Running age starts
at the recorded start, falling back to creation if no start is retained. Waiting
age starts at the latest available creation/enqueue/ETA timestamp. Future ETA
and recently enqueued jobs do not generate premature alerts. The definition,
execution list, details and review filter use the same rule. Running durations
advance; known finish/cancellation timestamps give fixed durations. A terminal
execution without a reliable end timestamp has Unknown duration.

Runtime refresh runs every 30 seconds while the dashboard is visible, unless the
viewer disables it. Automatic requests pause during discovery and while a request
is in flight; failures do not trigger a tight retry loop. Navigation removes the
timer and visibility listener. Last updated is the successful server snapshot;
after 90 seconds without a fresh snapshot the UI warns that the data is old.
Older responses and errors cannot overwrite a newer filter/sort result. Discovery
remains manual. Column sorting covers all matching definitions before pagination.

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
The module includes no cron, lifecycle hook, recurring source scan, new runner,
demo data or migration. Dashboard refresh reads runtime metadata only.

## Verification

Use targeted Odoo tests (`--test-tags /ab_queue_monitor`) on an unused HTTP
port, with `--workers=0 --max-cron-threads=0 --load=base,web,rpc`, to avoid
starting another runner. Transaction tests cover isolation, permissions,
deduplication, malformed/large sources, state mapping, differential discovery,
health evidence, duration boundaries, ETA-aware review warnings, scoped aliases,
active executions alongside newer completed ones, and classification context.
Run `node ab_queue_monitor/tests/check_monitor_refresh.cjs` for timer lifecycle,
request overlap, hidden tabs, stale snapshots and response ordering. HttpCase tests click Discover,
inspect idle/executed jobs and business context, and render Arabic mobile RTL.
All test-created records are rolled back. Test code is retained in the source
repository as explicitly requested; exclude `tests/` and bytecode when building
a runtime-only production addon archive.
