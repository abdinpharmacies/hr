> Historical feature and validation record. The [2026-11-11 retirement report](messaging-legacy-retirement.md) records the completed rollout and supersedes earlier pending-maintenance and historical-receipt backlog statements below.

# Automatic same-phone linking and Callcenter intake diagnosis

Sales Chatter **19.0.1.19.0** supersedes the earlier requirement to review every
first channel association. It is source-tested and packaged; live deployment is
still pending the user-managed maintenance window.

## Automatic behavior

When an authorized employee opens or refreshes Sales Chatter, or its notification
poll runs, an unlinked Telegram/WhatsApp conversation automatically joins the one
active saved customer with the same normalized phone, within the same company and
intake branch. Existing unlinked conversations are included. A newly received
matching conversation is linked on the next authorized refresh/poll; the messaging
receiver itself does not make elevated staff decisions.

WhatsApp evidence comes from an accepted inbound event and its sender number.
Telegram evidence comes from the sender sharing their own Telegram contact.
Typing a number, a numeric Telegram account ID, a profile name or a third-party
contact card is not equivalent evidence.

Equivalent formats such as `+201098320212`, `+20 1098320212` and `01098320212`
match. Active additional numbers participate. Archived phone rows/customers,
ambiguous shared numbers, inactive identity links and conflicting ownership do not
automatically move to another customer. Those exceptional cases retain the
manager/manual workflow. Separate saved customers are not collapsed solely because
they share a number.

For an exact eligible match, the link picker also finishes without showing the
review-reason form. The server rechecks the fingerprint and unique match under the
branch lock. It records the acting employee/user, time and phone evidence using
`auto_link_customer`; no fabricated human confirmation is recorded.

Conversation IDs, message histories, order snapshots, queued destinations, unread
positions and drafts remain independent and unchanged. One saved customer groups
those conversations in the inbox and popup notifications. External catalog
customers are never written by this association.

## Existing-contact picker follow-up

Version **19.0.1.23.0** removes both the written-reason requirement and extra
same-person checkbox from manual existing-contact linking. Its icon is in the Contacts toolbar beside Add, Edit
and Archive. The picker is scoped to the current conversation branch; a phone
match is unnecessary when the agent selects the contact and saves the association. Ownership-conflict
resolution and company/branch permissions remain enforced. See the latest
rollout section in `docs/phone-display-alerts-rollout.md` for validation/packages.

## What “Telegram Callcenter Intake” does

Read-only inspection of the live `callcenter` database confirmed:

| Setting | Current configuration |
| --- | --- |
| Record type | CRM intake branch (`ab_crm_branch`) |
| Display name | Telegram Callcenter Intake |
| Stable code | `telegram-callcenter-intake` |
| Telegram account | `tg-callcenter`, displayed as `abdin_callcenter_bot` |
| WhatsApp account | `wa-callcenter`, displayed as `WhatsApp` |
| Replica mapping | فرع العتبة القاهرة |
| Default intake store | مخزن افتراضي |
| Allowed sales stores | فرع العتبة القاهرة and مخزن افتراضي |
| Active saved replies in this intake | 44 |

Both messaging accounts are active with reception and outgoing enabled. The
intake branch scopes staff/company access, saved customer association, grouped
conversations, available saved replies and the eligible sales stores. Each order's
selected store is separately validated against these stores and the employee's
permissions; the intake label is not the fulfillment destination.

The Telegram wording is a legacy display name. WhatsApp preparation deliberately
reuses the existing Telegram intake/company so both channels can share customer
scope. It does not represent an additional Telegram account or require messages
to pass through Telegram. **Callcenter Intake** would be a clearer display name.
Only the display name would need changing; keep the branch record, stable code,
account mappings and existing business records. No rename or routing configuration
change was performed during this diagnosis.

Relevant source:

- `ab_crm_core/models/core.py`: branch, channel and scope relationships.
- `ab_crm_sales_workspace/models/workspace.py`: intake replica/default store and employee/store authorization.
- `ab_crm_whatsapp_workspace/models/account.py`: WhatsApp preparation reuses the Telegram intake mapping.
- `ab_crm_sales_workspace/models/customer_streams.py`: customer grouping and automatic phone association.

## Verification and rollout

- Isolated targeted upgrade and full acceptance: **140 Odoo tests**, zero failures/errors.
- Desktop: **72 browser tests / 433 assertions**; mobile: **12 tests / 50 assertions**.
- Cases include equivalent/secondary numbers, verified versus third-party evidence,
  shared/archived phones, unauthorized employees, invalid sessions, branch scope,
  exact-ID history preservation, order/queue snapshots, audit idempotency and no
  review-reason dialog for a verified match.
- The dedicated two-transaction test verifies that stale simultaneous association
  is rejected and a fresh retry leaves exactly one identity and one audit entry.
- Existing English and both Arabic catalogs are retained. Runtime language tests
  remain in the full suite, and both PO catalogs pass format validation.
- The isolated clone contains existing missing-avatar fixture warnings, unrelated
  to messaging media or these changes.

Test databases: `callcenter_auto_phone_link_test_20261110` and
`callcenter_auto_phone_link_race_test_20261110_final`. Logs and private validation config
are under `/tmp/auto-phone-link-validation/`. Runtime archives/checksums are under
`/tmp/auto-phone-link-validation/packages/`; tests and test asset declarations are
excluded from those archives. The previous-source package preserves all work that
existed at the beginning of this follow-up.

Deploy Sales Chatter with a database/filestore backup and the targeted
`-u ab_crm_sales_workspace` procedure in `docs/phone-display-alerts-rollout.md`,
using free alternate ports 5069/5072, zero workers/cron, and `--stop-after-init`.
The user controls the live maintenance window and their Odoo process. No live
upgrade, customer mutation, external catalog write, configuration change or test
send occurred during this work. Normal WhatsApp reception remains open to all
senders; any later agent-initiated live test send remains restricted to
`+201014763233`.
