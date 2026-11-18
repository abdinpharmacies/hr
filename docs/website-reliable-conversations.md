# Reliable website conversations

Implementation: `ab_crm_website` 19.0.1.6.0, `ab_storefront_callcenter_adapter` 19.0.1.2.0 and the matching gateway. Existing work in both checkouts is preserved. No runtime process was restarted and no live switch was enabled by this implementation.

## Delivery and identity

Customer sends use a UUID for one send intention. Pending UUIDs, bodies, drafts, retry counters and deadlines survive refresh and navigation in tab-scoped session storage keyed by the original destination, including verified sign-in handoff; independent tabs create independent sends. An acknowledgement removes only its matching submission and does not clear a newer draft. Closing a browser tab ends that tab's draft storage. Server history persists independently.

The order page and native floating chat use request timeouts, cursor catch-up, visibility, online and pageshow recovery. The native history panel includes earlier transport sessions for the same verified identity. A native send is deduplicated under the destination row lock; website replies are deduplicated under the endpoint row lock. Repeated identical text with different UUIDs creates separate messages. A replay of a committed send can still be acknowledged after the conversation ends; a new send cannot.

Website gateway sends retry transient or uncertain outcomes and expired leases with the same token, body and destination. Eight automatic attempts use delays of 5, 10, 20, 40, 80, 160 and 300 seconds. Exhaustion produces review evidence. Authentication, validation and ended-session failures do not automatically retry. Managers can explicitly select **Retry website send with same token** in Messaging Delivery for uncertain website operations. The approval token and destination stay unchanged; the attempt number increases and the actor/time are appended to history. Older gateway review evidence is retained as superseded. Every dispatch is re-authorized.

Version 1 order notifications, version 2 chat envelopes and version 3 lifecycle events are separate. Version 3 adds idempotent `identity_bound` and `session_ended` events. The gateway asks the receiver for capabilities and re-probes unsupported features every 60 seconds. Order and chat fetching proceed independently; malformed or conflicting individual events are quarantined without discarding other customers' events. A reviewed event blocks its own stream; another customer's stream continues.

A source-scoped account UUID comes from the authenticated user, or verified checkout ownership, never a phone or commercial partner match. New verified orders and floating chat share a Sales Chatter conversation. Late recognition routes future order messages to the verified timeline without moving historical phone-only orders, snapshots or queued operations. A verified guest handoff retains original message envelopes and links the guest stream to the account timeline. Both authenticated login and active guest ownership are required. Native channel and message reads/searches also enforce the verified account boundary for portal/public users.

Refresh, minimization and disconnection keep a guest's active session. Explicit End chat creates a new guest identity on the next conversation, even with the same native guest cookie. Replies remain addressed to their approved native destination; ended-session replies never follow a visitor into a replacement session. A signed-in return resumes the same account conversation, with earlier native sessions available in Previous conversations.

Saved replies reuse the configured library, employee language, placeholder dialog and existing manager/branch/company restrictions. Insertion produces an editable draft and requires Send. The website integration rejects overlong expansion and ignores insertion callbacks after navigation. Website order and floating-chat origins and reply destinations are shown separately.

Queued, accepted by the website, and read by a customer are different evidence. This transport reports website acceptance only. It does not claim customer-read evidence from a successful POST or from an agent reading Sales Chatter.

## Owner-controlled activation

1. Retain a consistent source/package and database backup under the owner's normal deployment procedure. Record the current intake, outgoing and lifecycle switch values. Historical reconciliation is a separate operation.
2. Upgrade the callcenter receiver to 19.0.1.6.0 first. Use its actual worktree in the addons path. Reload it through the owner's normal process management.
3. Upgrade/reload the gateway next. Its existing queue schema is sufficient; no queue migration or provider credential changes are required. The new sender preserves Telegram/WhatsApp retry policy. The old gateway must not run alongside the new website worker for the same accounts.
4. Upgrade the storefront adapter to 19.0.1.2.0. Keep **Enable verified conversation lifecycle** disabled until the receiver capability check succeeds. Reload through the owner's normal process management and refresh frontend assets.
5. Enable the lifecycle switch for the intended website endpoint. Retain the existing owner-controlled intake and outgoing switches. Verify one signed-in floating/order timeline, one guest end/return, and one approved agent reply using owner-approved acceptance content. Checkout remains independent of chat acceptance.
6. Observe `python -m app.ops status` and `python -m app.ops review` using the owner's gateway environment. Status includes website pending age, retry count, blocked-stream count and failure category; it does not print message bodies or credentials. Confirm pending age falls after recovery and that review cases are investigated.

