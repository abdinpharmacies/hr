# Local Website Callcenter pilot

Current behavior (2026-11-15): Website invoice cards are display only. Agents create invoices manually through the general contact/header POS workflow. Website prefill, per-card Create order and the POS quotation panel are removed. Earlier prefill/handoff validation below is historical and superseded. Existing drafts, invoices, snapshots and handoff metadata remain intact. Native portal chat integration and recovery of the two test messages remain suspended. No ecommerce restart or database cleanup is required.


Activated on **2026-11-12 at 01:02:57 Africa/Cairo** (2026-11-11 23:02:57 UTC).

Verified after the administrator helper and user-controlled PyCharm restarts:

- Authenticated, certificate-verified ecommerce fetch returns HTTP 200.
- Callcenter scoped HTTPS API check succeeds.
- Website, Telegram and WhatsApp user workers are active independently; the old shared system worker is inactive and disabled.
- All three callcenter accounts retain enabled intake and sending; the ecommerce endpoint is enabled.
- No worker warnings appeared in the activation check. Two explicitly authorized COD test orders were subsequently delivered on 2026-11-13, as recorded below.
- Temporary validation ports 5069/5072 and 5075/5076 were released.

Use the HTTPS origins below and newly created carts. Orders/carts created before the activation cutoff remain excluded. COD collection and physical fulfillment have not been tested.

The installed adapters are configured for the existing `callcenter-intake` branch and its current intake store. The legacy OMS adapter is installed on ecommerce but disabled, with no managed orders. It remains unused.

The view errors came from compact view architecture fields in the new addons. Odoo 19 XML developer mode expects leading text when reading architecture from source files. Both view files are now formatted and have regression coverage for the exact reader that failed. Live ORM checks successfully rendered all eight affected views. No Odoo core files or native storefront/customer API sources were changed.

Prepared configuration:

- Ecommerce: dedicated `website_callcenter_exchange_service`, enabled Callcenter Endpoint, default source unit code `eplus_default`.
- Callcenter: dedicated `website_callcenter_gateway_service`, Website channel/account `website-pilot`, existing branch/company and intake-store permissions.
- Explicit mappings: 31,233 unique shared E-Plus serials whose existing default-unit names and factors match exactly. Eighteen missing target products and two unit mismatches remain unmapped for review. No product, price or stock data was edited.
- API keys are revocable and valid for 90 days. They are stored only in mode-0600 configuration files under the existing private messaging configuration directory.
- Local TLS proxy: `https://127.0.0.1:5443` for ecommerce, `https://127.0.0.2:5444` for callcenter. Separate IPs avoid sharing Odoo session cookies between databases. The proxy is loopback-only and user-managed; the unrelated global nginx service was not changed.
- Both Odoo configs specify `proxy_mode = True`, with private backups created before editing. The user completed the required PyCharm restarts, including the subsequent delivery-line fix.
- Separate user-managed Website, Telegram and WhatsApp worker units/configurations are prepared. They refuse to start while the old root-managed shared worker is active. The Telegram receiver and FastAPI HTTP service remain separate and unchanged.
- The gateway database was backed up with its existing backup command. Its existing idempotent schema setup added the missing `read_receipt` table.

## Administrator setup procedure (completed)

Run this reviewed helper from your own terminal, entering your sudo password locally:

```bash
bash /home/abdin_04/.config/crm-messaging/website-pilot/finish-admin-setup.sh
```

The helper installs trust for the pilot CA, pauses existing outgoing messaging, waits for in-flight sends to drain, disables/stops only the shared durable messaging worker, starts the scoped Telegram and WhatsApp workers, then restores the previous sending flags. On failure it attempts to restore the old worker and sending flags. It never restarts Odoo and does not send test messages to customers.

The helper and both PyCharm restarts were completed by the user. Codex then verified HTTPS and enabled the Website pilot. The procedure is retained here for recovery/reference; do not rerun it during normal operation.

If the browser still reports an untrusted local certificate after system trust is installed, import `/home/abdin_04/.config/crm-messaging/website-pilot/tls/ca.crt` through the browser's certificate manager. Do not disable certificate verification.

Useful status commands:

```bash
systemctl --user status crm-website-pilot-https.service
systemctl --user status crm-messaging-pilot-telegram.service crm-messaging-pilot-whatsapp.service crm-messaging-pilot-website.service
systemctl status crm-messaging-callcenter-worker.service
```

The original user-managed Odoo ports remain intact. No historical orders are backfilled. Only the two authorized test orders below were confirmed; no online charges were made. Actual online settlement remains unverified.


## Checkout repair and two-order channel test — 2026-11-13

The shipping error was a configuration failure: all five delivery carriers were archived. All payment providers were also disabled. Restored only the existing Standard delivery (`delivery.free_delivery_carrier`), preserving its zero fixed price and COD eligibility, and enabled the existing native COD provider (`delivery.payment_provider_cod`) and payment method. Online providers remain disabled. Previous settings are saved privately in `website-pilot/checkout-settings-before-test.json`.

