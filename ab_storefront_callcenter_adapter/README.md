# Storefront Callcenter Adapter

Install this companion on the ecommerce checkout. It depends on `ab_ecommerce_storefront` and leaves the storefront, customer API, login, payments and reservation implementations unchanged. Confirmed ordinary new orders produce durable snapshots in the confirmation transaction. Adapter-owned text chat uses authenticated ownership or originating-session ownership plus a hashed private guest capability.

Configure Callcenter Endpoints before enabling intake. Invoice lines include the readable source unit name as optional `unit_name`, alongside the original unit code. Callcenter displays the received values without product or unit mappings; agents enter invoices manually in POS. Use the gateway Website worker and `ab_crm_website` on callcenter. The full setup and rollout guide is `docs/website-callcenter-adapter.md` in the callcenter checkout. No live endpoint configuration or worker activation is included.

Snapshots carry the native storefront `ab_public_reference` as optional `public_reference`, separately from the internal `reference` number. Sales Chatter uses the public value in its Order Reference row.

New endpoints select existing websites from the active companies before their company is derived. The Website selector does not create websites. Use its Search more dialog to distinguish identical website names by the Domain column. Saved endpoint website/source identities remain immutable.
