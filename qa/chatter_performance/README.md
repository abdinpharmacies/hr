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
