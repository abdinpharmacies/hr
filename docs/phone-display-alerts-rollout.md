> Historical feature and validation record. The [2026-11-11 retirement report](messaging-legacy-retirement.md) records the completed rollout and supersedes earlier pending-maintenance and historical-receipt backlog statements below.

# Egyptian phone display and customer alerts

Sales Chatter version **19.0.1.18.0** builds on the existing unified-contact,
reception and dispatch changes. This increment changes only Sales Chatter source.
It has not been deployed to the live Callcenter database.

## Behavior

- `+201098320212`, `+20 1098320212` and `01098320212` display as
  `01098320212`. Parsing uses the company country; read-only inspection confirmed
  the live Callcenter company is configured as `EG`. Other countries retain
  international display formatting. Telegram account IDs remain unchanged.
- APIs retain existing phone/destination values and add display values. Searches
  recognize equivalent and partial national/international forms, including legacy
  effective contact phones. This does not rewrite legacy records or merge by name.
- Add offers Create new and Use existing. Selecting a saved customer opens its
  editor and retains the proposed phone for explicit confirmation. Editors expose
  scoped channel accounts, reviewed association and manager merge controls.
- Editing and archival preselect the current saved customer. Phone correction uses
  add, primary selection and archive actions. Customer archival preserves messages
  and orders. Merge previews separate each customer's phones, identities and
  conversations; the canonical details and primary phone remain authoritative.
- One customer row and one icon per channel retain per-conversation destinations,
  business inbox labels and unread counts. The chooser indicates selection and
  supports arrow/Home/End navigation, Escape and outside clicks.
- Unread state is employee/company/conversation scoped. Reading removes popup
  eligibility; dismissal acknowledges only the captured message IDs without
  advancing reads. Later arrivals remain eligible.
- Popup grouping spans all response pages; each conversation has its own action.
  Unlinked senders remain separate. Successful reads/acknowledgments refresh badges
  and synchronize only tabs for the same employee/company.
- Alert navigation reuses conversation selection, retains text/attachments/quotes,
  remembers the exact stream and focuses the exact message. Failed navigation does
  not dismiss the alert. Hidden/unfocused tabs, search and older-history views do
  not automatically advance reads; Jump to latest returns to normal reading.

## Verification

Dedicated databases:

- `callcenter_phone_alert_test_20261110`: targeted Sales Chatter upgrade and tests.
- `callcenter_phone_alert_race_test_20261110`: independent transaction-contention
  test cloned from the existing isolated validation database.

Both used the Callcenter worktree addons path, zero workers/cron threads and
alternate ports 5069/5072. The live Odoo process was not stopped or restarted.
No live message was sent, no live data was changed, and no external catalog was
written. The existing test clone has missing legacy avatar files; these produced
fixture warnings. Its CSS filestore was copied before successful browser checks.

- Full acceptance: **135 tests, zero failures/errors**.
- Desktop browser acceptance: **71 tests, 430 assertions** in the final focused
  run, including customer grouping, pagination, captured-ID dismissal races,
  failed navigation, employee/company tab isolation, keyboard controls, exact
  message focus, drafts and attachments, merge preview and older-history reads.
- Mobile browser acceptance: **12 tests, 50 assertions**, including LTR/RTL
  multiple-number navigation. Desktop tests also validate LTR/RTL layouts.
- Real transaction contention: stale concurrent shared-number association rejected;
  fresh retry requires manager review.
- Both Arabic catalogs cover exported terms and pass `msgfmt --check-format`.
  Runtime tests verify new Arabic labels for both `ar` and `ar_001`.
- Python/XML/JavaScript parsing and whitespace checks passed. Runtime archives
  omit tests, test asset entries and caches.

Evidence lives in `/tmp/phone-alert-validation/`: `final-acceptance.log`,
`final-browser.log`, `history-browser.log`, `concurrency.log`, and
`final-strings.pot`. Runtime/previous-source archives and checksums are in
`/tmp/phone-alert-validation/packages/`. The previous-source archive preserves
all pre-existing uncommitted Sales Chatter fixes from the start of this task.

## User-managed deployment window

1. Confirm the user has opened the maintenance window and stopped their
   PyCharm-managed Callcenter process. Check that ports 5069/5072 are free without
   terminating any process. Recheck config, addons path and database selection.
2. Privately back up the live `callcenter` database and filestore and retain the
   previous verified source. Preserve the existing reception/dispatch fixes and
   the configured gateway services. Do not restore the entire old worktree over
   unrelated ongoing changes.
