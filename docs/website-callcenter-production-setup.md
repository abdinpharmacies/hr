# Website → Sales Chatter: connection and production setup

The website confirms the sale and records an immutable event in the same transaction. The gateway's Website worker fetches that event, commits it in callcenter, then acknowledges ecommerce. Checkout never waits for a network request. Staff sees orders sharing a submitted phone in one conversation screen, with a separate display-only incoming invoice card for each order. Browser chat remains authorized and routed per source order; grouping a phone does not verify a customer identity.

## Current local pilot

| Setting | Ecommerce | Callcenter |
| --- | --- | --- |
| HTTPS origin | `https://127.0.0.1:5443` | `https://127.0.0.2:5444` |
| Internal Odoo HTTP | `127.0.0.1:4102` | port `4092` |
| Odoo database | `e_commerce` | `callcenter` |
| Addon | `ab_storefront_callcenter_adapter` | `ab_crm_website` |
| Dedicated service login | `website_callcenter_exchange_service` | `website_callcenter_gateway_service` |

The account/channel code is `website-pilot`; its intake branch is `callcenter-intake` in company 1. The source UUID is `0185e375-29f9-427c-b6ba-91ce5138425b`. This UUID identifies the endpoint; it is not a password. The local cutoff is 2026-11-11 23:02:57 UTC. The cart's creation time, rather than the later confirmation time, determines cutoff eligibility.

The Website worker is the user service `crm-messaging-pilot-website.service`; HTTPS is `crm-website-pilot-https.service`. Website transport configuration is private at `/home/abdin_04/.config/crm-messaging/config-website-pilot.json`. Keys are stored only in private mode-0600 files; they are deliberately omitted from this document. The existing gateway uses its own PostgreSQL queue database. Telegram and WhatsApp have separate scoped workers. The previous shared worker is disabled.

These loopback origins and the pilot CA belong to this PC. They are not production addresses. Use new production credentials and the production endpoint's source UUID; do not copy private pilot files into a release archive.

## How two separate production servers communicate

The gateway may run beside callcenter or on a third private host. It initiates the server-exchange HTTPS requests to both Odoo origins. Ecommerce does not need a direct connection to callcenter's database, and callcenter does not need access to ecommerce's database. The gateway queue is a third logical database containing transport work; it is not either Odoo business database.

```mermaid
sequenceDiagram
    participant Customer
    participant Website as Ecommerce Odoo
    participant Worker as Website gateway worker
    participant Queue as Gateway queue
    participant Callcenter as Callcenter Odoo
    Customer->>Website: Confirm website checkout
    Website->>Website: Commit sale + snapshot + outgoing event
    Worker->>Website: HTTPS fetch with source service key
    Website-->>Worker: Pending versioned events
    Worker->>Queue: Persist events
    Worker->>Callcenter: HTTPS receive with callcenter service key
    Callcenter->>Callcenter: Commit order card + incoming message
    Callcenter-->>Worker: Committed event receipt
    Worker->>Website: HTTPS acknowledge UUID + fingerprint
    Worker->>Queue: Mark delivery done
```

For replies, the worker leases the selected order's staff reply from callcenter, sends it to ecommerce's receive endpoint, and reports the receipt to callcenter. The customer browser talks only to ecommerce. Staff-side phone grouping does not combine browser authorization or distribute a reply to every order sharing a phone.

| Initiator | Destination | Production port | Purpose |
| --- | --- | --- | --- |
| Customer browser | Website reverse proxy | TCP 443 | Checkout and order-owned chat |
| Staff browser | Callcenter reverse proxy | TCP 443 | Sales Chatter/POS and proxied Odoo WebSocket |
| Gateway worker | Both reverse proxies | TCP 443 | Fetch, receive, acknowledgement and staff-reply exchange |
| Reverse proxy | Its own Odoo upstream | Private configured HTTP/WebSocket ports | Forward application traffic |
| Gateway worker | Its queue database | Private configured database port, commonly PostgreSQL 5432 | Durable delivery/recovery |
| Each Odoo runtime | Its own PostgreSQL server | Private configured database port | Business data |

Public DNS names must resolve correctly from the gateway host, and TLS certificates must match those names. Keep direct Odoo/database ports private. The worker requires outbound HTTPS access and the Odoo reverse proxies must allow its requests. The worker itself needs no public Website webhook listener; its Website transport polls. An existing FastAPI HTTP gateway may serve other channels, but additional Uvicorn workers do not deliver or partition Website events.