The adapter now records `is_delivery` in the immutable quotation. POS preparation omits zero-value delivery lines from product mapping while retaining them in the quotation. Nonzero delivery charges require agent review. Both runtimes were restarted by the user to load this fix.

Two new guest carts were associated with the existing Emad Abdeen customer through authorized backend preparation. Cart addition, checkout, COD transaction creation, payment post-processing and confirmation used the actual HTTPS website routes. No login/OTP configuration was changed. The COD transaction request was repeated for each order and returned the same transaction reference.

| Website reference | Contents | Total | Sales Chatter conversation | Delivery result |
| --- | --- | --- | --- | --- |
| S00158 | 1 × FAMILIA POCKET 10 TISSUES 1 BOX | EGP 2.50 | 8 | One card, one event, source acknowledged |
| S00159 | 1 × FAMILIA POCKET 10 TISSUES 1 BOX | EGP 2.50 | 9 | One card, one event, source acknowledged |

The real supervised Website worker transported both events; no destination events were injected manually. Source/destination snapshots match exactly, including delivery address, notes, quoted totals and payment evidence. Both orders share the normalized customer phone but retain separate conversations. Live mapping checks returned exactly one mapped tissue product per order, with free delivery retained in the quotation.

Both orders are confirmed with native stock pickings in `assigned` state. Each has one pending, unpaid COD transaction. Neither has an automatic POS handoff. Both are labelled **TEST WEBSITE CALLCENTER CHANNEL — DO NOT FULFILL OR INVOICE** and remain available for inspection. A preliminary draft, S00157, lost its stateless test-client session and was cancelled through Odoo before submission; it generated no adapter event. The test client now uses ordinary cookie-based sessions instead of the stateless `X-Odoo-Database` header.

Verification evidence: `/tmp/website-two-orders-verification.json`, `/tmp/website-live-mapping.log`. Website, Telegram and WhatsApp workers and the TLS proxy were active after verification; the old shared worker remained inactive.


## Incoming order button — 2026-11-13

The website quotation is now rendered inside its incoming Sales Chatter message. **Create order** uses the existing contact-to-POS handoff to fill the linked draft with mapped product quantities/units and delivery details, retaining native POS pricing permissions and manual invoicing. Existing captured orders acquire this presentation after the callcenter Python restart and a browser hard-refresh; their immutable event snapshots are not rewritten. The targeted addon upgrade has been applied. The user-controlled callcenter restart remains pending.


## Clarified order chat layout — 2026-11-13

Every Website order now has a distinct visible Inbox chat, identified by submitted phone and order reference. Matching phones or reviewed contacts do not collapse these order chats. Each timeline retains its own immutable incoming quotation, text messages and Create order handoff. The earlier phone-grouped layout is superseded.

Twelve focused adapter/security/POS/browser tests passed, followed by a passing focused check of titles after contact linking. The targeted live addon upgrade succeeded. Existing Website chat grouping keys were recomputed through Odoo ORM, without rewriting orders/messages or sending events again. A user-controlled callcenter restart and browser hard-refresh are required to load the Python display/scope changes. The separately diagnosed branch stock-readiness and product-prefill retry issues are not changed by this layout update.


## Final customer-screen clarification and invoice display — 2026-11-13

The latest instruction supersedes the separate-visible-chat layout above. Same-phone Website orders now share one staff conversation screen containing all their incoming order cards and text messages. Each source order retains its own backend conversation, browser authorization and reply destination. Each card selects its own source order before Create order starts/reopens its POS handoff. Grouped search, pagination and read acknowledgement are validated; unrelated-phone records remain excluded.

The simplified incoming card uses a centered Website Order heading, collapsed View invoice / Hide invoice toggle, labelled customer name/phone/address, preserved human notes without the generated terms paragraph, a contained product table and verified payment method text. Technical transaction status remains in immutable evidence and the existing POS comparison panel rather than the simple incoming card.

Fifteen distinct focused tests passed: thirteen callcenter and two ecommerce. The targeted live callcenter addon upgrade succeeded. Four existing payment methods were verified against matching ecommerce transaction references/amounts/currency and stored as protected display metadata. Existing grouping keys were recomputed through ORM; no original messages, snapshots, prices or stock were rewritten. Source companion code and runtime archives were updated. User-controlled PyCharm restarts of callcenter and ecommerce, then a browser hard-refresh, remain required to load the Python changes.

Production connection and deployment instructions: [website-callcenter-production-setup.md](website-callcenter-production-setup.md). The separately diagnosed POS branch-stock readiness and failed-product-prefill retry issues remain outside this presentation update and are called out as production acceptance gates.


## Post-restart verification — 2026-11-13

The user completed both PyCharm restarts. New ecommerce/callcenter runtime PIDs were confirmed. Certificate-verified authenticated source fetch returned HTTP 200 with zero unacknowledged events; the callcenter HTTPS origin returned HTTP 200. The TLS proxy and Website, Telegram and WhatsApp workers were active. This completes the pending runtime restart step above; it does not resolve the separately recorded POS stock-readiness/retry defects.
