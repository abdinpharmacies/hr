# Channel services: deferred draft

Status: design draft only. No service split, storage migration, `queue_job`
installation, cutover or production deployment is authorized by this change.

The proposed services are `fastwhatsapp` (WhatsApp reception, media, delivery and
callbacks), `fastelegram` (Telegram reception/delivery), and `fastecommerce`
(website chat and order-event transport/replies). Share a transport library,
with separate configuration, scoped keys, SQLite stores, health and capacity
controls. Reuse only FastRAG's API-key/connector pattern.

Odoo remains the owner of canonical CRM/order history, approvals and business
jobs via a separately approved `queue_job` integration. Website Odoo owns
checkout, payments and orders. Gateways own protocols, local durable buffering,
idempotency and transport evidence. Future gateways have no PostgreSQL dependency
and do not fetch provider credentials from Odoo at startup.

The draft connection default is Odoo submitting approved deliveries with
service-specific keys, and each service pushing incoming/status events to scoped
Odoo APIs with separate credentials. Version the connection-check, submission,
status and reconciliation APIs. Buffer failed callbacks. Lock this interface
choice before implementation approval.

Acceptance means durable local storage. Keep accepted, delivered and read states
separate. Wake work promptly and bound concurrency across independent conversations
while preserving ordering, expiry, provider limits and uncertain-send review.

A later migration approval must cover one channel at a time, operator-controlled
legacy export outside the new runtimes, offsets, UUIDs, tokens and review evidence.
Never run competing receivers or replay completed sends. Current gateway
PostgreSQL/Odoo coupling, idle polling and failure backoff remain until that work.