There are two independent service API keys. The source key is accepted only by the ecommerce endpoint's configured service user/source/website/company scope. The destination key belongs to the callcenter account's configured service user/company/branch. Both are sent in Authorization Bearer headers, never in URL query strings or browser code. The worker sends X-Odoo-Database for the intended Odoo database. Provider Account must exactly equal the source UUID, and the gateway account dictionary key must exactly equal the callcenter messaging account code. UUIDs/account codes identify the integration; API keys authorize it.

## Required production services

1. Ecommerce Odoo with the companion addon and existing storefront dependencies.
2. Callcenter Odoo with `ab_crm_website`, `ab_crm_sales_workspace`, messaging, HR and the existing native POS dependencies.
3. The matching `crm_messaging_gateway` release, a dedicated durable queue database, and one supervised Website worker. Existing HTTP workers and channel receivers remain separate.
4. Certificate-verified HTTPS origins reachable from the worker, such as `https://shop.example.com` and `https://callcenter.example.com`.
5. A working callcenter branch/POS connection with authorized stores and a ready stock snapshot. A successful RPC connection test alone does not satisfy stock readiness.

Use the tested code baseline; the two addon ZIPs alone do not contain the gateway or the other custom dependencies. Stage and validate before enabling intake. Back up Odoo databases/filestores and the gateway queue before upgrading a deployed installation.

## Configure Odoo while intake is disabled

1. Install the ecommerce companion only on ecommerce and `ab_crm_website` only on callcenter. Use targeted installs/upgrades for these modules. Leave the legacy OMS adapter unused.
2. On ecommerce, create a dedicated internal service user with **Callcenter Exchange Service** and only the intended company. Do not grant employee/admin sales privileges. Generate a revocable API key with a bounded lifetime.
3. In **Callcenter Endpoints**, select the website, company, service user and a future activation cutoff. Keep the endpoint disabled. Copy its source UUID; its website/source identity is immutable.
4. On callcenter, create a separate internal **Messaging Service Account**, restricted to the intended company and intake branch. Generate a different API key. Create a Website channel and messaging account. Use an account code such as `website-production`, set **Provider Account** to the exact ecommerce source UUID, and assign the same service user, company and branch. Keep intake/sending disabled initially.
5. Configure the intake branch's active replica, default sales store, allowed stores, country and staff/employee POS profiles. Verify that staff can see that branch and create ordinary native POS drafts there.
6. Configure explicit **Website Unit Mappings** using shared E-Plus product serials and source unit codes. Set the corresponding **Callcenter Unit Code** on ecommerce units. Match the correct unit category/factor; never use local record IDs as cross-system product identifiers. Mappings provide readable unit labels only. Free and charged delivery remain in the invoice display; agents enter POS products and delivery details manually.
7. Verify ordinary website delivery carriers and intended payment providers independently. The adapter does not configure checkout pricing, delivery availability or payment settlement.

## HTTPS and reverse proxy

Terminate TLS at your trusted reverse proxy and enable `proxy_mode = True` in each Odoo configuration. Restrict direct access to the internal Odoo ports so arbitrary clients cannot spoof forwarded HTTPS headers. Preserve these proxy headers:

```nginx
proxy_set_header Host $host;
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_pass http://odoo_upstream;
```

Define separate upstreams and valid certificates for each origin. Configure native Odoo WebSocket routing for Sales Chatter as required by your Odoo deployment. The gateway must use the final HTTPS origins directly: redirects, embedded credentials and URLs containing paths/query strings are rejected. For a private CA, install the CA in the worker's trusted bundle or set `SSL_CERT_FILE` to an appropriate CA bundle. Never disable verification. Keep Authorization headers, credentials and request/message bodies out of access/debug logs.

## Authentication and API-key generation

The transport is **Odoo → durable gateway worker → Odoo**. Each HTTP leg uses the receiving Odoo server's native API-key Bearer authentication over HTTPS. The Website worker is a separate `python -m app.website` process in the gateway codebase; the FastAPI HTTP application does not authenticate these Website exchange calls. No OAuth/JWT issuer, shared administrator password or customer API token is involved.

The adapter controllers declare `auth='bearer'` and `save_session=False`, and additionally require an explicit Bearer header and HTTPS. Odoo validates the key, expiry and owner and sets the request user. Then the adapter checks the dedicated service role, configured service user, source/account identity, company and branch before scoped elevated access. The UUID/account code identifies the integration; it does not authorize access.

