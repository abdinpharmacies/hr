# Website orders in Sales Chatter

The adapter captures confirmed ordinary website orders and transports immutable evidence to Sales Chatter. Staff confirms the customer, reviews incoming invoice cards, and manually enters the invoice through the existing POS workflow. Website prices and payment evidence are displayed separately from local POS prices. The adapter never creates an invoice, takes payment, reserves stock, releases a website reservation, or transfers fulfillment responsibility.

## Addons and transport

- `ab_storefront_callcenter_adapter` is the ecommerce companion, with its release source under `companions/ecommerce/`. Its only ecommerce dependency is `ab_ecommerce_storefront`; the customer API is optional and unchanged.
- `ab_crm_website` extends Sales Chatter invoice display. It preserves the native POS action and pricing checks.
- `crm_messaging_gateway.app.website` runs durable Website delivery using the existing PostgreSQL or SQLite queues. HTTP workers remain separate.

Native `sale.order.action_confirm()` is the capture point, after `super()` succeeds. Checkout preparation, redirects, abandoned carts and failed payments are not capture points. Prescription orders and orders created before the endpoint cutoff are excluded. Capture and confirmation share one transaction. No network call is added to checkout. Historical events cannot be edited or deleted. Each event carries protocol version, source UUID, order UUID, event UUID, per-order revision and a canonical SHA-256 fingerprint. Source database IDs are never product or unit identifiers.

The destination requires consecutive revisions and rejects conflicting event IDs or revision reuse. Duplicate deliveries return the existing receipt. Source acknowledgements happen only after the destination HTTP request has committed. A restart after destination commit but before acknowledgement safely redelivers. Both the Odoo ledger and the gateway queue deduplicate retries. Chat posts and agent replies also have idempotency identities. All message bodies are rendered as text.

The local installation was configured and activated on 2026-11-12. See [local pilot status and recovery instructions](website-callcenter-local-pilot.md). The steps below remain the setup procedure for a new environment.

## Configure a disabled pilot

1. Install the ecommerce companion on ecommerce and `ab_crm_website` on callcenter. Do not install the legacy OMS adapter. Use targeted installs and the matching worktree/configuration.
2. Create a dedicated ecommerce internal service user with **Callcenter Exchange Service**, without Settings or Sales staff groups. Give it only its endpoint company and a revocable Odoo API key. In **Callcenter Endpoints**, select the website, service user and cutoff. Leave the endpoint disabled until ready. Its source UUID and website are immutable.
3. Configure a Website channel and messaging account on callcenter. Use the exact source UUID as **Provider Account**, the intended branch/company and a dedicated Messaging Service Account authorized for that branch. Do not give the service user staff or Settings groups. Confirm that the previous worker is disabled. Configure the branch's existing intake replica, default sales store and staff permissions.
4. Invoice lines carry the readable source unit name in optional `unit_name`, alongside the original `unit` value. Callcenter renders these received values directly; older snapshots keep their original unit value. No unit mapping or product lookup is used for invoice display or POS preparation. Website Orders is under CRM / OMS with existing manager access and read-only views. Website Unit Mappings navigation is inactive; its records, model and XML IDs are retained. Free and charged delivery remain invoice evidence.
5. Add the Website account to the gateway's existing private mode-0600 configuration. `token` is the ecommerce service API key; `odoo_key` is the callcenter service API key. Keep both keys outside source control. Example account shape, with placeholders:

```json
{
  "website-pilot": {
    "provider": "website",
    "provider_account": "SOURCE-UUID-FROM-ECOMMERCE",
    "website_url": "https://shop.example.com",
    "website_database": "ecommerce",
    "token": "ECOMMERCE-SERVICE-API-KEY",
    "odoo_key": "CALLCENTER-SERVICE-API-KEY",
    "reception": "disabled",
    "enabled": false,
    "sending_enabled": false
  }
}
```

The existing top-level `odoo_url`, `odoo_database`, `odoo_transport`, queue database and sending switch still apply. Use HTTPS for both origins; redirects and embedded credentials are rejected. The Website endpoints require HTTPS even when the generic gateway permits loopback HTTP for development. Configure Odoo's trusted reverse proxy correctly rather than weakening transport checks.

6. Replace the shared durable worker with the separate Website, Telegram and WhatsApp service templates as appropriate. Do not run an old unscoped worker alongside the scoped services. Start only one Telegram receiver per bot; the existing database/file receiver lock remains in effect. Extra Uvicorn workers do not partition durable queues. The Website worker is `python -m app.website`; other workers use `python -m app.worker --provider telegram` or `--provider whatsapp`.
7. Enable one endpoint/account and the required sending switches for a bounded new-order pilot. Confirm a real COD order and an online order reach Sales Chatter once, with unchanged website payment and reservation evidence. Review contact linking and invoice evidence before manually entering POS products. Do not treat prepaid evidence as permission to charge again.

