# Development validation — 2026-11-08

Implementation is validated for development. Production cutover, provider traffic, webhook activation and capacity approval have not occurred. The current Odoo and messaging services were left running with their existing configuration.

## Automated evidence

| Check | Result |
| --- | --- |
| Gateway suite, PostgreSQL compatibility and SQLite | 110 passed, no skips |
| Core messaging / Telegram / WhatsApp adapter regressions | 23 passed |
| Workspace and optional WhatsApp bridge regressions | 73 passed |
| Final bridge-only upgrade after reception guard change | 15 passed |
| Browser suite included in the Odoo runs | 14 passed, 36 assertions |
| Python syntax and XML parsing | Passed |
| Arabic catalogs for the three affected addons | Six catalogs compile |
| Protected addon hashes | All 202 files unchanged |

The final bridge-only run repeats bridge tests already included in the 73-test run; these counts must not be added as distinct cases. Odoo's statistics also count fixture work separately; the counts above use `odoo.tests.result`.

Gateway tests cover competing processes, duplicate ingestion/claims, ordering, atomic polling offsets, receiver process death and lock release, stale leases, unavailable Odoo/providers, real SQLite disk-full rollback, bounded writer contention, preserved receipts, PostgreSQL export/import digests, corrupt import rollback, consistent backup recovery and uncertain sends that cannot automatically dispatch again. The runtime guard checks WAL, FULL synchronization, foreign keys and rejection of SQLite older than 3.51.3. Tests use APSW 3.51.3.0 in a separate temporary gateway environment. One existing Starlette/httpx TestClient deprecation warning remains.

Odoo tests exercise both send entry points, one operation per message, historical linking without resend, replay deduplication, immutable history, cross-company and branch access, private media access even through a sudo controller, revoked permissions/employee eligibility, template eligibility, closed reply windows, uncertain outcomes and no direct fallback for disabled/archived migrated accounts. Browser checks cover independent channel drafts/attachments/replies, composition, RTL and existing Chatter behavior.

The browser fixture excludes five existing unrelated POS patches from the test setup asset bundle because of their registry-loading dependency. These exclusions are transaction-local test records. Protected source files and production asset declarations are unchanged.

## Isolated runtime

Fresh installation and targeted upgrades used `/opt/odoo19/server/addons` and this checkout, database `crm_whatsapp_sqlite_test_20261108`, with `--http-port=5069 --gevent-port=5072 --workers=0 --max-cron-threads=0 --stop-after-init`. The optional bridge and its 47-module dependency graph installed successfully. Core adapter tests used the separate fresh database `crm_core_messaging_test_20261108`; queue compatibility tests used `crm_queue_pg_test_20261108`. No live database upgrade ran.

Core tests run separately because their existing minimal company fixture does not supply fields required by the installed sales-workspace dependency graph. A combined run initially exposed that fixture mismatch; the independent core suite and the complete workspace/bridge suite subsequently passed.

Evidence remains locally under `/tmp/crm-sqlite-validation/`: `core.log`, `verified-regressions.log`, `final-bridge.log`, `language-check.log`, `benchmark-receiver.json` and `initial.diff`. Temporary paths and validation databases are development evidence, not deployment configuration.

Example final gateway invocation from the checkout:

```bash
PYTHONPATH=/tmp/crm-sqlite-validation/runtime:crm_messaging_gateway \
PATH=/tmp/chatter-ffmpeg/usr/bin:$PATH \
MESSAGING_TEST_DSN_FILE=/tmp/crm-sqlite-validation/pg.dsn \
/tmp/crm_gateway_venv/bin/python -m pytest crm_messaging_gateway/tests -q
```

Both Arabic catalogs retain English `msgid` values. Runtime checks validate account field/view translations and frontend template/queue strings in `en_US`, `ar` and `ar_001`; Arabic frontend locale direction is RTL. The legacy `ar` language was created only in the isolated database for this check. Existing workspace catalog headers produce metadata warnings, with no compilation errors.

The saved starting diff was reconstructed and compared with the working tree. Pre-existing tracked changes remain intact; this task adds only the documented extension hooks and version bump to the previously modified workspace Python/manifest. Runtime packaging excludes Python/browser tests and removes test asset declarations only inside the generated archive. Source tests remain in the checkout.

## Capacity is not approved

No representative production peak is available. A synthetic assumption of 50 cycles/second was used solely to exercise the harness at a target of 100 cycles/second. With four processes, FULL synchronization and an open receiver-like connection, 1,000 complete incoming/outgoing cycles took 22.486 seconds: **44.472 cycles/second**, p95 cycle latency **0.392 seconds**. All cycles completed, but the target was missed. This is not a production sizing claim and does not meet the deployment gate.

Before production approval, measure representative traffic, repeat at twice that measured peak on the intended encrypted local storage, verify backlog drains and acceptable latency, and complete provider integration checks. Confirm encrypted volume coverage for database/WAL/exports/backups, install the reviewed backup timer, and rehearse the quiesced export/import and restore/reconciliation procedures in `SQLITE.md`. Do not resume a stale PostgreSQL queue after SQLite traffic.