During the local pilot, two separate keys were generated through Odoo's `res.users.apikeys` model, as their respective dedicated service users, using scope `rpc`, description `Website callcenter pilot` and a 90-day expiration. The administrator-controlled setup used this native internal API:

```python
from datetime import timedelta
from odoo import fields

key = env['res.users.apikeys'].with_user(service_user).sudo()._generate(
    'rpc',
    'Website callcenter pilot',
    fields.Datetime.now() + timedelta(days=90),
)
```

This is an Odoo administrator-shell operation, not a public HTTP key-generation endpoint. It must target the intended service user, not the administrator. Administrative elevation was used only to permit the bounded lifetime; the resulting key authenticates as the service user. The `rpc` key scope itself does not encode website/company/branch restrictions: those come from that user's permissions and the adapter's explicit scope checks.

For production, prefer generating each key through the dedicated service account's Odoo account security/API-key interface under your administrator's approved lifetime policy. Odoo's UI normally creates a native general-purpose user key, which the Bearer handler accepts; the service user's minimal permissions and adapter checks still limit this integration. Keep the two service users and keys separate. Use the exact private-shell method above only as an authorized administrative setup procedure when necessary.

Odoo generates cryptographically random key bytes, returns the plaintext key once, and stores a hash plus a lookup prefix in its own database. The installed Odoo code uses 20 random bytes encoded as 40 hexadecimal characters. The gateway needs the actual secret, so its protected mode-0600 configuration contains the two plaintext service keys; do not confuse that file with hashed Odoo storage. Do not print keys in logs, store them in source control or send them to browsers. Restarting Odoo does not regenerate them.

Map the ecommerce key to the Website account's `token`; map the callcenter key to its `odoo_key` (and the required top-level key for a Website-only gateway configuration). Revoke expired/compromised keys through Odoo. For planned rotation, generate a replacement for the same service user, update the private worker configuration, restart that worker and verify exchange before revoking the old key.

Customer authentication is separate: members use ecommerce login/order ownership; guests require the originating checkout session and a private hashed order capability. Customers never receive either integration API key. Login/OTP remains unchanged.

## Gateway configuration

Create a Website-only private configuration owned by the service account, with file mode `0600` and a private parent directory. Replace every placeholder below; this is not a ready-to-run secret file.

```json
{
  "database_url": "postgresql://QUEUE_USER:QUEUE_PASSWORD@QUEUE_HOST/crm_messaging",
  "odoo_url": "https://callcenter.example.com",
  "odoo_database": "CALLCENTER_DB",
  "odoo_key": "CALLCENTER_SERVICE_API_KEY",
  "odoo_transport": "controller_v1",
  "sending_enabled": false,
  "allow_loopback_http": false,
  "accounts": {
    "website-production": {
      "provider": "website",
      "provider_account": "SOURCE_UUID_FROM_ECOMMERCE_ENDPOINT",
      "website_url": "https://shop.example.com",
      "website_database": "ECOMMERCE_DB",
      "token": "ECOMMERCE_SERVICE_API_KEY",
      "odoo_key": "CALLCENTER_SERVICE_API_KEY",
      "token_source": "config",
      "reception": "disabled",
      "enabled": false,
      "sending_enabled": false
    }
  }
}
```

The account key `website-production` must exactly match the callcenter messaging account code. `token` authenticates requests to ecommerce; `odoo_key` authenticates requests to callcenter. The top-level key is required by the current settings schema; a Website-only deployment can use the same dedicated callcenter key there and in its Website account. The queue must be separate from either Odoo database. Secure its connection and storage using your production database policy. SQLite remains supported on explicitly confirmed encrypted storage; there is no requirement to migrate an existing validated backend just for this adapter.

Set `CRM_MESSAGING_CONFIG` to this file for the Website worker. Validate the file without printing secrets:

```bash
CRM_MESSAGING_CONFIG=/etc/crm-messaging/website.json /srv/crm-messaging/venv/bin/python -c 'from app.config import settings; settings(load_provider_tokens=False); print("Configuration valid")'
```

Run this from the gateway directory or set its module path. Use the gateway's existing `python -m app.ops migrate` command once to initialize/migrate its queue schema after backup, under the same private configuration.

Adapt `crm_messaging_gateway/deploy/crm-messaging-callcenter-website-worker.service` to your production service user, working directory, virtualenv, configuration path and queue state directory. Its process is:

```bash
python -m app.website
```

