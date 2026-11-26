# Sales Chatter timing — 2026-11-26

The approved source changes are implemented in Sales Chatter **19.0.1.44.0**,
Website **19.0.1.18.0**, and the messaging gateway. Performance acceptance is
**partial**: active-chat targets pass for one agent; reply acknowledgement remains
slightly above its target in the final combined workload, and ten-agent contention
fails. This is not a production-capacity certificate. Operator-managed services were not upgraded or restarted.

## Implementation

The active conversation now refreshes independently of inbox and contacts, with
one active request and one pending rerun per resource. Employee/company/navigation/
website-target checks discard superseded responses. Contacts refresh on opening,
explicit search/save and authorized directory invalidation. Existing websocket
updates and five-second recovery timers remain.

`workspace_updates` authorizes the target and caps both new pages and requested
visible IDs at 50. It combines serialization when the union fits one page and
otherwise uses two capped reads. Ingestion cursors drain bursts across rendering
frames, including backdated messages. Visible edits, reactions and delivery states
refresh without re-fetching every cached page; older rows refresh on scrolling.
Composer contents and history/search/quote navigation remain intact. Replies
coordinate with their own in-flight read request for at most 250 ms; server locks,
authorization, claim/assignment, uncertain outcomes and delivery operations remain.

Private invalidations contain capped authorized canonical conversation IDs,
change categories and opaque timing IDs. Read changes are employee scoped;
website preferences invalidate their exact conversation. Login, reconnect,
overflow, scope changes and recovery polling reconcile complete notifications.
Page previews use batched timestamp/ID aggregates while incoming inbox ordering
and cursors remain unchanged. Website target reads/unread metadata/lifecycle
lookup use scoped searches and counts. A 1,000-message website regression rejects
calls to full-history/unread recordset helpers. No index was added: a temporary
message-event index retained the same measured query plan (20.8 ms before,
33.0 ms after in the diagnostic sample), so it lacked supporting evidence.

Gateway idle defaults are 250 ms with finite 100–2,000 ms configuration bounds.
The existing fair scheduler, immediate continuation after progress, leases,
destination ordering, receipts and retry rules are retained. Telegram's 30-second
long poll is unchanged. Blocking provider requests still occupy their worker;
separate production/pilot account commands are in the gateway README.

## Measured results

API fixtures were repeated three times with identical synthetic data per method.
The 60/600 fixture has 30 samples per API/run; the 1,000/10,000 fixture has five.
Large-fixture p95/p99 are coarse sample statistics. The large fixture uses 1,000
gateway-created first messages plus 9,000 batched ORM messages, not a complete
10,000-event ledger. Planner statistics were refreshed after seeding. Ten-agent
and large-fixture tests were separate. Other local validation and user processes
shared the host, so these are local observations rather than isolated CPU limits.

All table times are milliseconds; cells show **p50 / p95 / p99**.

| API/workflow | Before | After |
|---|---:|---:|
| Active refresh, 1,001 loaded messages / 50 visible | 1960 / 2404 / 2562 | 137 / 243 / 288 |
| Inbox, 60 conversations | 380 / 457 / 509 | 131 / 223 / 314 |
| Complete notifications, 60 conversations | 767 / 953 / 1013 | 356 / 748 / 1025 |
| Inbox, 1000 conversations | 396 / 680 / 680 | 330 / 489 / 489 |
| Complete notifications, 1000 conversations | 22209 / 27658 / 27658 | 18123 / 23030 / 23030 |

The active refresh uses **22 → 1 browser requests**, p95 **498 → 85 SQL
statements**, and **843,788 → 42,934 serialized JSON bytes**. Inbox page queries
fell **118 → 61**. Final inbox and complete-notification comparisons stayed within
the 10% regression limit. Complete traversal still takes roughly 23 seconds at
10,000 unread messages and can delay notification reconciliation; targeted
invalidations avoid that work during ordinary updates. Active chat is independent.
Initial baseline full-traversal byte counts were not recorded (JSON `null` was
mistakenly measured as four bytes); those values are not response-size evidence.

The final real loopback gateway → SQLite → Odoo → websocket → rendered-message
run used one staff agent, 30 text arrivals and 30 queued replies. All messages
rendered, with no browser console errors. Opaque IDs correlate committed messages
and render events; clocks are from the same host. Gateway durable timestamps are
observed at ingest return, so they can overlap worker claims slightly.

| Final single-agent boundary | p50 | p95 | p99 | Objective |
|---|---:|---:|---:|---|
| Odoo commit → rendered message | 310 | 383 | 432 | p95 ≤ 1,000: pass |
| Durable queue acknowledgement → rendered message | 595 | 752 | 836 | p95 ≤ 2,000: pass |
| Reply submission → rendered queued acknowledgement | 211 | 554 | 583 | p95 ≤ 500: **miss** |

