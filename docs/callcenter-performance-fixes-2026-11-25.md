# Callcenter performance fixes — 2026-11-25

Immediate source changes and local validation are complete. The user explicitly
deferred the large staging fixture, concurrency ramps and 30-minute soak. This is
not a production capacity certificate. Nothing was deployed, no production flags
were enabled, and neither PyCharm-managed Odoo process was stopped or restarted.

## Implemented behavior

- `notifications_v2` selects read/acknowledgment-filtered candidates before paging,
  bounds each request to 100 messages and supports authorized conversation-targeted
  replacement, including empty results that clear alerts. Legacy notifications
  retain their contract and share notification serialization. Unread counts remain
  distinct from alert acknowledgment counts and merge correctly across pages.
- Authorization, sessions, branches, canonical website streams and target lookups
  are cached only inside the current request and keyed by actor/company/context.
  Reconnect recovery starts a fresh authoritative snapshot; message cursors are
  traversal positions, never permanent new-message watermarks.
- Inbox activity uses ORM aggregates before page selection. Only selected page
  rows and previews are serialized. Order and Support targets, source UUIDs,
  aliases, activity ordering and customer grouping remain distinct.
- Contact filtering/paging runs in scoped ORM queries after an explicit bounded
  normalization backfill. Stored case-folded name/phone keys have Odoo-managed
  indexes. Literal `%`/`_`, Arabic/English, national/normalized phone, active
  alternate-number and legacy fallback behavior have regression coverage. Inactive
  numbers remain excluded according to existing semantics. Keys reject forged
  writes and have the same reader groups as protected contact phones. Native ORM
  recomputation preserves customer write timestamps.
- Native Odoo bus invalidations use authorized users' private partner channels and
  contain only the company ID. Native commit hooks deliver them after commit.
  The browser coalesces invalidations and overlapping refreshes, resets replaced
  employee/company state, reloads on reconnect and retains five-second recovery
  polling. Commit-to-visible latency has not been capacity-certified.
- Gateway scheduling rotates operations, website accounts and protocol versions
  within 25 operations or 250 ms between operations. Durable deferrals count as
  scheduling progress so one deferred item does not impose an idle wait on the
  next eligible item. Failed receipt/report attempts rotate through their existing
  bounded windows. Leases, ordering, retries and uncertain-send review remain.
- Website account selection and separate mutually exclusive pilot/production unit
  templates are prepared. Existing protocol/storage remain. The independent
  service restructure is only a [future draft](channel-services-future-draft.md).

## Local application measurements

Identical ORM/API-created fixture: 60 customers, 60 conversations and 600 messages;
one sequential caller, one warm-up and 30 samples per stage, with ORM caches
invalidated between samples. Before uses unchanged committed addon source in a
`/tmp` overlay; after uses the changed application methods. Database:
`callcenter_perf_20261125`, exclusively synthetic, isolated from callcenter/POS.

Times are application-method wall time in milliseconds, including authorization,
ORM work and Python response construction. They exclude HTTP/network/proxy overhead.
These are actual application API methods, not SQL-only benchmarks. Browser checks
below are separate. A 30-sample p99 is only the largest sample, not a robust tail
estimate.

| API/stage | Before p50 | Before p95 | Before p99 | After p50 | After p95 | After p99 |
|---|---:|---:|---:|---:|---:|---:|
| Notification first page | 373.5 | 432.5 | 466.1 | 62.4 | 69.1 | 69.9 |
| Complete unread snapshot | 436.7 | 596.1 | 714.2 | 475.2 | 525.4 | 564.5 |
| Inbox page (30 rows) | 458.7 | 564.7 | 588.5 | 311.5 | 359.3 | 385.8 |
| Contact search (30 rows) | 71.4 | 78.5 | 81.6 | 68.9 | 82.2 | 100.6 |

Legacy notification first pages contain 50 conversations; v2 pages contain at most
100 messages. Their first-page work is different. The complete-snapshot row compares
the same full 600-message unread fixture. Search has little data at this scale;
its indexed-query overhead and local timing variation are visible, and this run
must not be used to infer 100,000-customer performance.

All 120 timing samples per phase completed without an API error or timeout. Peak
process RSS was 157.0 MiB before and 154.0 MiB after;
this includes the Odoo process/fixtures, not endpoint-only memory. CPU saturation,
queue age/growth, sustained throughput, provider/network latency and browser
commit-to-visible latency were not measured. They remain unset in sanitized JSON,
not reported as zero. No sender-to-receiver capacity is claimed.

Sanitized evidence: [summary](../qa/chatter_performance/results/summary.json),
[before samples](../qa/chatter_performance/results/before.json),
[after samples](../qa/chatter_performance/results/after.json).
Opaque sample correlation IDs contain no bodies, credentials or PINs and are not
claimed to be distributed traces across providers.

