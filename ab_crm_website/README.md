# Website Sales Chatter

Companion to `ab_storefront_callcenter_adapter`. Receives versioned confirmed-order and text-chat events into Sales Chatter, with immutable evidence and company/branch isolation. Website orders sharing a submitted phone display as incoming invoice cards in one customer conversation screen. Agents review the cards and enter products, quantities, units and delivery details manually in POS through the existing contact/header workflow.

Cards have no Create order button. Website-specific POS preparation and the POS quotation panel are removed. Invoice product details show Product, Quantity, Price, Discount and Total. Source unit values remain in the received snapshot and are hidden in Sales Chatter. No product or mapping lookup is performed. Website Orders appears under CRM / OMS; mapping navigation is inactive while existing records and XML IDs remain intact. Existing drafts, invoices, snapshots and historical handoff metadata are retained; direct contact handoffs do not update Website handoff/progress metadata.

See [the setup, security and rollout guide](../docs/website-callcenter-adapter.md). The adapter performs no automatic financial or stock operations. New native order comments and Live Chat messages use the version 2 chat exchange. Historical recovery remains excluded.

Delivery addresses display on one line as Governorate | detailed address, followed by the storefront public tracking reference (`sale.order.ab_public_reference`, for example `NO-151126-E4CRGK`). The internal order number remains in the heading. Recognized Egyptian address snapshots resolve the received governorate code to its name; unrecognized addresses retain all received text on one line. Saved snapshots remain unchanged.

A persistent Website customer identity now owns one canonical staff conversation per normalized submitted phone, configured account, branch and company. Names do not establish identity. Logged-in customers and guests follow the same submitted-phone rule; unusable phones receive an order-specific identity. This does not merge saved contacts. Each incoming message retains its originating order. Website replies require a new, validated chat event and the account sending switch. One composer sends to the latest customer message’s order or native Live Chat session. Orders share one timeline with order cards and references in the messages. The header uses centered Support/Orders icons without a selector. A reply to an earlier message retains that message’s exact destination. Each queued reply freezes its typed destination. Historical outgoing operations without validated destination evidence remain blocked for review. Telegram and WhatsApp keep their existing reply behavior. Website browser access continues to use the original order UUID through the existing storefront adapter protocol.

Existing conversations require administrator reconciliation. Run a targeted upgrade of `ab_crm_website` and `ab_crm_sales_workspace` on an isolated restored database first. Preview an account through `env['ab_crm_website_order'].website_reconciliation_preview(account.id)`, inspect its groups and `requires_review` flags, then call `website_reconciliation_apply(account.id, preview['fingerprint'])`. The bound defaults to 500 orders for the whole account and refuses a larger account rather than splitting a customer group. A changed preview must be generated again. Conflicting saved-contact associations are skipped until a manager resolves the existing associations through the reviewed contact-link workflow. Explicit inactive identity/unlink evidence is retained.

The oldest conversation remains canonical. Other conversations become historical aliases; messages, snapshots, audits and queued operations are retained. Contact/account navigation hides aliases and the canonical timeline displays their history once. Repeating reconciliation preserves that history and existing destinations. Reconciliation does not send messages or create POS invoices.

Before a runtime correction, retain a verified database/filestore backup and rehearse the same preview and preservation checks on its isolated restore. Upgrade only the two changed modules using unused alternate ports, zero workers/cron threads and stop-after-init. Python changes need a new Odoo process; an existing `--dev=xml` process cannot load them merely by refreshing the browser. Coordinate activation through the user's PyCharm process without terminating it to free a validation port. Runtime packages exclude tests, fixtures and caches; keep them in the development checkout for reproducible validation.

Website recovery and verified identity are described in `docs/website-reliable-conversations.md` in the callcenter checkout. Version 3 producers require the receiver and gateway upgrade first; the endpoint lifecycle switch defaults to disabled. Pending sends retain their original UUID and destination. A website acknowledgement proves acceptance, never customer reading.


## Order replies and private media

Received order cards and website messages expose reply arrows. The selected message determines the destination on the server; its quote remains selected until send or cancellation. A stable submission UUID protects uncertain retries, including the original destination and attachment digests. Without a selection, the latest eligible incoming message is used.

The storefront tracking chatter has a Refresh button and five-second updates. Polling pauses in hidden tabs, prevents overlap, and appends messages by ID without clearing the composer, attachments or loaded history. The separate order-chat page also provides manual refresh.

Version 4 transfers up to four files, 20 MB each, through authenticated binary endpoints. Message envelopes contain stable attachment IDs, filename, MIME type, byte length, SHA-256 digest, media kind and available voice duration. Files remain private; internal notes are excluded. Existing v1 order/text, v2 chat and v3 lifecycle exchanges remain available.

Deploy both adapters and the gateway together, upgrade only the adapters, verify the v4 round trip, then enable **Enable v4 website media** on the intended storefront endpoint. The flag defaults to off. The gateway negotiates support and reports unsupported peers for review; it never acknowledges incoming media until all bytes and the message are stored in callcenter. Deployment, endpoint activation and user-managed service restarts are separate operations.

The website receiver accepts optional customer phone metadata (a string of up to 64 characters); visitors cannot supply it. Names and phones are display metadata, while account UUIDs retain ownership. Empty phone clears the displayed phone; legacy envelopes without phone remain valid. Only the conversation header channel shows the source icon: the existing Abdin bot for floating chat, or the supplied image for order conversations. Its tooltip and accessible label identify the selected source and stored order reference. Message bubbles and reply previews do not repeat source icons.

Version 3 also accepts `order_dispatched`, restricted to an order destination. It permanently closes that order's reply destination, retains readable history and posts one translated delivery-closure notice. Other orders and floating sessions remain usable. Guest session-end events post one translated guest-leave notice; delayed/replayed closure events do not duplicate it or reopen the session. Existing accepted submissions remain replayable and queued sends are checked again before delivery. Upgrade this receiver before enabling the source's dispatch-lifecycle producer flag. No deployment, status backfill or automatic reopening is performed.

## Explicit conversation targets and read positions

Detail/history, composer uploads and read updates use an explicit `{kind, uuid}`
target. Support and Orders each present one combined timeline inside a customer row; drafts are separate by channel. Individual message destinations, read positions remain target-specific. Legacy reply routing is accepted only
when its destination is unambiguous.

New guest departure information comes from immutable lifecycle events. Existing
protected notices remain readable as information rows; ordinary messages are
never identified by their text. Lifecycle information does not count as unread,
change the inbox preview or advance received-message activity.

New order grouping uses verified account or optional trusted browser identity,
never contact names or phone numbers. Guest origin is fixed at capture and
survives later account handoff. Read positions are private to the Odoo user and
verified employee, account, branch, company and target. The model has no direct
staff CRUD access. Chat archival and restoration are removed; all histories remain
visible, including ended guest sessions and closed orders. Inbox ordering uses
received messages only, newest first, across canonical aliases.
Install receiver support before enabling optional source checkout metadata.

## Independent chats (19.0.1.16.0)

Every website order and Support session has its own inbox entry, history, draft,
attachments and read position. Notifications open the exact notified target and
message. Customer associations remain evidence; they do not combine chats.
Manual chat linking and website reconciliation are disabled. The general Inbox
Refresh remains available. See `RELEASE.md` for activation and rollback.