3. Deploy the verified Sales Chatter runtime package and run the targeted upgrade:

   ```bash
   /opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin \
     -c /opt/odoo19/conf/callcenter19.conf -d callcenter \
     --addons-path=/opt/odoo19/server/addons,/opt/odoo19/worktrees/callcenter19 \
     -u ab_crm_sales_workspace --stop-after-init \
     --http-port=5069 --gevent-port=5072 --workers=0 --max-cron-threads=0
   ```

4. Inspect the upgrade log; have the user resume their Odoo process and refresh
   browser assets. Verify national phone display, both Arabic locales and one
   customer with two WhatsApp conversations plus Telegram. Confirm each opens the
   correct history and destination, and dismissing one captured alert does not
   mark messages read or suppress a later arrival.
5. Review legacy duplicate suggestions manually using the manager preview. Do not
   automatically merge, change external catalog records, redirect conversations
   or retry queued replies. Normal WhatsApp reception remains open to all senders;
   agent-initiated live test sends remain restricted to `+201014763233`.

If recovery is needed, restore a compatible previous Sales Chatter runtime source
with the existing reception/dispatch fixes retained. Preserve all message IDs,
order snapshots, contact evidence and queued destinations; do not delete business
records or reset uncertain outgoing operations.

## Same-phone association follow-up

Sales Chatter 19.0.1.19.0 automatically links uniquely matched verified channel
numbers without the review-reason prompt. See `docs/automatic-phone-linking.md`
for the exact eligibility rules, newer packages, validation and the read-only
“Telegram Callcenter Intake” diagnosis. The maintenance-window procedure above
still applies.

## Customer-only header follow-up

Sales Chatter **19.0.1.20.0** supersedes the earlier header presentation: both
Telegram and WhatsApp headings show only the customer name and formatted customer
phone. They no longer show account IDs, bot/business inbox labels, update times
or unread counts. Channel icons and chooser entries also omit unread badges.
Customer-list unread badges and popup alert behavior remain available.

Verification uses the existing isolated `callcenter_auto_phone_link_test_20261110`
database and alternate ports 5069/5072. Evidence and current/previous runtime
packages are in `/tmp/chatter-header-validation/`. Live deployment still follows
the user-managed maintenance-window procedure above.

Header validation passed: 72 desktop browser tests (436 assertions), 12 mobile
browser tests (50 assertions), and the focused Odoo run reported 5 tests with zero
failures/errors. Both Arabic catalogs pass `msgfmt --check-format`.

## Channel-link icon follow-up

Sales Chatter **19.0.1.21.0** replaces the text link action with a chain-link icon
beside the channel icons. It opens the existing contact picker for the current
conversation, allowing its channel to join the saved customer's grouped row.
The existing server-side association checks and customer-only heading remain.

Targeted upgrade and browser validation passed in
`callcenter_auto_phone_link_test_20261110` on ports 5069/5072: 3 Odoo tests,
72 desktop browser tests (440 assertions), and 12 mobile tests (54 assertions),
with zero failures. Both Arabic catalogs pass `msgfmt --check-format`.
Current and previous runtime packages, checksums and logs are available in
`/tmp/chatter-link-icon-validation/`. Deployment remains pending the user-managed
maintenance window; the running user process was not stopped or restarted.

Separately, the user-identified invalid unidentified-sender conversation was
archived through the live Odoo ORM. All three original messages were retained;
it had no saved customer, orders or queued operations. A read-only follow-up
confirmed the archive and the four valid conversations remain active.

## Contact toolbar and reason-free linking follow-up

Sales Chatter **19.0.1.22.0** removes the reason field and mandatory reason
validation for existing-contact association. The chain-link icon now sits beside
Add, Edit and Archive in the Contacts toolbar, including mobile. It requires a
selected conversation.

Agents may select an active contact without a matching phone; explicit same-person
confirmation remains where sender evidence is unavailable. The picker searches
the conversation's branch instead of offering contacts that cannot be linked.
Specific missing-record/scope messages replace the generic matching-customer error
in this flow. Company/branch access, manager conflict resolution, fingerprint
checks, locking and audit attribution remain enforced through ORM/RPC. Phone
maintenance and duplicate-consolidation reasons are separate workflows.

Final isolated validation passed: 6 Odoo tests, including unauthorized calls,
stale previews and branch isolation; 73 desktop browser tests (448 assertions)
and 12 mobile tests (57 assertions), with zero failures/errors. Both Arabic
catalogs pass format checks. Runtime packages, previous-source rollback package
and SHA256 checksums are under `/tmp/contact-link-reason-validation/packages/`;
logs are in its parent directory. No live upgrade or restart was performed.

