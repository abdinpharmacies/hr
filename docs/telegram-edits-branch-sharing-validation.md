# Telegram edits and branch sharing

Source and configuration prepared on 2026-11-08. Live activation is awaiting the
user-managed Odoo upgrade/restart and privileged gateway service restart.

## Findings and changes

The polling receiver requested only new messages and reactions, and normalization
ignored `edited_message`. Telegram supplies revised known messages through that
update type; both polling and webhook subscriptions accept an explicit update
list. See [Telegram Update](https://core.telegram.org/bots/api#update) and
[getUpdates](https://core.telegram.org/bots/api#getupdates).

Gateway **1.4.0** subscribes to private message edits while preserving polling
mode, offsets and queue durability. Edits carry an original message reference,
edit timestamp and unique Telegram update ID. The worker checks authenticated
Odoo capabilities before delivery and defers edits without consuming retries
while the consumer or its database schema awaits upgrade.

CRM Messaging **19.0.1.7.0** updates the matching incoming message in place and
retains earlier content, original location evidence and attachment bytes.
Matching requires the authorized account, sender/conversation, company, branch
and original incoming event; reaction events are excluded even when provider
references collide. Duplicate identities require identical content, and older
edits cannot overwrite newer versions. Edit evidence remains protected from
direct ORM/RPC mutation. Unknown original messages retain edit audit evidence
without creating a conversation or a fabricated original. This does not backfill
edits discarded before activation or synchronize deletions.

Sales Chatter **19.0.1.14.0** displays edited text/captions, current attachment and
location revisions, quotes and an Edited marker. Refresh also updates messages
in loaded older history without resetting drafts. Location evidence selected for
an order is frozen until staff explicitly select a location again; an edited
customer message does not silently change order delivery coordinates.

The branch picker always sends a native Telegram location. An unchecked-by-default
**Send branch details** checkbox optionally adds a second text message. The
location preview and explicit Send button remain. Both messages are queued in
one transaction with stable retry identities. Existing company/session/review
checks and fulfillment permissions are preserved.

## Live configuration

The following authorized settings were changed and independently verified:

- Odoo `tg-callcenter.branch_location_enabled = True`.
- Gateway `accounts.tg-callcenter.location_enabled = true` in its private config.

Account/global sending settings and credentials were preserved. Private before
snapshots are under `/tmp/telegram-edits-fix`; they are excluded from artifacts.
No provider test messages were sent, and WhatsApp/webhook configuration was not
enabled or changed.

Gateway restart attempts failed: `sudo -n` required a password and systemd denied
the non-interactive request. The existing gateway PIDs remained unchanged. No
PyCharm Odoo restart or live module upgrade was performed.

Activate with the existing Odoo configuration and these arguments:

```text
-d callcenter -u ab_crm_messaging,ab_crm_sales_workspace
```

Then run locally:

```bash
sudo systemctl restart crm-messaging-callcenter-worker.service crm-messaging-callcenter-receiver.service
```

Refresh the browser after the upgrade. Live edit and venue transport verification
remains pending those restarts; sending a real customer test message is not part
of this validation.

## Verification

Evidence directory: `/tmp/telegram-edits-fix`.

| Check | Result |
| --- | --- |
| Targeted isolated module upgrade with `--dev=xml` | Passed |
| Workspace business/security suite | 80 methods passed, zero errors/failures |
| Messaging ingestion/security suite | 27 methods passed; final edit lookup and reaction collision covered |
| Authenticated controller suite | 3 methods passed; capability authorization covered |
| Upgrade readiness | Capability remains false before the database version upgrade |
| Frozen delivery location with final edit lookup | Passed focused rerun |
| Browser components | 39 tests, 234 assertions passed |
| Gateway including SQLite durability | 152 passed, one FFmpeg-dependent test skipped |
| PostgreSQL gateway storage tests | Not rerun; storage implementation/schema unchanged |
| English, `ar`, `ar_001` runtime translations | Passed, including Edited, branch details and history labels |
| Existing Arabic entries | Preserved and checked against task baseline |
| Python/XML/manifest and gettext checks | Passed |

Databases: `crm_branch_final_test_20261108` and
`crm_branch_messaging_test_20261108`. Temporary HTTP/gevent pairs: 5069/5072 and
5075/5076, workers and cron disabled. Temporary browser and SQLite dependencies
were installed only in test environments. Initial validation attempts recorded
one test-assertion issue, missing temporary dependencies and locale setup issues;
the final runs listed above passed.

Runtime packages exclude development tests, static test assets, caches and private
configuration. The task patch is generated against a snapshot of the existing
uncommitted work so unrelated changes remain distinguishable.