Pilot credentials and runtime configuration are private and excluded from source. The configured local installation and verified test orders are recorded in [local pilot status](website-callcenter-local-pilot.md).

## Customer identity and chat

Website orders sharing the submitted phone appear in one staff Inbox conversation screen, with each order as a distinct incoming invoice card. The transport still retains a separate order UUID and browser authorization/reply destination for every source order. Grouping is scoped by company and branch, and does not verify identities or merge customer records. Phone matching supplies candidates; staff uses the existing confirmation flow to link a saved contact. The general contact/header POS navigation remains available; cards do not prepare orders. Another employee cannot take over a linked draft through a forged handoff request.

The confirmation and customer order pages link to adapter-owned text chat. Browser requests always go through ecommerce. Members must own the order through their commercial partner. Guests need the original checkout session ownership hash and a private order-scoped capability. Capability cookies are Secure, HttpOnly and SameSite=Strict, expire after 24 hours, and are stored only as hashes. Order UUIDs, public references, sale access tokens and phone numbers are insufficient. Chat polls every five seconds while the page is visible, with CSRF checks on all polling and submission requests. Reloading an owned page renews a guest capability; an expired capability cannot submit messages. Login and OTP behavior are unchanged.

Server operations are `/storefront-callcenter/v1/fetch`, `/acknowledge`, `/receive`, and `/crm/website/v1/receive`. They require dedicated bearer credentials and validate configured source/account/company/branch before elevated access. The normal Odoo JSON2 messaging endpoints continue to carry outgoing leases, receipts and delivery reports. Website chat supports text only. Provider delivery uncertainty remains a review case rather than an automatic blind resend.

## Review, monitoring and stopping

Sales managers can publish a fresh confirmed-order snapshot using **Send callcenter update** on a captured ecommerce order. This explicit action does not change native order states. Later snapshots update the adapter order card and set its progress to Review. They never overwrite a prepared POS draft or invoice. Existing draft contents and historical handoff links remain intact; the immutable event ledger retains earlier snapshots. Callcenter progress is separate metadata, with no writes to native ecommerce business states.

Monitor per-account incoming backlog age, attempts, review cases, outgoing receipt/report backlog and conflicting identities. Source events remain unacknowledged through destination outages; queue errors and reports do not log message bodies or credentials. A disabled source endpoint stops capture and exchange; stop or disable the Website worker/account as well to prevent processing previously captured local work. Disabling intake leaves existing website orders, payments and reservations intact. Fulfillment reconciliation and historical backfill are outside this adapter.

## Incoming invoices and manual POS entry

Website quotation events appear as incoming messages in Sales Chatter. Each card retains its immutable invoice, customer/address snapshot, product table, totals, payment method and View invoice / Hide invoice toggle. Earlier revisions retain their original values; multiple orders sharing the submitted phone remain in the same authorized customer screen.

Cards contain no Create order button. Agents use the existing general contact/header button to open POS, then enter products, quantities, units and delivery details manually. General contact details still use the established contact workflow. Website snapshots supply no POS product lines, delivery overrides or quotation payload, and no Website quotation panel is added to POS. Direct handoff API calls do not change Website handoff/progress metadata. Existing draft lines, invoices, snapshots and historical links are preserved.

Native portal chat integration and recovery of the two test messages remain suspended. This change requires only a targeted callcenter addon upgrade, its refreshed runtime archive, a user-controlled callcenter restart and browser refresh. Ecommerce checkout, payments, reservations, gateway delivery and authentication are unchanged; no ecommerce restart or database cleanup is required.

## Validation

Use the focused addon tests and `crm_messaging_gateway/tests/test_website.py`. Browser tests additionally need Chrome and `websocket-client`; skipped browser tests are not evidence of UI success. Run gateway tests with `PYTHONPATH=.` from its directory and `MESSAGING_TEST_DSN_FILE` pointing to a private DSN file for a dedicated PostgreSQL test database. The existing PostgreSQL fixture resets only its selected test queue database. SQLite tests use temporary files.

Use isolated Odoo databases, `--workers=0 --max-cron-threads=0`, alternate HTTP/gevent ports and `--stop-after-init`. Never upgrade runtime databases merely to validate, bind ports 4091/4092, or restart the user's services. Production addon archives exclude tests, fixtures, caches and development artifacts. Validation results are recorded in the task's completion report.


See [production connection and configuration](website-callcenter-production-setup.md) for the current pilot origins, credentials/scopes, gateway configuration, HTTPS and rollout procedure.

Branch Locations provides Import Branch Locations beside New for managers and system administrators without a row selection. The existing popup validates duplicates, ambiguous stores and preview consistency, and imports inactive profiles for review. Native import/export remains available. Its separate menu and Legacy Order Archive navigation are inactive; historical orders, lines, audits, security, actions and XML IDs remain intact. Retained archive views support direct XML developer-mode loading.
