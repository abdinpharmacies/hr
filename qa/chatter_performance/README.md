# Chatter performance validation

Local functional validation uses an isolated database and mocked provider calls.
The `test_performance_*` Odoo methods cover bounded notifications, removal after
reads/acknowledgments, old conversations, literal search, request cache lifetime,
private invalidations and serialization of only the selected inbox page.
`TestBranchBrowser.test_performance_notification_components` runs the browser
notification suite. Set `CHATTER_PERFORMANCE_OUTPUT` to a private JSON output
path to capture actual API samples from `test_performance_api_measurements`.
The measurement test rolls its synthetic records back.

Use the current project addon path and an isolated test database. All commands
must specify `--workers=0 --max-cron-threads=0 --http-port=5069 --gevent-port=5072`
(or another verified unused pair). Do not run these fixtures against callcenter
or POS. Do not install retired OMS modules or enable real provider delivery.

The small local measurement fixture is 60 conversations, 600 messages and 60
contacts, one sequential caller, 30 samples per endpoint after warm-up. First
notification pages differ in units: legacy pages contain 50 conversations;
v2 pages contain 100 messages. Compare complete snapshots for equivalent work.
This fixture cannot certify the approved 100k/100k/1m capacity baseline.

Staging acceptance still requires resource-limited Odoo with production-like
workers and websocket routing, mocked providers and ORM-created 100,000 contacts,
100,000 conversations and 1,000,000 messages. Include long threads, already read
history, multiple companies/branches, source aliases, independent order/Support
chats, up to 10 staff and ramps of 25/50/100 website sessions. Record actual API
and browser p50/p95/p99, commit-to-visible timing, separate provider/network
time, errors, resource use and queue age/growth. Run 5 messages/s combined with
20/s ten-second bursts and separate receipt traffic for a final 30-minute soak.
Correlate opaque test IDs only. Do not log bodies, credentials or employee PINs.

No production certificate is issued until all approved gates pass. Preserve
accepted/delivered/read distinctions. An accepted provider send is not evidence
of customer delivery.

## Recorded local evidence

`results/before.json` and `results/after.json` contain sanitized sequential API
samples. Rebuild their nearest-rank summary with:

```bash
python3 qa/chatter_performance/summarize.py \
  --before qa/chatter_performance/results/before.json \
  --after qa/chatter_performance/results/after.json \
  --output qa/chatter_performance/results/summary.json
```

Build verified runtime-only archives without deploying them:

```bash
python3 qa/chatter_performance/package_runtime.py --output /tmp/chatter-runtime-packages
```

The full staging test and soak were explicitly deferred by the user. Existing
broader test failures are compared by name in `results/protection-comparison.json`;
matching failures do not constitute a green full-suite or production certificate.

## Approved message-timing iteration — 2026-11-26

The message-timing plan replaces the earlier capacity plan for this iteration.
Use the [timing report](../../docs/sales-chatter-timing-2026-11-26.md) for current
results and limits. Full-capacity staging and the 30-minute soak remain separate.

`run_timing.py` runs three API repetitions on 60/600 and 1,000/10,000 fixtures,
plus a 1,001-message active-history comparison. Save the pre-change addons first
and include identical measurement tests in that saved source. The small fixture
uses gateway-created messages. The large fixture uses one gateway-created message
per conversation and nine batched ORM messages; it does not represent a complete
10,000-event provider ledger. Planner statistics are collected after seeding.
Each test rolls back. Use a separate disposable database per concurrently running
Odoo test process; shared test transactions and generated-asset GC can race.

```bash
/opt/odoo19/venv19/bin/python qa/chatter_performance/run_timing.py \
  --config /private/timing.conf --database callcenter_timing_TEST \
  --output /tmp/timing-results --phase before --baseline-addons /tmp/saved-addons
/opt/odoo19/venv19/bin/python qa/chatter_performance/run_timing.py \
  --config /private/timing.conf --database callcenter_timing_TEST \
  --output /tmp/timing-results --phase after
```

Use the gateway's environment with its pinned runtime/test dependencies for queue
and mocked payload measurements. Run idle variants sequentially at 0.1, 0.25,
0.5, 1 and 2 seconds, three repetitions each, with identical durations.

```bash
python qa/chatter_performance/queue_timing.py --interval 0.25 --seconds 300 --output /tmp/queue.json
python qa/chatter_performance/payload_timing.py --provider-delay-ms 50 --output /tmp/payloads.json
```

Actual browser timing requires a separate disposable Odoo database, its filestore,
loopback test HTTP, Chrome, Playwright and one synthetic gateway worker. Prepare
normal service/staff users and short-lived credentials in a private fixture:

```bash
/opt/odoo19/venv19/bin/python qa/chatter_performance/runtime_fixture.py \
  --config /private/e2e.conf --database callcenter_timing_E2E --output /private/fixture.json
python qa/chatter_performance/gateway_fixture.py --fixture /private/fixture.json \
  --output /private/gateway.json --queue /private/queue/queue.db
```

Start the test Odoo server with `--http-interface=127.0.0.1 --http-port=5085
--gevent-port=5086 --workers=0 --max-cron-threads=0`, its exact disposable database,
and `CRM_MESSAGING_TRACE=1`. From `crm_messaging_gateway`, use the private gateway
config and trace environment to run `python -m uvicorn app.main:create_app
--factory --host 127.0.0.1 --port 5087` and one `python -m app.worker` process.
Provider sending remains disabled. Verify all ports are free before starting;
track and stop only these temporary processes afterward.

```bash
node qa/chatter_performance/browser_timing.cjs --fixture /private/fixture.json \
  --output /tmp/browser.json --chrome /path/to/chrome --agents 1 --incoming 30 --replies 30
```

Use `--agents 10 --replies 0` for shared-conversation inbound contention and
`--disableWebsocket --incoming 3 --replies 0` to block the websocket handshake.
The latter rejects any correlated push notification. Browser tracing is opt-in
through `sessionStorage.ab_chatter_timing=1`; samples contain opaque IDs and timing
metadata. The script saves partial measurements on each completed sample. A
partial file is not a passing workload. Keep private fixture/config files out of
source control and reports.

Rebuild the consolidated JSON from the recorded file names and sanitized logs:

```bash
python qa/chatter_performance/summarize_timing.py \
  --directory /tmp/chatter-timing-20261126 --output /tmp/timing-summary.json
```

The raw result directory includes intermediate variants and failed stress runs.
Use the final inbox samples for page-preview results. Initial full-traversal
baseline samples did not collect response-byte totals; their value of four bytes
represents JSON `null`, not a real snapshot response size. Browser timings use
local wall clocks on the same host. These fixtures do not certify PostgreSQL queue
capacity, remote providers, ten agents on the large fixture or a production rollout.