The outgoing-only control previously measured p95 316 ms; the final combined
workload is the acceptance result. The ten-agent shared-conversation run completed
25 arrivals across ten views before a 30-second timeout on the next arrival.
Completed samples had commit-to-render p95 about 4.2 seconds. Existing concurrent
read/reply serialization and a deferred durable event were observed; the event
later committed and the queue drained. Ten-agent reply contention also timed out.
These failed/partial runs are retained, not reported as passing workloads.

With the websocket handshake blocked, three arrivals rendered with no correlated
push events, within 907 ms from reception. Local read activity also triggered
refreshes; this does not isolate a five-second timer as the sole recovery cause.

Idle comparisons used three 10-second, 5-message/s durable-queue runs per setting.
Odoo was mocked in this benchmark. CPU is the maximum observed process CPU seconds
per approximately 10-second run, including its producer/SQLite work; connections include workload and idle polling, while SQL counts omit connection-setup PRAGMAs. The provisional
6%-of-one-core CPU budget rejected 100 ms; 250 ms met that budget in this fixture.

| Idle wait | Queue-wait p95 | CPU seconds | Connections per run |
|---|---:|---:|---:|
| 0.1 s | 393 ms | 0.671 s | 662 |
| 0.25 s | 349 ms | 0.519 s | 497 |
| 0.5 s | 497 ms | 0.430 s | 413 |
| 1 s | 995 ms | 0.383 s | 338 |
| 2 s | 1974 ms | 0.357 s | 298 |

The final five-minute queue workload processed **1649** events at
5/s with a 20/s, ten-second burst. Remaining backlog: **0**.
Observed post-burst drain: **0.008 seconds**;
queue-wait p95 **287 ms**, CPU
**16.28 seconds**, peak process RSS
**53004 KiB**, **15774 connections**
and **48971 application SQL statements**.
This establishes the mocked queue case, not sustained full browser/Odoo capacity.
Separate 3×30-sample mocked payload runs measured worker p95: text 20 ms,
100-KiB media 146 ms, receipts 36 ms. Media includes two injected 50-ms provider
calls. Real provider/network time, provider delivery and browser media/status
end-to-end latency remain unmeasured.

## Verification and evidence

- **23 focused Odoo tests passed**, including direct authorization, employee/
  company scope, independent website targets, aliases, unread removal, >50-message
  bursts, long website history, exact directory/read invalidations, and preserved
  incoming ordering/delivery-job counts.
- **33 focused Hoot tests passed**: timing 6, composer 14, notifications 6,
  navigation 7. English/Arabic workspace heading/login/direction checks passed.
  These are not a visual audit of every Arabic conversation state.
- **341 gateway tests passed, 28 skipped**; PostgreSQL-specific and other
  environment-dependent checks remain skipped. Existing Starlette deprecation
  warning remains. Both Arabic catalogs in both addons passed gettext format
  checks; no source UI strings changed. Python/JS syntax and diff checks passed.
- An earlier broad comparison had the same **17 failing method names** on the
  saved baseline and modified source (3 failures, 14 errors). It is not a green
  full suite. Intermediate runs also exposed fixture PIN, missing filestore,
  overlapping test asset-GC and measurement setup issues. Final focused runs are
  recorded separately; no production process was restarted for validation.

[Consolidated results](../qa/chatter_performance/results/timing-2026-11-26/timing-summary.json)
and sanitized samples are in the same directory. Reproduction commands and
fixture caveats are in [QA instructions](../qa/chatter_performance/README.md).
All 213 durable synthetic inbound events finished; the initial ORM seed accounts
for the 214th incoming message. There were 90 queued outgoing operations for 90
distinct messages, with provider sending disabled.

Private configs, API keys, session tokens and complete server logs remain under
`/tmp/chatter-timing-20261126`, outside the repository. Full-capacity staging,
combined ten-agent/large-fixture certification and the 30-minute soak remain separate.

## Runtime prerequisites and rollback

The inspected runtime configuration uses this `callcenter19` checkout. Changes are in the worktree; the user's Odoo and gateway processes were not
restarted or upgraded.
Use the verified runtime packages under `/tmp/chatter-timing-20261126/packages`
with matching addon versions. They exclude tests/caches and development-only
unit-test assets, retain gateway runtime migrations, and have verified SHA-256
manifests. The operator must perform the targeted addon upgrade, Odoo restart,
gateway worker restart and browser asset reload together. Do not use `-u base`.
No real customer messages were sent; provider sending was disabled in local tests.

For interval rollback with the new gateway source, set `worker_idle_seconds=1.0`
and `website_idle_seconds=2.0`. For source rollback, restore the previous paired
addon/gateway packages and reload their assets through the normal operator
workflow; remove the two new config keys when restoring gateway source that
rejects unknown settings. No persistent schema/index/data migration was introduced.
Reserved ports 4091/4092 and user-managed services were left untouched. Temporary
validation services are stopped and their ports verified released before delivery.