## Verification and existing failures

- Fresh isolated install and targeted upgrades of Sales Chatter/Website Chatter
  completed. Final focused regression selection: **16 passed**, covering unread
  totals/removal, paging, old conversations, forged/revoked access, request cache
  lifetime, bus privacy/coalescing, page-only serialization, normalized-key privacy,
  timestamps, literal and alternate/inactive/legacy phone search, independent
  website targets and canonical aliases. The measurement test passed separately.
- Final browser selection: **2 HttpCase methods passed**. This includes **5 HOOT
  notification tests / 26 assertions** and actual English/Arabic workspace/login
  labels, translated normalization-field labels and RTL direction.
- Gateway suite: **329 passed, 28 skipped**. PostgreSQL-specific fixtures and other
  explicitly skipped paths are not claimed as tested. Existing deduplication,
  receipts, authorization, crashes, throttling, ambiguous-send and SQLite tests ran;
  new tests cover fair scheduling, quanta, idle cycles, account selection, evidence
  rotation and deferral progress.
- Broader POS handoff/credentials/WhatsApp selection: **62 methods**, with the exact
  same **6 failures and 9 errors** on both untouched and changed source. Native
  failure names and internal browser failure names match. These include retired
  chat-link expectations, inactive legacy `ar` test setup and old browser harness
  assumptions such as missing `draftKey`. They were not made green by restoring
  retired behavior. See the [comparison](../qa/chatter_performance/results/protection-comparison.json).
- An earlier exploratory 246-method run was not green (22 failures / 43 errors),
  and is not represented as a successful full-suite run. The isolated comparison
  and passing focused selection above are the validation claims for this change.
- Python parsing, changed JavaScript syntax, both Arabic catalogs for both addons,
  manifest author/developer metadata, archive content/checksums, service-template
  verification and `git diff --check` passed. An unrelated installed AnyDesk unit
  emitted a legacy PIDFile warning during service-template verification.

No POS, pricing, stock, payment or order-submission implementation was changed.
No complete production-readiness claim follows from unchanged source or partial
regression coverage.

## Remaining gates and activation

The approved 100,000-customer / 100,000-conversation / 1,000,000-message fixture,
25/50/100 website-session ramps, up to 10 staff, message/receipt traffic and final
30-minute soak were **deferred by the user**. The small local page measurements
are below the provisional latency targets, but full-load p95/p99, healthy websocket
visibility, sustainable capacity, queue growth and duplicate/lost-delivery gates
remain unverified. No production certification is issued.

Inbox candidate aggregation/sorting still depends on authorized target count;
notification read/preference predicates still depend on current actor positions.
Serialization is bounded by the selected page, but constant-cost processing at
100,000 targets is not established. Record these costs in the deferred staging
run rather than claiming that all dataset scaling limits have disappeared.

Current gateway PostgreSQL/Odoo coupling, idle polling (one/two seconds), failure
backoff and blocking operation timeouts remain. The 250-ms quantum is checked
between operations; it cannot preempt a network call. Provider acceptance is not
customer delivery. Credential/TLS findings and service redesign are outside this
phase.

Deploy only through a separately approved rollout. Preserve existing history,
UUIDs, receipt evidence, queues and business records. Complete the private bounded
ORM search-key backfill before enabling indexed search in the intended runtime.
Until then the compatibility search path remains. No direct PostgreSQL diagnostic
or ad-hoc data-edit helper was used. No retired OMS modules were installed.

## Runtime artifacts

Packages exclude tests, static test assets, QA tooling, migrations and
bytecode; addon metadata and archive byte contents were checked. They were built
without installing/enabling any service. Full archive hashes:

| Archive | Source files | SHA-256 |
|---|---:|---|
| ab_crm_sales_workspace.zip | 123 | `656a54277e4e8908d1622b0e92444f89e5c09ad8e7c5f964f0b658ef4bebe7b0` |
| ab_crm_website.zip | 59 | `2863a040a46d71c27c03bc2262fd4a4b1e94325336146ac6700dfda33aab370c` |
| crm_messaging_gateway.zip | 70 | `e223ce6f2c57faf789ed5c18e7bd5315f2b519ce5875dff25f14e7a633c5a893` |

[Package index](/tmp/callcenter-performance-20261125/packages/artifacts.json).
Reproduction/tooling: [QA instructions](../qa/chatter_performance/README.md),
[summary script](../qa/chatter_performance/summarize.py),
[runtime packager](../qa/chatter_performance/package_runtime.py).

Unrelated staged FastRAG files, existing tools and the prior production-readiness
audit were preserved. Validation used reserved alternate test ports only; all
owned temporary test processes shut down and 5069/5072 were verified released.
