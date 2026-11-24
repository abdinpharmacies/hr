# Native Website chat validation — 2026-11-17

> Historical record: versions, deployment state and validation results below describe the dated work only. Temporary QA scripts/evidence may have been removed. For the current order-status button and login-return behavior, use [the current guide](website-order-status-links.md). This record does not establish a current production rollout.

Implemented versions: `ab_crm_website` 19.0.1.5.0, `ab_storefront_callcenter_adapter` 19.0.1.1.1, matching Website gateway transport.

| Scope | Verified result | Evidence |
| --- | --- | --- |
| Existing Callcenter order adapter, immutable snapshots and access | 14 passed | `/tmp/website-chat-validation.log` |
| Conversation routing, approvals, source/contact isolation and browser replies | 16 passed: 14 business/access checks and 2 browser checks | `/tmp/website-chat-verified.log` |
| Ecommerce adapter including pending/direct/native portal posts, initial acknowledgement, duplicate native replies, first floating input, guest continuity/login rejection and offline operator availability | 20 passed | `/tmp/storefront-chat-verified.log` |
| Gateway Website, generic transport, SQLite, PostgreSQL account scoping, dual-channel and authentication regressions | 98 passed, no skips | Final combined pytest run with `MESSAGING_TEST_DSN_FILE=/tmp/website-chat-queue-dsn` |
| English desktop and Arabic mobile selector/composer | Actual reply queued to explicitly selected order; selector translation checked | `/tmp/website-chat-language-verified.log` |
| Final Arabic composer placeholder and selector | Separate final browser run after catalog completion | `/tmp/website-chat-translations-final.log` |
| Python/XML syntax, manifest load and both Arabic catalogs | Targeted upgrades and static validation; no missing exported terms; gettext format checks pass | Final POTs `/tmp/website-chat-final.pot`, `/tmp/storefront-chat-final.pot` |

Odoo tests ran with `/opt/odoo19/venv19/bin/python`, zero workers/cron threads, isolated data directories and databases `website_chat_validation_20261117` and `storefront_chat_validation_20261117`. HTTP/gevent pairs were 5069/5072 and 5075/5076. HTTP browser tests explicitly restricted `--db-filter` to their isolated database. Gateway PostgreSQL tests used only `website_chat_queue_test_20261117`. Test-only pytest/APSW/WebSocket packages were installed under `/tmp`; runtime dependency files were unchanged.

Browser validation found the inherited Telegram/WhatsApp fieldset provider restriction. The final Website composer has its own module-scoped wrapper, leaving the other composers intact. The tests also found and corrected a missing source component in no-phone grouping after contact linking, and capture of an internally posted comment. A new invoice revision is covered explicitly: it does not override the latest customer-message reply destination.

Earlier browser attempts were skipped for a missing WebSocket test package, then failed due to the inherited runtime database filter and the provider restriction. These are not reported as passes. Final evidence above supersedes them. The first misfiltered browser attempt made HTTP requests against the runtime database; no production acceptance messages/orders were submitted. Some restored test filestore references and unrelated addon deprecation warnings remain in the test logs; they do not establish a successful live rollout.

Runtime ZIPs and SHA256 files are under `/tmp/website-chat-release`. Packages exclude addon tests, fixtures, caches, demos and development migrations. Gateway queue schema migrations are retained because they are runtime requirements. Packaging verification compares each archived file byte-for-byte with its source and checks declared addon data files.

Outstanding: owner-controlled local Python process reloads, complete live local-pilot round-trip acceptance, production deployment access, approved production channel/pricelist inspection and correction, and explicitly approved production acceptance content/orders. Production SSH returned `Network is unreachable`. Chat/sending switches were not activated, and no existing orders, inventory, prices or payments were rewritten. See [rollout and rollback](website-chat-rollout.md).

The subsequent [live local acceptance](website-chat-local-acceptance.md) records real browser/worker/order round trips, the two source fixes and their 21-test regression run. Production remains explicitly deferred by the user.

After the owner reload on 2026-11-18, both remaining native checks passed live. A storefront default-data reset was repaired locally and fixed by preserving configured operators in `ab_ecommerce_storefront` 19.0.1.0.1. The targeted storefront/adapter upgrade and **22 tests** passed on the isolated database (`/tmp/local-chat-upgrade-preservation.log`). Current local fetch backlogs are zero; all six acceptance events are acknowledged.