Use service supervision, restart-on-failure and restrictive filesystem permissions. Do not run the old unscoped durable worker beside provider-scoped workers. Keep one Telegram receiver per bot. Additional Uvicorn processes do not partition the durable queues.

## Routes and direction

All server-exchange routes use POST, HTTPS, dedicated Bearer credentials and the configured Odoo database header. The native worker supplies these values; no customer API token is involved.

| Route | Destination | Purpose |
| --- | --- | --- |
| `/storefront-callcenter/v1/fetch` | Ecommerce | Fetch unacknowledged events for the configured source |
| `/crm/website/v1/receive` | Callcenter | Commit a validated event and its order/message |
| `/storefront-callcenter/v1/acknowledge` | Ecommerce | Acknowledge the committed event UUID/fingerprint |
| `/crm/messaging/v1/lease_outgoing` and receipt/report routes | Callcenter | Lease and report outgoing staff replies through the existing gateway |
| `/storefront-callcenter/v1/receive` | Ecommerce | Deliver an order-scoped agent reply |

The worker fetches roughly every two seconds. Polling customer pages uses ecommerce-owned routes and protected order/session ownership; server API keys never reach the browser. Requests are scoped before elevated access. Events carry source, order UUID, event UUID, revision and fingerprint. Retries deduplicate; conflicting reused identities fail. A destination commit followed by a lost acknowledgement can be retried safely.

## Activation and acceptance

1. Finish configuration and mappings with intake disabled. Restart the appropriate Odoo processes during your approved deployment window, then refresh frontend assets.
2. Set the intended cutoff and enable the ecommerce endpoint and callcenter account/channel. Enable the matching Website account in the worker configuration and start its supervised worker. Enable the callcenter account's outgoing switch, gateway top-level `sending_enabled`, and Website account `sending_enabled` only when staff replies should be delivered. Restart only the relevant gateway worker after changing its configuration.
3. Place a clearly labelled, authorized new COD test order through the website. Verify one capture event, one destination order/message and source acknowledgement. Two orders using the same submitted phone should appear as two incoming invoice cards in one customer screen. Phone matching must not silently verify or merge contacts.
4. Open each card and verify customer name, submitted phone, delivery address, product quantities/units, total and actual payment method. Confirm generated terms HTML is absent from the display. Payment status remains evidence, not permission to charge again. Older captured snapshots may lack an explicit payment method; use verified adapter display metadata for those records, and never infer COD from a generic custom provider or pending status.
5. Verify cards have no Create order button. Use the general contact/header POS button, then manually enter products, quantities, units and delivery details. Verify direct handoff calls contain no Website products/quotation and do not update Website handoff/progress metadata. Existing drafts and invoices must remain intact.
6. Verify normal POS permissions and branch stock readiness using the supported synchronization setup. Do not bypass guards or edit stock quantities. Website prefill and the POS quotation panel are removed.
7. Test staff/browser text replies, unauthorized order access, revoked credentials, a temporary gateway outage and duplicate retries. Confirm browser and customer-API checkout behavior remains unchanged.

Actual payment-processor settlement, branch stock reconciliation and physical fulfillment are separate from adapter transport. This integration automatically creates no invoice, charge, branch sale or new stock reservation. Native ecommerce payments/reservations remain unchanged.

## Monitoring, rotation and stopping exchange

Monitor oldest unacknowledged event age, queue backlog, retries/review cases, duplicate/conflict reports and worker health. Inspect sanitized service logs; do not enable raw body/credential logging. Protect and back up queue and Odoo data together according to your recovery policy.

For key rotation, issue a replacement for the same dedicated scoped service user, update the corresponding private worker key, restart that worker, verify exchange, then revoke the old key. If either key is compromised, revoke it immediately and investigate before restoring exchange. Do not reuse customer, staff or administrator credentials.

Disabling the ecommerce endpoint stops new capture; stopping the Website worker stops its exchanges while durable pending events remain available. Disable intake and outgoing switches on both sides for a full pause. Disabling only the gateway's `sending_enabled` does not stop incoming fetch. Leave WhatsApp/Telegram workers alone. Do not delete orders, events or reservations to clear a backlog, and do not reset UUIDs or replay historical orders blindly. Re-enable the same identities for safe retries after resolving the cause.

The native portal chat integration and recovery of the two test messages remain suspended. For the manual-invoicing change, upgrade only `ab_crm_website`, rebuild its callcenter runtime archive, then request the user-controlled callcenter restart and browser refresh. No ecommerce restart or database cleanup is required.
