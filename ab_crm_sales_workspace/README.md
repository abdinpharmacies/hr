# Sales Chatter

`ab_crm_sales_workspace` extends the existing CRM/messaging addons and employee authentication. Its existing menu/action IDs are retained, with **Sales Chatter immediately after POS** under Sales. `ab_sales` and `ab_whatsapp_api` source are unchanged.

The full-height conversation list and chat workspace follow the WhatsApp dashboard layout, with customer names, message previews, unread counts, contacted-channel navigation, message history and a fixed composer. Orders has its own action under Sales Chatter and opens a POS-style editor with a draft sidebar, branch/customer summary, product cards and order lines. Conversation and message cursors load 50 records at a time. Five-second refresh preserves unsent drafts and message scroll position; switching conversations or navigating between Conversations and Orders preserves composer and order drafts in memory, scoped to the current employee and company. In-memory drafts survive re-authentication by the same employee, and remain hidden from other employees. Reloading the browser does not persist unsent local edits; use **Save draft** for durable order drafts.

Only Telegram is intended for live activation in this phase. WhatsApp remains owned by `ab_whatsapp_api`; Website integration is deferred. Channel indicators identify the selected contacted source and do not imply online status. Telegram confirmation is displayed as Sent; its bot integration supplies no customer delivery/read or presence indicators. Provider diagnostics are restricted to administrative views and logs.

## Staff workflow

1. Open Sales Chatter and sign in through its employee/PIN popup. Authorized employees share conversations without claiming. Historical assignments remain stored; employee attribution is recorded in protected logs. Order revisions and concurrent-edit checks remain enforced.
2. Self-shared Telegram contacts resolve during authenticated CRM ingestion, independently of employee sessions. Third-party shares remain unverified.
3. CRM normalizes phones using the account company country and matches within its configured intake stores. Unique matches supply catalog details; unmatched and ambiguous phones retain CRM contacts. CRM managers review matching candidates in CRM / OMS → Conversations → Contact identification. Identification evidence remains in CRM/OMS; staff reads and delivery diagnostics are restricted to managers and administrators.
4. Explicitly create an order, choose an allowed fulfillment store, add products/units/quantities and record the customer's confirmation.
5. Accept the order after selecting a branch, adding valid lines and recording customer approval. Phone verification and catalog matching are separate and do not block acceptance. Its snapshot is frozen. Reopening requires a reason, creates a new revision and clears confirmation. Old/new prices, actor/time and all order history are retained.

Server-side checks cover workspace actions and direct message/order ORM/RPC calls. Central intake permissions are separate from user/employee fulfillment-store permissions. Acceptance never submits a sale, invoice, payment or inventory operation. The icon composer supports attachments, audio recording, emoji, saved replies and keyboard sending. Its server-derived queue eligibility does not establish gateway availability or provider acceptance. AI/RAG and branch submission are deferred.

## Telegram connection

The token is entered **only in Settings → Technical → Parameters → System Parameters**, with developer mode enabled. Use key `ab_crm_sales_workspace.telegram_token.<company_id>.tg-callcenter` and paste the BotFather token as its value. Existing keys must be edited rather than duplicated.

For this development company the exact key is displayed in **Sales → Configurations → Telegram Connection**. That configuration contains only the account code, bot username, parameter key and connection status. **Prepare connection** reads the parameter and prepares the disabled account using the existing authorized company mapping. There is no token field or Intake selector, and no Telegram setup control in the Chatter workspace. Staff cannot read system parameters or the dedicated service's credential endpoint. Reception and sending remain disabled until gateway verification and explicit activation.

Chatter sessions are separate from POS sessions, last eight hours and can be closed with **Sign out**. They use existing employee PINs without changing POS authentication. Channel notifications appear in Odoo every five seconds while a Chatter session is active, including when viewing another action. Notifications are scoped to the employee, Odoo user, company and authorized branch. One sticky alert groups each conversation’s pending customer messages. Alerts persist across refresh and PIN login, independently of read positions; Sign out hides them without acknowledgment. Dismiss and successful Open conversation acknowledge only the displayed message snapshot, synchronizing tabs while retaining concurrent arrivals. Opening an alert focuses its latest customer message and preserves unsent drafts. They require a running gateway for real incoming traffic.

## Contacts and status

Contacts supports Add, Edit, Delete and Refresh. Edit/Delete use a searchable, paginated saved-contact picker. Entered phones are normalized, potential duplicates are offered without merging, and edits use local CRM display overrides without modifying catalog customers, verified identities or channel destinations. Delete archives the CRM contact while retaining messages, orders and future incoming alerts. Contacts without conversations remain visible, with sending unavailable until a channel conversation exists.

Each message has one timestamp and status footer. Internal queue acknowledgments display Sending; confirmed Telegram sends display Sent. Delivered/Read require authenticated WhatsApp receipts from its owning integration. Retry is offered only for a definitive retryable rejection, with at most three total attempts. Uncertain outcomes and invalid attachments cannot be blindly resent. Updated records the last successful conversation refresh; no customer presence is inferred.

## Development operation

See [the development runbook](../crm_messaging_gateway/DEVELOPMENT.md) for protected masked setup, account/replica mapping, loopback polling, startup/status/stop, the user-managed Odoo reload and explicit activation approval. Polling does not require a public hostname or tunnel.

[Validation](VALIDATION.md) distinguishes isolated evidence, development installation and outstanding real-pilot requirements. The workflow must not be described as live until the real Telegram pilot passes.

The order window reuses `ABMany2one` and `ab_sales.ProductCard` with channel-order adapters. Its local draft sidebar, barcode/keyboard search, units, totals and window controls never mount the POS action or write POS draft/sales records. OMS requests retain their separate models, actions, menus and lifecycle; no fulfillment bridge is introduced.
