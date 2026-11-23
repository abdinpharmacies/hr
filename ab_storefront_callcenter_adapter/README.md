# Storefront Callcenter Adapter

Install this companion on the ecommerce checkout. It depends on `ab_ecommerce_storefront` and leaves the storefront, customer API, login, payments and reservation implementations unchanged. Confirmed ordinary new orders produce durable snapshots in the confirmation transaction. Adapter-owned text chat uses authenticated ownership or originating-session ownership plus a hashed private guest capability.

Configure Callcenter Endpoints before enabling intake. Invoice lines include the readable source unit name as optional `unit_name`, alongside the original unit code. Callcenter displays the received values without product or unit mappings; agents enter invoices manually in POS. Use the gateway Website worker and `ab_crm_website` on callcenter. The full setup and rollout guide is `docs/website-callcenter-adapter.md` in the callcenter checkout. No live endpoint configuration or worker activation is included.

Snapshots carry the native storefront `ab_public_reference` as optional `public_reference`, separately from the internal `reference` number. Sales Chatter uses the public value in its Order Reference row.

New endpoints select existing websites from the active companies before their company is derived. The Website selector does not create websites. Use its Search more dialog to distinguish identical website names by the Domain column. Saved endpoint website/source identities remain immutable.

Version 2 chat uses native sale-order chatter and native Live Chat sessions. Order chat stays pending until the initial order event is acknowledged; later revisions do not disable it. The compatibility order-chat URL reads the native thread and retains checkout-session/capability protection. New customer comments are captured transactionally; notes, automated posts and bridge replies are excluded. Historical messages are not backfilled.

Configure Chat Enabled, Outgoing Enabled, the website’s Live Chat channel and the dedicated module-owned Callcenter Support user on its endpoint. Add that user to the configured Live Chat channel and ensure its allowed company matches the website. The bridge mode keeps native greeting/widget behavior and queues support messages even when no ecommerce employee is online. Login uses a separate authenticated identity and never merges guest history. Keep sending disabled until the compatible consumer/worker are deployed and acceptance tests pass. Legacy v1 reply submission is blocked; v1 order intake remains supported.

Local-server acceptance found two follow-up fixes: native `/mail/message/post` requests derive their website from the request host when the website-route attribute is absent, and queued acknowledgements use the native Live Chat session language. Reload the source Python process after upgrading this patch release.

Use storefront 19.0.1.0.1 or later with the operator-preservation fix: reloading default Live Chat data must retain the configured bridge operator. Native-comment, Arabic-acknowledgement and operator-preservation checks passed after the local reload.

Website recovery and verified identity are described in `docs/website-reliable-conversations.md` in the callcenter checkout. Version 3 producers require the receiver and gateway upgrade first; the endpoint lifecycle switch defaults to disabled. Pending sends retain their original UUID and destination. A website acknowledgement proves acceptance, never customer reading.


## Order replies and private media

Received order cards and website messages expose reply arrows. The selected message determines the destination on the server; its quote remains selected until send or cancellation. A stable submission UUID protects uncertain retries, including the original destination and attachment digests. Without a selection, the latest eligible incoming message is used.

The storefront tracking chatter has a Refresh button and five-second updates. Polling pauses in hidden tabs, prevents overlap, and appends messages by ID without clearing the composer, attachments or loaded history. The separate order-chat page also provides manual refresh.

Version 4 transfers up to four files, 20 MB each, through authenticated binary endpoints. Message envelopes contain stable attachment IDs, filename, MIME type, byte length, SHA-256 digest, media kind and available voice duration. Files remain private; internal notes are excluded. Existing v1 order/text, v2 chat and v3 lifecycle exchanges remain available.

Deploy both adapters and the gateway together, upgrade only the adapters, verify the v4 round trip, then enable **Enable v4 website media** on the intended storefront endpoint. The flag defaults to off. The gateway negotiates support and reports unsupported peers for review; it never acknowledges incoming media until all bytes and the message are stored in callcenter. Deployment, endpoint activation and user-managed service restarts are separate operations.

Order chats close permanently when the order reaches Out for Delivery, including completed warehouse dispatch and linked prescription dispatch. History remains readable; new customer messages, direct chatter posts, agent replies and uploads to that destination are rejected. Other order chats and floating sessions continue. Reversing status does not reopen chat. Previously accepted sends retain their acknowledgement.

Upgrade the callcenter receiver before enabling **Enable dispatch lifecycle after receiver upgrade** on the source endpoint. Keep the existing verified-lifecycle option enabled too. The new producer flag defaults to off; enable it before dispatching orders that must notify callcenter. It does not backfill earlier closures. Terminal lifecycle events wait until the destination's previously accepted messages have been acknowledged, including media, so closure cannot overtake delivery. Customer metadata uses the account partner's name and bounded phone; empty phone clears it and legacy omission remains accepted. Account UUIDs determine ownership.

## Optional checkout identity metadata

After upgrading the receiver, enable **Enable verified checkout identity after
receiver upgrade** on the intended endpoint. It defaults to off. New checkout
submissions capture account identity or an opaque identity derived from the
trusted browser checkout owner before asynchronous confirmation. The original
guest/account origin remains fixed; later verified login handoff can link the
conversation without changing that origin. Names and phone numbers do not
establish ownership. Existing submissions are not backfilled.


## Notification-only operation and offline order chatter

Version 19.0.1.5.2 keeps native portal order comments available without Callcenter acknowledgement, including when endpoint intake or chat forwarding is disabled. Existing order ownership, website/company isolation and dispatch closure still apply. Enabling notification intake does not authorize Callcenter to validate purchases, payments or stock operations.

Use Enabled for order notifications. Chat Enabled controls the optional chat bridge; Outgoing Enabled controls remote replies. Both can remain off for notifications only. Native comments saved while forwarding is off are retained in Odoo and are not backfilled to Callcenter. When forwarding is enabled, customer messages and uploads are stored locally before acknowledgement; transport withholds them and order lifecycle events until the initial order is captured.

Settings administrators can list endpoints in their selected companies even when another role implies Callcenter Exchange Service. Ordinary exchange users remain limited to their own endpoints. Upgrade the module to load this rule; uninstalling is unnecessary and can remove integration records.

If using the optional Live Chat bridge, select an active internal bridge operator in the endpoint company, different from the exchange user and without Settings administrator access. Add this user to the selected Live Chat channel's operators. The supplied user is Callcenter Support. A notification-only endpoint does not require a Live Chat channel.
