> Historical feature and validation record. The [2026-11-11 retirement report](messaging-legacy-retirement.md) records the completed rollout and supersedes earlier pending-maintenance and historical-receipt backlog statements below.

# Unified contacts and unrestricted inbound reception

Source versions: CRM Messaging 19.0.1.10.0, Sales Chatter 19.0.1.17.0,
WhatsApp Sales Chatter 19.0.1.5.0, gateway 1.6.1.

## Reception diagnosis

Read-only inspection on 2026-11-10 found seven WhatsApp incoming events pending
with zero attempts, plus two earlier delivery-status events in review after eight
attempts. Both reviewed statuses have no matching Odoo send operation. The queue
stored only `odoo_rejected_or_unavailable`; the historical exception was swallowed
by the worker, so the original exception text cannot be recovered from that record.
The current rejection was reproduced in an isolated Odoo regression:
`Provider acceptance is not recorded yet. Retry this status later.`

The queue's ordering predicate treated incoming messages and delivery statuses as
one sequence for a recipient. A reviewed status therefore prevented the worker
from claiming subsequent incoming messages. A failing SQLite regression reproduced
this condition before the fix; the corrected PostgreSQL and SQLite predicates
preserve ordering separately for each event kind, and per provider message
reference for delivery statuses. Status evidence remains in review.
No incoming event or status is deleted or silently marked delivered.

Independent digits-only checks also quarantined opaque incoming sender identifiers
at the gateway and rejected them in Odoo. A failing normalization regression
reproduced this restriction. Incoming printable ASCII provider identifiers now
remain intact through storage, Odoo, history projection and the unlinked inbox.
They need no phone or saved customer. Outgoing destination validation remains
separate. Signatures, business-account routing, scoped service users, deduplication,
media limits and existing outgoing uncertainty protections remain in force.

## Contact and inbox behavior

- Module-owned normalized phone rows retain labels, activity, confirmation evidence,
  actor and time. Contact responses retain `phone` and add `phones`.
- Additional numbers require explicit same-customer confirmation and a reason.
  Managers alone resolve shared-number and identity-ownership conflicts. Direct
  ORM writes to protected phone associations are rejected, including context defaults.
- Initialization is an idempotent manager action. It uses the effective saved phone;
  a different legacy phone remains inactive and is returned for review. External
  catalog customers are never modified.
- Linking uses all active numbers and a fingerprint. A branch lock and write fence
  serialize competing associations; confirmation rechecks account, contact,
  conversation, scope and evidence. A self-shared Telegram contact stores control
  evidence and offers saved-contact suggestions; reception never creates a saved
  customer automatically. New association remains an explicit staff decision.
- Managers can preview and confirm consolidation. The canonical contact retains
  reviewed active numbers and identity links. Superseded contacts are archived with
  a canonical reference. Conversation/message IDs, order snapshots, outgoing
  operation destinations and channel histories remain intact.
- One inbox row groups accessible conversations by company, intake branch and saved
  customer. Active numbers are searchable, including normalized local formatting.
  One top icon per channel opens directly or shows a chooser with destination,
  business inbox and unread count. Selection persists by employee/company/contact.
- Drafts, quotes, attachments and read positions remain keyed by conversation ID.
  The heading shows the actual channel destination. Contact editing preserves the
  selected conversation. Orders with phone lists require an explicit phone choice;
  old order phone snapshots and queued reply destinations remain unchanged.
- English UI and both Arabic catalogs include the new controls. Both LTR and RTL
  channel choosers are covered by browser tests.

## Requested live association

Read-only verification found one saved customer for **+201014763233**, a Telegram
conversation whose profile name is **Hassan Hosny**, and self-owned Telegram contact
messages proving control of that exact phone. Before rollout, WhatsApp's conversation for the same
number was unlinked and the saved name override was numeric. No duplicate saved
contact was found for this
requested number. These observations do not replace fingerprint checks at rollout.

During the user-managed maintenance window:

1. Have the user stop the PyCharm callcenter Odoo process; never stop it on their
   behalf. Preserve the Telegram polling process and credentials. Verify the current
   source, branch, addons path, live database and free alternate ports again.
2. Back up the `callcenter` database and its filestore, gateway database and protected
   configuration privately. Retain the previous verified source packages and dispatch
   fix. Capture queue counts without printing credentials or message contents.
3. Run a targeted upgrade of
   `ab_crm_messaging,ab_crm_sales_workspace,ab_crm_whatsapp_workspace` using
   `/opt/odoo19/conf/callcenter19.conf`, the callcenter worktree addons path,
   `--stop-after-init --http-port=5069 --gevent-port=5072 --workers=0 --max-cron-threads=0`.
   Do not use `-u base`. The user resumes the PyCharm process afterward.
4. Reload only the WhatsApp receiver and shared delivery worker with compatible
   source. Leave the dedicated Telegram polling receiver, its credentials and
   sending settings unchanged. Normal reception accepts all senders.