## Rollback

Disable website outgoing sending before pausing its worker. Disable the storefront lifecycle producer switch, then drain/review already-produced v3 events with the compatible receiver before downgrading any receiver. Keeping the compatible receiver installed while disabling the feature is the preferred rollback. Do not remove new fields/models, erase evidence, merge phone-only history, or redirect queued operations to a different destination. Do not restart the owner's processes automatically. If restoring older code is required, use the matching database/package backup and a coordinated owner maintenance window; schema downgrades are not provided.

## Validation

See [the case matrix](website-reliable-conversations-matrix.md). Tests use only `website_chat_validation_20261117`, `storefront_chat_validation_20261117` and `messaging_reliable_test_20261118`. HTTP/gevent pairs are 5075/5076 for callcenter and 5069/5072 for storefront, with zero workers and cron threads. Browser database filters are exact. External providers are mocked in the gateway suite. Runtime ZIPs exclude addon tests, fixtures, demo files, development migrations and caches.

Physical device sleep/wake, a real multi-device network partition, long-running concurrent-tab stress and production acceptance remain operational checks. Browser lifecycle events and server/queue recovery are exercised in automated tests. No production rollout or historical reconciliation is included.


### Verified results — 2026-11-18

| Scope | Passed | Failed | Skipped | Final evidence |
| --- | ---: | ---: | ---: | --- |
| Gateway, PostgreSQL, SQLite and provider regressions | 303 | 0 | 0 | `/tmp/reliable-gateway-final.log` |
| Callcenter business, security, bearer HTTP, English desktop and Arabic mobile | 36 | 0 | 0 | `/tmp/reliable-callcenter-release-verified.log` |
| Storefront business/security, native HTTP, lifecycle browser and Arabic labels | 32 | 0 | 0 | `/tmp/reliable-source-release.log` |
| Final destination-key preservation through sign-in handoff and browser checks | 3 overlapping cases | 0 | 0 | `/tmp/reliable-source-handoff-draft-final.log` |

There are **371 distinct passing cases** across the three suites; overlapping focused reruns are not added to that total. Both addon manifests/data files, Python/XML/JS syntax, `git diff --check`, all four Arabic catalogs with `msgfmt --check-format`, and final POT coverage passed. Receiver/source Arabic browser checks verify actual translated text. Packages were compared byte-for-byte with the source and checked to exclude development-only files. ZIPs, SHA256 files and `manifest.json` are in `/tmp/reliable-website-release`.

The native lost-acknowledgement baseline failed before its fix. Intermediate runs also caught missing translation metadata, an Odoo 19 member API mismatch, the nullable order/session domain, and test setup/timing issues; only the final successful runs are counted above. Restored validation filestores contain missing historical image blobs and unrelated addon warnings. These are fixture limitations, not evidence of live deployment. The operational cases listed as Pending in the matrix were not executed and are separate from the automated skipped count.

Reproduce with `/opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin server`, the corresponding config, the isolated database and exact worktree addons path, a targeted `-u` for the owning addon, `--workers=0 --max-cron-threads=0 --stop-after-init`, and the alternate port pair above. Browser checks require HTTP and an exact `--db-filter`; they must not use `--no-http`. Gateway tests use the owner's existing gateway virtualenv, `PYTHONPATH=/tmp/website-test-deps:crm_messaging_gateway`, and the private isolated DSN file `/tmp/reliable-queue-dsn`; no credentials are included here.
