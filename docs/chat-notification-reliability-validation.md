# Chat and order-notification reliability validation

> Historical record: versions, deployment state and validation results below describe the dated work only. Temporary QA scripts/evidence may have been removed. For the current order-status button and login-return behavior, use [the current guide](website-order-status-links.md). This record does not establish a current production rollout.

Date: 2026-11-23. Approved scope: chat, notifications and diagnostics. No production
upgrades/restarts, historical order recovery or earlier-comment replay occurred.
Checkout stock validation and the configured historical cutoff are unchanged.

## Implementation commits

| Checkout | Commit | Change |
| --- | --- | --- |
| e_commerce | `ef86d19a` | Adapter 19.0.1.5.3: authenticate delivery independently of bridge health; protect author actions and accepted media receipts |
| callcenter19 | `afad4e25` | Receiver 19.0.1.15.1: retry competing preference creation after savepoint rollback |
| callcenter19 | `bb3eec1d` | Gateway: account-filtered status and sanitized Website diagnostics |

Unrelated pre-existing Callcenter workspace edits and untracked QA work were
preserved. Validation uses those existing dependency files; their hashes are in
the runtime package manifest. The dependency addons are not part of this release.

## Isolated environment

- Evidence root: `/tmp/chat-reliability`.
- Source database: `two_server_qa_reliability_20261123_store`.
- Deterministic race database: `two_server_qa_reliability_20261123_call`.
- Receiver regression/browser database: `two_server_qa_reliability_20261123_regression`.
- PostgreSQL queue test database: `two_server_qa_reliability_20261123_call_gateway_test`.
- Task-owned HTTP ports: 5189, 5169 and 5269; separate local TLS proxy ports 5643/5623.
- Odoo interpreter/server: `/opt/odoo19/venv19/bin/python`, `/opt/odoo19/server/odoo-bin`.
- Gateway interpreter: `/home/abdin_04/.config/crm-messaging/venv/bin/python`, with existing QA dependencies in `/tmp/chat-lifecycle-validation/gateway-deps`.
- Browser: local Google Chrome through existing Playwright QA tooling.

Each Odoo validation used workers=0, max-cron-threads=0 and explicit unused ports.
Synthetic databases/filestores/configurations and queue files are outside release
packages. No existing user process was stopped to obtain a port.

## Final targeted results

| Check | Result | Evidence |
| --- | --- | --- |
| Fresh source and receiver installation | Passed | `validation/store-install.log`, `validation/call-install.log` |
| Gateway full PostgreSQL + SQLite suite | 351 passed, no skips; one existing dependency deprecation warning | `gateway-final-tests.log` |
| Adapter capture, checkout identity and endpoint access | 42 passed, 1 skipped | `source-tests.log` |
| Accepted media replay after bridge fault | 1 passed | `media-replay-final.log` |
| Receiver business/isolation + English desktop/Arabic mobile two-tab browsers | 62 passed | `receiver-final-tests.log` |
| Shared-login employee order/support read preferences | 1 passed | `shared-login-tests.log` |
| Deterministic preference creation races | 6 passed; exactly 2 attempts and 1 preference in every case | `preference-races.json`, `preference-races.log` |
| Read-only deployment preflight | Source and receiver passed; intentionally wrong database rejected | `source-preflight.log`, `receiver-preflight.log` |
| Python/XML parsing | 83 Python files and 7 XML files passed at validation time | AST/lxml checks |
| Arabic catalogs | Both ar/ar_001 catalogs passed msgfmt --check-format for both addons | Four generated MO files outside release |
| Whitespace/diff validation | Passed in both checkouts | git diff --check |

The optional source Customer API payment test skipped because that optional addon
was not installed. It is outside the chat/notification change. No new or changed
source UI strings were introduced; existing translated errors were reused. POT
export was therefore unnecessary. English and Arabic runtime browser tests passed.

The race script establishes the loser's PostgreSQL snapshot before the winner
commits and then exercises inbox/detail, detail/read and notifications/read for
both order and support targets. Duplicate-key diagnostics in that deliberate race
log are expected: the savepoint recovers them and ConcurrencyError causes the
whole request to retry. Other unique/not-null errors remain unconverted.

Initial receiver setup exposed English/Arabic assertion failures while English
was inactive and synthetic system users defaulted to Arabic. Normalizing only the
synthetic language defaults resolved them. An initial browser run used the old
race database filter; correcting the isolated config resolved its login rejection.
A new media test's mock response type and an alert test's overbroad conversation
assertion were corrected before their final successful runs. These corrections
did not change stock, pricing or unrelated business logic.

## Browser, attachment and outage results

The initial zero-duration smoke delivered its message round trips correctly but
asserted queue emptiness before one asynchronous receipt report finished. Its
result is retained as a failed diagnostic run, not counted as a pass. The bounded
recovery run below allows delivery/report processing and explicitly checks final
queue state, destination uniqueness and business preservation.

- Guest orders and support: passed source outage, closure races, exact replay and capability isolation (`validation/guest-results.json`).
- Attachment matrix: image, document, audio/voice and video round trips passed byte-hash, replay, private-download and size-limit checks, including both large-media boundary cases (`media-results.json`, `large-media-0-results.json`, `large-media-1-results.json` under `validation/`).
- Chromium guest workflow passed (`validation/cross-browser-results.json`).
- Logged-in identity handoff, logout revocation, account switching and private-history resumption passed (`validation/identity-browser-results.json`).
- Controlled source, receiver and gateway interruptions passed in the 180.237-second recovery run: eight delivery cycles, healthy latency 4.553–7.669 seconds, recovery latency at most 41.744 seconds, within the 30/90-second limits (`validation/workflow-results.json`).
- Signed-in dispatch notices, retained history, single portal notices and other-order drafts passed in four Chromium desktop/mobile English/Arabic profiles (`validation/dispatch-browser.log`).
- Exactly one receiver message was found per incoming event at its intended destination. Final incoming/outgoing queue residue was empty. Runtime source hashes and the stock/reservation, pricing and native-order snapshot remained unchanged.

## Release artifacts and limits

Runtime archives and per-file SHA-256 manifest are in `/tmp/chat-reliability/release`.
They contain only receiver 19.0.1.15.1, adapter 19.0.1.5.3 and gateway runtime.
The archives were checked against committed source and exclude tests, credentials,
QA evidence, hidden configuration and caches. The gateway's existing schema
migrations remain part of its runtime package. No addon migrations/hooks were added.

See `docs/chat-notification-reliability-release.md` for exact manual targeted
upgrade/rollback commands and the read-only preflight. Production activation,
customer-facing acceptance and verification of deployed dependency hashes remain
manual. Firefox/WebKit and a longer production-like soak were not repeated for
this patch; this run used Chromium, with English desktop and Arabic mobile
Callcenter coverage. The validation does not recover or certify historical orders.

The final combined runner reported `passed: true`; every task-owned process was
stopped and all task HTTP/gevent/TLS ports were released (`validation/run-result.json`).
Synthetic databases and private evidence remain available for inspection.