5. In an authorized employee session, initialize the existing contact's numbers,
   save its name as Hassan Hosny, preview the WhatsApp link and confirm the exact
   fingerprint with a reviewed reason. Retain the existing verified Telegram link.
   Verify one row and both independent histories/destinations.
6. The seven pending inbound events should be claimed normally after the worker
   reload; they need no resend or reset. Reconcile the two unmatched delivery statuses
   separately. Do not blindly retry statuses that still have no accepted operation.
7. If a reviewed incoming event was quarantined solely for `unsupported_identity`,
   use `app.ops retry-incoming --event-id ... --note ...` after review. This removes
   only the obsolete routing marker, updates the normalized fingerprint and retains
   the event identity, source digest and original message content. Operator audit is
   preserved. Other recoverable failures use the same bounded retry workflow.
8. Legacy unsupported events storing only a digest cannot reconstruct omitted
   attachments. Resend only those originals when needed. Agent-initiated live
   WhatsApp tests are restricted to **+201014763233**; other cases stay synthetic.

## Verification and artifacts

Isolated validation uses `callcenter_whatsapp_dispatch_test_20261109`, ports
5069/5072, zero cron threads and workers. Real two-transaction contention uses a
separate `callcenter_unified_contacts_concurrency_test_20261110` clone. No live
messages were sent, and no live data or services were changed during source work.

Logs are `/tmp/unified-contacts-acceptance.log`,
`/tmp/unified-contacts-gateway-status-final.log`,
`/tmp/unified-contacts-scope-languages.log`,
`/tmp/unified-contacts-queue-snapshot.log`, and
`/tmp/unified-contacts-concurrency.log`.
Runtime packages are in `/tmp/unified-contacts-validation/packages/`.

Final isolated Odoo acceptance: 130 tests, zero failures/errors. Desktop browser
coverage: 62 tests / 368 assertions; mobile channel coverage: 12 tests / 50
assertions. The real shared-number race rejects the stale transaction and requires
manager review on its fresh retry. Both Arabic runtime catalogs and English field
labels passed. A focused queued-reply test confirmed destination immutability.

The gateway suite passes 200 tests, with one existing real-codec test skipped
because FFmpeg/ffprobe are unavailable. Existing isolated clones have missing
legacy avatar files; those logged fixture warnings are unrelated to message media.
Synthetic acceptance alone does not establish new Meta delivery. The completed
live rollout and previously received backlog are documented below.

## Recovery

Retain all phone rows, identity audits, conversations, messages, order snapshots and
queue receipts. Do not roll back by deleting records or resetting uncertain outgoing
operations. Restore a compatible source package with the dispatch fix preserved if
needed, and reconcile any in-flight operation before separately authorizing retries.


## Live rollout completed — 2026-11-10

The user opened the maintenance window and stopped/resumed their PyCharm Odoo
process. The targeted live upgrade completed with exit code zero and no errors.
Private verified backups of the database, filestore, gateway queue/configuration
and previous verified source are in `/tmp/unified-contacts-live-backup-20261110/`.
The user reloaded the WhatsApp webhook service and shared worker using their sudo
authentication. The dedicated Telegram polling receiver remained PID 156203.
Credentials and sending configuration were unchanged. No live test messages were
sent by the agent.

The browser connector failed to load its request-header policy, so live visual
verification was unavailable. A bounded administrative Odoo ORM operation completed
the already-authorized association, validating the sole active administrator
employee session, eligibility, scope, existing self-owned Telegram phone evidence,
signed WhatsApp sender and reviewed fingerprints. It preserved existing records
and wrote actor/employee, time, old/new values and reason to the protected audit.
No authentication/session records or credentials were changed.

The existing contact is now **Hassan Hosny**, primary phone **+201014763233**,
with WhatsApp and verified Telegram identities. The two conversations have one
canonical inbox group. All 98 messages and 41 queued destinations were preserved.
All seven previously blocked inbound events drained, each with exactly one Odoo
message and one WhatsApp history projection. The source-level UI tests verify the
same grouping and independent channel navigation.

The final worker update additionally separates status ordering by provider message
reference. Unmatched historical delivery statuses retain their evidence for review;
they do not block incoming reception or updates for unrelated outgoing messages.
Do not mark those statuses successful or resend uncertain outgoing messages merely
to clear the queue.

Final live queue verification: all 21 WhatsApp incoming events are done (the original
14 plus seven recovered). Completed status events increased from 11 to 17, confirming
all six valid blocked updates drained. Fifteen pending and two reviewed historical
statuses have no corresponding recorded send operation; their evidence remains in
the bounded retry/review workflow. No pending status has a matching send operation.
The user-managed Odoo process is PID 797497 and the final worker is PID 803959.
Temporary validation ports 5069/5072 are released. Protected Odoo and gateway
configuration files are byte-for-byte unchanged from the pre-upgrade backup.
