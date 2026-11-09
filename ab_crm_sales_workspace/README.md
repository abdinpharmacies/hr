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

Each message has one timestamp and status footer. Internal queue acknowledgments display Sending; confirmed Telegram sends display Sent. Delivered/Read require authenticated WhatsApp receipts from its owning integration. Retry is offered only for a definitive retryable rejection, with at most three total attempts. Uncertain outcomes and invalid attachments cannot be blindly resent. The header shows recorded incoming activity and the latest outgoing status; no customer presence is inferred. Employee reading advances only through a visible message in the active, unobscured conversation. Fetching history or polling does not acknowledge reading.

## Development operation

See [the development runbook](../crm_messaging_gateway/DEVELOPMENT.md) for protected masked setup, account/replica mapping, loopback polling, startup/status/stop, the user-managed Odoo reload and explicit activation approval. Polling does not require a public hostname or tunnel.

[Validation](VALIDATION.md) distinguishes isolated evidence, development installation and outstanding real-pilot requirements. The workflow must not be described as live until the real Telegram pilot passes.

The order window reuses `ABMany2one` and `ab_sales.ProductCard` with channel-order adapters. Its local draft sidebar, barcode/keyboard search, units, totals and window controls never mount the POS action or write POS draft/sales records. OMS requests retain their separate models, actions, menus and lifecycle; no fulfillment bridge is introduced.


## Message navigation and actions

The centered channel row shows existing, authorized conversations linked to the same customer record, branch and company. Account labels distinguish multiple accounts. Switching preserves each conversation’s draft, attachments and quoted reply. Deferred or absent integrations are not activated and no conversations are created by navigation.

Right-click, the message chevron and Shift+F10 open the same menu: Reply, eligible reactions, Copy, Preview/Download and eligible Retry. Unsupported Edit/Delete actions are hidden; temporary restrictions include their server-provided explanations. Editable fields, links, selected text and Shift+right-click retain native menus. Images, audio and PDFs open in the attachment viewer; other ready files remain downloadable. Quoted replies include a bounded summary and available image thumbnail. Opening a quote loads a bounded original-message context and focuses it after rendering; inaccessible originals show a neutral fallback. Reaction events remain in the immutable history.

`workspace_detail` and `workspace_focus` are read-only with respect to employee read positions, including when a legacy caller supplies `mark_read=True`. `workspace_acknowledge(message_id)` validates the employee session and target conversation before monotonically advancing the private read position. `workspace_channel(conversation_id)` validates the linked destination; `workspace_reply(message_id)` resolves incoming or outgoing originals within the authorized conversation. These APIs do not alter provider delivery/read evidence.

Chatter's compact header shows the latest message update beside the contact in the user's timezone, with icon-only channel switches and an active indicator. Reactions stay on their target messages. Failed sends use an inline warning; eligible retries appear on hover or keyboard focus and reuse the same message. Uncertain sends and invalid media keep their existing retry restrictions. Attachment previews and draft cards use the active channel's color.


## Templates, search and unread navigation (19.0.1.10.0)

Saved replies use a searchable list and editor/preview, stacked on narrow screens. Managers can create, update and archive replies. Creation selects the saved record so subsequent saves update it; Refresh retains a valid selection and Archive clears it. Discard/Keep editing protects unsaved changes, including closing the dialog. Required parameters must contain nonblank values. Insert into composer never sends a message. The optional WhatsApp addon keeps approved templates in a separate dialog with an explicit Queue action.

The composer contains twelve emoji choices and replaces the current selection, restoring the caret. Escape and outside clicks dismiss the picker. Server eligibility still controls message reactions independently.

The first-unread marker is captured when opening a conversation and remains stable after acknowledgement. First unread loads older context on demand; Jump to latest remains available while viewing history and displays the current unread count. Conversation search submits with Enter/Search, returns newest matches first in pages of 50 and offers Older results. Selecting a match focuses timeline context without replacing the draft; Clear keeps the current timeline position. Stale query/channel responses are ignored.

Image thumbnails load near the visible timeline through the authenticated private-media operation. File cards show names, formatted byte sizes and preview/download controls. Removed thumbnails and closed viewers release their object URLs; delayed responses cannot recreate URLs after unmount. No public media routes or provider operations were added.

The additive response fields are `save_template.selected_id` (saved ID or false on archive), `workspace_detail.first_unread_message_id`, `workspace_detail.unread_count`, `workspace_reply.has_older`, and media `size`. Read metadata belongs only to the authenticated employee/session. Fetching/searching does not acknowledge reading.


## Floating navigation and bilingual reply library (19.0.1.10.1)

The centered search icon sits between the contact details and channel controls. Search opens over the timeline without changing the header or message-area height; Escape, Close and outside clicks dismiss it. Selecting a result closes the panel and focuses its message. First unread remains available inside the search panel. Read acknowledgement pauses while the search overlay obscures messages.

Jump to latest is a circular down-arrow at the bottom center of the message area, with a transparent, nonblocking outer container and the existing unread badge.

The reviewed library in `resources/pharmacy_cosmetics_saved_replies.csv` contains 22 English/Arabic pairs for pharmacy and cosmetics service: greetings, exact product details, quantities, stock checks, prescription review, pharmacist handoff, delivery/contact details, pickup, order review/totals/confirmation, cosmetics shades/preferences, packaging/expiry enquiries, changes/cancellation, issues/returns and closing. It contains administrative wording rather than medicine recommendations or medical claims. Most replies need no edits; transactional totals, estimates, references and summaries have required placeholders. Confirm facts before inserting a status/price reply.

On the user's explicit request, 44 replies were added through Odoo ORM to the existing `telegram-callcenter-intake` branch in `callcenter`, with branch/company validation and stable module-owned XML IDs. Three existing replies at import time were preserved; no message or sending operation was created. This was a bounded data addition, independent of the source UI changes: no live module upgrade or process restart. The catalog is not automatically installed into arbitrary branches. Staff can use Templates → Refresh and search by EN, AR or topic.

The embedded message box places attachments at the start and emoji, audio recording and Send at the end, mirrored in Arabic. Hover or click the paperclip for Photo/video, Location, Document, Music and saved templates. Location inserts a coordinate map link for review; it does not send a native location event or send automatically. Outgoing MP4 videos use private media access and the existing queue, with a 16 MB limit and gateway H.264/AAC verification. Video sending requires the corresponding gateway update and its FFmpeg/ffprobe dependency. Conversation search uses an in-field guidance placeholder without increasing header height.