## Linking without an extra identity confirmation

Sales Chatter **19.0.1.23.0** removes the same-person checkbox and its server
validation for linking an existing contact. Selecting the contact and saving is
enough. The preview retains `requires_confirmation: false` for compatibility,
and the optional RPC argument remains accepted. Audits record the actual
supplied confirmation/evidence instead of assuming that the customer confirmed.
Manager conflict resolution, scope, fingerprints and locking remain enforced.

Evidence and current/previous runtime packages are in
`/tmp/contact-link-confirmation-validation/`. Live deployment still follows the
maintenance-window procedure; no live upgrade or restart occurred.

This increment passed 6 Odoo tests with zero failures/errors, including agent
linking on both channels, conflicting ownership, stale fingerprints and preserved
message/destination evidence. Browser coverage passed 73 desktop tests
(449 assertions) and 12 mobile tests (57 assertions). Both Arabic catalogs pass
`msgfmt --check-format`; existing translations remain preserved.

## Inbox unlink and native notification follow-up

Sales Chatter **19.0.1.24.0** renames the sidebar heading to Inbox (الوارد).
The contact toolbar shows Unlink only when the selected customer groups multiple
conversations. One action separates all those conversations into independent
inboxes, retaining the saved customer, message IDs, order snapshots, sender
evidence and queued destinations. Archived identity associations prevent
automatic relinking on later refresh or incoming messages. Manual linking remains
available. Access checks, branch locking, snapshot fingerprints and protected
employee/user audits apply to the whole group.

Duplicate-consolidation entry points, the inline unlinked-review notice and the
redundant Create/Edit buttons below the conversation header are removed.

Alerts use Odoo's native notification service with `sticky: true`, one notification
per customer and a separate open action per conversation. They remain until acted
on or their message eligibility is cleared by a read. Closing acknowledges only
the captured message IDs, without marking messages read; later arrivals alert
again. Failed navigation retains alerts. Poll updates/session cleanup close
notifications silently, and the service waits for localization before building
translated notification text. Unlink broadcasts a refresh for grouping/badges.

Validation: six targeted server tests passed for unlink history/queue preservation,
Telegram/WhatsApp separation, unauthorized access, stale previews, notification
read/dismissal behavior and both Arabic catalogs. The final browser run passed
3 Odoo browser cases: 74 desktop tests (464 assertions) and 13 mobile tests
(68 assertions), with zero failures/errors. The initial notification harness
failures were resolved and rerun; final evidence is in
`/tmp/contact-unlink-validation/browser-verified.log`, with server evidence in
`/tmp/contact-unlink-validation/acceptance.log`. Both PO files pass format checks.
Runtime and previous-source packages/checksums are in
`/tmp/contact-unlink-validation/packages/`. No live upgrade, restart, unlink or
external message test was performed. Deployment remains within the user-managed
maintenance-window procedure above.

## Connection recovery and native screen feedback

Sales Chatter **19.0.1.25.0** and WhatsApp workspace **19.0.1.6.0** move transient
errors, warnings and information from the Chatter screen and its dialogs to
sticky native Odoo notifications. Order save/discard and branch repricing keep
their explicit action buttons. Normal form choices and message status content
remain part of the screen.

Interrupted inbox requests show one readable connection warning without the
technical RPC URL. Repeated polling failures do not create duplicate warnings;
successful recovery is reported after failed inbox/notification reads recover.
The current inbox, history, drafts and attachments remain available. Cached
sessions recover after a startup outage. Sends, saves and other mutations are
never automatically replayed after an uncertain response.

The targeted isolated upgrade and Arabic runtime translation check passed.
Final browser verification passed 78 desktop tests (501 assertions) and 13 mobile
tests (69 assertions), across 3 Odoo browser cases with zero failures/errors.
Coverage includes connection loss/recovery, retained drafts after failed sends,
inbox preservation and native action confirmations. Both Arabic catalogs pass
format checks, and the fresh Odoo POT export contains the new connection strings.
Evidence is in `/tmp/chatter-feedback-validation/acceptance.log` and
`/tmp/chatter-feedback-validation/browser-verified.log`. Current and previous-source
runtime packages with SHA256 checksums are under
`/tmp/chatter-feedback-validation/packages/`. Temporary validation ports are
released. No live upgrade, restart or external message was performed; deployment
remains pending the user-managed maintenance window.
