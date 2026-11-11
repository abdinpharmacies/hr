# Messaging recovery and legacy sales retirement

Implemented on 2026-11-11 in the `callcenter19` checkout and the `callcenter` database.
Other worktrees and website deployments were not changed.

## Runtime changes

- Verified the existing Telegram bot identity and absence of a webhook. Restarted
  only its existing receiver, preserving the database offset and exclusive lock.
  Three pending inbound updates reached Odoo; the heartbeat stayed healthy for
  more than five minutes, including after the final receiver reload. User-sent
  Telegram and WhatsApp messages then both reached Odoo (11:39 Cairo time).
  Temporary failures now exit 75 after bounded retries;
  invalid credentials, competing receivers, active webhooks and malformed events
  remain explicit sanitized stops.
- `app.ops status` retains its existing response fields and adds per-account
  reception health and backlog age. Missing/stale enabled polling is unhealthy
  after 120 seconds, independently of gateway liveness and queue readiness.
- Historical WhatsApp receipts require a unique outgoing historical projection,
  account, provider reference, destination, branch and company match. Ordinary
  operation-based statuses retain their existing path and boolean API response.
  Status updates do not regress delivered/read evidence, create operations, send
  messages, change unread state or reopen the reply window.
- Previewed all 17 old pending/review WhatsApp status events. Retried historical
  events 77, 78, 91, 94, 96, 98 and 100; all completed. Marked confirmed orphans
  73, 76, 79, 82, 86, 90, 92, 97, 99 and 102 ignored. All 17 have operator audits,
  mandatory reasons and preview digests; original payloads/fingerprints remain.
  Outgoing operation counts stayed at 33 Telegram and 14 WhatsApp during this
  reconciliation. New unmatched receipts retain normal retry/review behavior.

## OMS and historical orders

After the user stopped Callcenter Odoo in PyCharm, refreshed private backups
covered the database, filestore, gateway queue and configuration. Every OMS table
was rechecked empty. A targeted upgrade detached Sales Chatter from OMS, then
Odoo's supported immediate uninstall removed `ab_oms_sync`,
`ab_oms_branch_adapter`, and `ab_oms_core`, in that order. Dependency checks
prevented unintended dependent-module removal. No business tables were directly
deleted by maintenance scripts.

The three retired addons and unused `ab_oms_website_adapter` were removed from
this checkout only after uninstall. The retired gateway worker remains inactive;
the current messaging gateway is retained. No migration hooks were introduced.

Full-row hashes before upgrade and after uninstall matched for:

| Preserved records | Count |
| --- | ---: |
| Legacy orders | 10 |
| Legacy order lines | 3 |
| Legacy order audits | 21 |
| CRM contacts | 2 |
| Conversations | 5 |
| Identities | 4 |
| CRM messages | 124 |
| Native sales headers | 44 |
| POS handoffs | 10 |

Legacy orders, lines and audits reject create/write/unlink and old transition
methods, including administrator/sudo ORM calls. Historical states and snapshots
remain unchanged. Scoped archive list/form views remain available. Sales Chatter
keeps its existing action IDs, direct Inbox navigation, conversation branch
sharing and the `ab_sales` POS/invoice handoff. Obsolete order-editing dialogs
were removed. English source strings and both Arabic catalogs are retained.

## Validation and rollback evidence

Private evidence is under `/tmp/callcenter-retirement-20261111/`. Hash-verified
maintenance-window backups, original source and reconciliation evidence are also
preserved in the durable private directory
`/home/abdin_04/.config/crm-messaging/backups/callcenter-retirement-20261111/`.
These directories contain protected configuration backups and must not be
published or included in the release. The original working changes were saved
before editing. The release archive contains runtime source and this report only.

- `callcenter_retirement_test_20261111`: restored and neutralized live clone;
  upgrade and supported uninstall rehearsal preserved archive hashes and removed
  only the three intended modules.
- `callcenter_retirement_fresh_20261111`: clean installation of the full sales
  and WhatsApp companion stack without installed OMS modules.
- `callcenter_retirement_core_test`: 30 core messaging tests passed without
  optional workspace constraints.
- Gateway suite: 221 passed, one intentionally skipped destructive backup test;
  additional final receiver cases and reconciliation checks cover both PostgreSQL
  and SQLite.
- Final changed gateway checks: 23 passed, including both queue backends.
- Final archive runtime checks verify both Arabic error catalogs and unchanged
  unread counts; archive view/action translations also passed on live Odoo.
- Final workspace rerun: all 85 tests passed. The other 59 sales/WhatsApp checks
  passed in the preceding broad run after the clean-install fixtures were corrected.
- Browser component suites: 72 Sales Chatter tests, 85 combined channel tests,
  and 13 mobile channel tests passed. English and Arabic POS navigation and native
  invoice access were exercised with external branch calls mocked.
- Initial broad runs exposed populated-clone assumptions, Arabic-only test
  language setup, and obsolete legacy-order assertions. Tests were adapted for
  the read-only archive; language fixtures are explicit. Logs retain all attempts.

Validation servers use alternate ports with workers/cron disabled. The user's
Odoo process was stopped and restarted only by the user. No synthetic customer
messages were sent. Pricing, inventory and external E-Plus connectivity were
outside this change.

Rollback requires a user-managed maintenance window and restoration of the
matching Odoo database, filestore, addon source and protected configuration.
Preserve the current live messaging queue: do not restore an older queue or
replay completed sends. Queue backups are recovery evidence, not permission to
rewind delivery state. Review any post-backup transactions before database restore.

## Final live verification

The user restarted Odoo after the final Arabic catalog correction. Both user-sent
channel messages reached Odoo. The final queue had 47 completed Telegram events,
57 completed WhatsApp events and 12 ignored WhatsApp events (two pre-existing);
no pending, processing or review events remained. Outgoing operation counts were
unchanged at 33 Telegram and 14 WhatsApp. The polling heartbeat was fresh, all
three current messaging services were active, and no retired gateway service was
installed/running. All temporary validation ports were released.
