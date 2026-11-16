# Website adapter validation — 2026-11-11

Current behavior (2026-11-15): Website invoice cards are display only. Agents create invoices manually through the general contact/header POS workflow. Website prefill, per-card Create order and the POS quotation panel are removed. Earlier prefill/handoff validation below is historical and superseded. Existing drafts, invoices, snapshots and handoff metadata remain intact. Native portal chat integration and recovery of the two test messages remain suspended. No ecommerce restart or database cleanup is required.


Implementation is ready for a configured pilot. No live endpoint, credential, worker or runtime database was changed.

| Check | Result | Evidence |
| --- | --- | --- |
| Callcenter fresh install | Passed, 44-module dependency graph | `/tmp/callcenter-website-install.log` |
| Ecommerce fresh install | Passed after activating the existing `ab_website` Arabic prerequisite | `/tmp/storefront-website-install2.log` |
| Callcenter business and direct ORM access | 6 passed | `/tmp/callcenter-website-business-release.log` |
| Bearer authentication, account scope, duplicate receipt and revoked API key | 1 passed | `/tmp/callcenter-website-http-final3.log` |
| Chrome: native POS, Arabic labels, local prices, repeat prefill and switching drafts/stores during prefill | 2 passed, no browser skips in the final run | `/tmp/callcenter-website-browser-final.log` |
| Ecommerce browser/API COD, disabled intake, cutoff, rollback, failed/online payment, capabilities, reply/message deduplication, manager revisions and language rendering | 11 passed | `/tmp/storefront-website-release-tests.log` |
| Prescription exclusion | 1 passed | `/tmp/storefront-website-prescription-test.log` |
| Service privilege metadata and exchange access | Passed | `/tmp/storefront-website-security-final.log` |
| Gateway regression suite, including PostgreSQL/SQLite isolation, restart after destination commit and Website replies | 271 passed | Full `pytest -q tests` run, dedicated test queue DSN |
| Arabic catalogs | Both catalogs in each addon cover exported terms and pass `msgfmt --check-format` | `ab_crm_website/i18n/{ar,ar_001}.po`, `ab_storefront_callcenter_adapter/i18n/{ar,ar_001}.po` |
| Python/XML/manifests and working diff | Parsed successfully; `git diff --check` passed | Source validation |

Distinct focused Odoo tests: 9 callcenter and 12 ecommerce. Setup/teardown counts printed by `odoo.tests.stats` are not counted as business tests. Earlier failed fixture iterations and an initial browser run skipped for a missing optional websocket dependency are superseded by the successful final runs above. The final browser run used the existing temporary websocket dependency under `/tmp/sales-chatter-test-deps` and Chrome; runtime Python dependencies were not changed.

Isolated databases:

- `callcenter_website_adapter_test_20261111`
- `storefront_website_adapter_test_20261111`
- `crm_website_queue_test_20261111`

Odoo validation used the matching callcenter/ecommerce addons paths and a private neutral test configuration, `--workers=0 --max-cron-threads=0 --stop-after-init`, HTTP/gevent ports 5069/5072 or 5075/5076, and `--no-http` except for browser/authentication tests. Temporary test servers exited after testing. Ports 4091 and 4092 and the user's Odoo processes were not touched.

The online-payment fixture executes native payment-to-sale post-processing with only the native accounting payment creation boundary mocked because the fresh test company has no accounting journal configuration. It verifies that the existing accounting boundary is called once and that the confirmed snapshot contains done-payment evidence. Actual processor settlement and physical fulfillment reconciliation remain unverified. Subsequent local pilot transport and COD validation are recorded below.

The existing storefront, customer API and legacy OMS adapter sources were not edited. The ecommerce companion is mirrored under `companions/ecommerce/` in the callcenter checkout for reproducibility and supplied in the ecommerce worktree as a new addon. Production addon ZIPs exclude tests, caches, fixtures and development migrations. Gateway source changes require the current messaging addon baseline already present in this worktree; no unrelated in-progress changes were discarded.


## Delivery lines and local COD pilot — 2026-11-13

Focused delivery-line checks passed: 9 callcenter adapter tests (`/tmp/website-delivery-line-tests.log`), 3 ecommerce capture tests (`/tmp/website-delivery-source-tests.log`) and the full POS handoff test with a free delivery line (`/tmp/website-free-delivery-pos-test.log`). Both changed Arabic catalogs passed format checks. Free delivery stays in the quotation without becoming a POS product; nonzero delivery requires review.

After user-controlled runtime restarts, native HTTPS website checkouts confirmed S00158 and S00159 for the authorized existing customer. Each totals EGP 2.50 for one tissue pack plus free delivery. Each repeated transaction submission reused its single pending COD transaction. The real Website worker delivered one event and conversation per order, with exact snapshot equality and source acknowledgement. Live product/unit mapping returned one mapped product line for each. No automatic POS handoff was created. Native pickings remain assigned; COD collection, invoicing and fulfillment were not executed. See [pilot record](website-callcenter-local-pilot.md) for retained test labels and the cancelled preliminary draft.


## Incoming message Create order — 2026-11-13

Moved the website quotation from above the conversation into the corresponding incoming order message. The per-message payload comes from the immutable event ledger, scoped by account, order UUID and provider message reference; ordinary chat/replies do not acquire an order card. The card's Create order button calls the existing conversation/contact handoff, avoiding the location-only message handoff path. POS prefill and linked-draft reuse remain unchanged.

Validation uses `callcenter_website_adapter_test_20261111`, HTTP/gevent ports 5069/5072, with no user-managed process restart. Evidence: `/tmp/website-incoming-order-tests.log` and `/tmp/website-incoming-order-final-tests.log`. The initial run passed eight adapter/security tests and three browser tests; its POS test exposed a test assertion that assumed the outgoing reply was the last item in the timestamp-sorted timeline. The assertion now selects the reply by content; the focused final run verifies the full handoff and Arabic button translation.


Final results: **12 distinct tests passed** across the two runs: eight adapter/security tests, the full POS handoff test, and three browser tests. The focused rerun passed both changed tests with zero failures/errors. Browser coverage includes the actual incoming-card button invoking the contact/conversation handoff and opening the linked POS action, local-price preservation, idempotent product prefill, interrupted navigation and Arabic labels. Both Arabic catalogs pass `msgfmt --check-format` and changed Python/XML parse successfully.

The live targeted `ab_crm_website` upgrade completed without errors (`/tmp/website-incoming-order-live-upgrade.log`), and the runtime addon archive was refreshed. No user-managed process was stopped. A user-controlled callcenter restart is required to load the changed Python message serialization; frontend clients must then hard-refresh. No customer order or invoice was created during this change.


## Separate visible chat per order — 2026-11-13

The clarified user requirement is one visible new chat for each submitted order, identified by the submitted phone. Website Inbox keys now use the order UUID even when the phone or confirmed contact is shared. Website timelines expose only their own order stream; attempted cross-order channel switching is rejected. Chat titles include the submitted phone and order reference for both reviewed and unreviewed contacts. Incoming quotation cards and Create order remain unchanged.

Twelve focused tests passed on the isolated callcenter database, including same-phone separate Inbox entries, contact review, unrelated-phone exclusion, direct cross-order rejection, POS handoff behavior and three browser/Arabic checks (`/tmp/website-separate-chats-tests.log`). A final focused check covers the title after contact linking (`/tmp/website-separate-chats-title-test.log`). The interim grouped-order-list approach was stopped when the user clarified the requirement and was not deployed.


The final title check passed (one test, zero failures/errors). Targeted live upgrade completed without errors (`/tmp/website-separate-chats-live-upgrade.log`). Existing Website Inbox keys were recomputed using the supported ORM compute queue (`/tmp/website-separate-chats-existing.log`), keeping immutable snapshots and message history unchanged. Runtime packaging was refreshed. User-managed Odoo processes were not stopped.


## Customer conversation and simple invoice card — 2026-11-13

The later user clarification supersedes separate visible order chats: all authorized Website messages for the same submitted phone now appear in one staff screen. Individual source order UUIDs, browser authorization, chat reply destinations and POS handoffs remain separate. Read acknowledgement, search and pagination operate over the authorized company/branch/phone group; unrelated-phone targets are rejected. Each incoming invoice card selects its own order before Create order opens POS.

The card now centers Website Order, starts collapsed, toggles View invoice / Hide invoice, labels customer/phone/address, removes generated terms from display while preserving customer notes, uses a contained responsive product table, and displays the actual payment method. Immutable snapshots remain unchanged. Older COD methods are enriched only from matching source transaction evidence in protected adapter metadata; generic custom/pending evidence is never guessed to be COD. New source captures include the native method/custom mode.

Thirteen distinct callcenter tests passed across the initial and focused corrected runs, including group pagination across more than fifty messages, grouped read state, unrelated-phone rejection, per-card handoff routing, English/Arabic labels and a 320px Arabic layout. Evidence: `/tmp/website-customer-invoice-tests.log`, `/tmp/website-customer-invoice-final.log`, `/tmp/website-customer-invoice-layout-final.log`, `/tmp/website-customer-invoice-arabic-final.log`. The early Arabic failures exposed missing exported PO metadata and a Sass min() unit incompatibility; both are superseded by the passing final layout run. Two ecommerce tests passed for browser COD method capture and customer-API confirmation (`/tmp/website-payment-method-source-tests.log`). No runtime customer orders were submitted by these tests.

## Manual POS invoicing — 2026-11-15

Removed the incoming-card Create order button, Website workspace/POS action overrides, product-mapping draft preparation and the POS quotation panel. Invoice cards retain their customer details, toggle, product table, payment method and grouped customer conversation. Unit mappings still support readable invoice units. Direct handoff calls use the general contact workflow and return no Website lines/quotation or Website delivery-address override; they do not update Website handoff/progress metadata. Historical links and saved draft contents are retained.

Validation used the existing isolated `callcenter_website_adapter_test_20261111` database, `/tmp/website-adapter-test.conf`, the mapped callcenter addons path, HTTP/gevent ports 5069/5072, workers=0, cron=0 and stop-after-init. Browser support used the existing `/tmp/sales-chatter-test-deps` websocket-client package and headless Chrome. Only `ab_crm_website` was upgraded for test runs.

**16 distinct focused tests passed:** nine adapter/security/presentation tests, four POS API/security/draft/grouping tests and three browser tests. Evidence:

- `/tmp/website-manual-invoicing-final-tests.log`: 12 passing tests; the additional manual-entry browser test initially failed because its fixture omitted native `persistCache`.
- `/tmp/website-manual-invoicing-corrected-tests.log`: corrected manual-entry/contact-navigation browser test passed, zero failures/errors.
- `/tmp/website-manual-invoicing-security-tests.log`: four POS tests passed, zero failures/errors. Explicit wrappers ensure Odoo collects the reused general handoff security checks; inherited test methods are not collected automatically.

The final browser results have no skips. Coverage includes English/Arabic invoice toggles and payment labels, 320px Arabic layout, absence of per-card buttons/POS quotation, the general workspace/POS action registrations, contact-to-POS navigation and manual native product entry. Both unchanged Arabic catalogs passed `msgfmt --check-format`; Python/XML parsing, manifest/data paths, removed asset checks and diff whitespace checks passed. No new source UI strings were introduced.

The targeted runtime `ab_crm_website` upgrade on `callcenter` completed with exit 0 and no errors, using no HTTP, workers=0, cron=0, stop-after-init and alternate port arguments. Log: `/tmp/website-manual-invoicing-live-upgrade.log`. Existing unrelated manifest/API/schema warnings remain; the draft-cache not-null warnings also appear in the prior 2026-11-13 upgrade log.

Read-only before/after row fingerprints matched every existing record in all six protected tables: **44 invoices, 66 invoice lines, 26 draft caches, five Website orders, five immutable Website events and 15 handoffs**. Private fingerprint evidence: `/tmp/website-manual-integrity-before.json`. No business-record cleanup or draft-line removal occurred.

Rebuilt `/tmp/website-adapter-release/ab_crm_website-19.0.1.0.0.zip` with matching `.zip.sha256`. Archive verification checks exact packaged-source equality, required manifest files and exclusion of tests, caches, demos and migrations; removed Website JS extensions are absent. The ecommerce companion archive was not rebuilt.

The user-managed callcenter PID remained running on 4092; temporary ports 5069/5072 were released. A user-controlled callcenter restart and browser hard-refresh remain required to load the Python removal in the active process and refresh assets. No ecommerce restart is required. Checkout, payments, reservations, gateway delivery and authentication were unchanged. Native portal chat integration and recovery of the two test messages remain suspended.

## Invoice references and CRM / OMS navigation — 2026-11-15

Implemented optional source `unit_name` in the ecommerce snapshot and both addon validators. Invoice cards render `unit_name` with the unchanged received `unit` as fallback, without querying mappings or products or rewriting snapshots. Website Orders is under CRM / OMS; mapping, standalone branch import and legacy archive menus are inactive. Branch Locations has a manager/admin import button beside New, with no selection required. The existing wizard, native import/export, review safeguards, historical records, security, actions and XML IDs remain intact. Retained archive views load directly in XML developer mode.

Validation:

- **26 callcenter tests passed, zero failures/errors** on `callcenter_website_adapter_test_20261111`, upgrading only `ab_crm_sales_workspace,ab_crm_website`. Includes old/new unit payloads, invalid optional values, no mapping/product queries, exact stored evidence, delivery/deduplication, bearer authentication/revocation, branch/company access, unauthorized wizard methods, CSV duplicate/ambiguous-store safeguards, retained archive security and source loading, customer conversation grouping, manual POS handoff, English/Arabic invoice cards and the import popup without selection. Browser tests include the Arabic narrow-layout check. Log: `/tmp/invoice-navigation-callcenter-final.log`.
- **Four ecommerce tests passed, zero failures/errors** on `storefront_website_adapter_test_20261111`, upgrading only `ab_storefront_callcenter_adapter` from this checkout's companion root before the ecommerce addon root. Covers captured readable units, native COD confirmation/reservation behavior, exchange access/deduplication/acknowledgement and delivery evidence. Log: `/tmp/invoice-navigation-ecommerce-tests.log`.
- Both suites used `/tmp/website-adapter-test.conf`, workers=0, cron=0 and stop-after-init; callcenter used HTTP/gevent 5069/5072 and proxy mode for its existing HTTPS-only bearer test. Ecommerce used 5075/5076 with no HTTP. Optional browser websocket support came from the existing `/tmp/sales-chatter-test-deps`. No environment dependencies were installed.
- Initial callcenter failures were test-fixture issues (required wizard file and equivalent false view attributes) and missing test-server proxy mode. The final complete run above supersedes them; endpoint transport checks were unchanged.
- Python AST/XML parsing, `git diff --check` and gettext format checks passed for all six Arabic catalogs. The existing Import Branch Locations translation now also references its list header button. English/Arabic toolbar labels and popup opening were checked in the browser.

Rollout:

1. Upgraded the compatible callcenter consumer first: `ab_crm_sales_workspace,ab_crm_website` on `callcenter`, using its mapped config/addons paths, stop-after-init, no HTTP, workers=0, cron=0 and ports 5069/5072. Log: `/tmp/invoice-navigation-callcenter-upgrade.log`.
2. Mirrored only changed companion files to `/opt/odoo19/worktrees/e_commerce/ab_storefront_callcenter_adapter`, then upgraded only that producer on `e_commerce` using its runtime config and the same temporary port safeguards. Log: `/tmp/invoice-navigation-ecommerce-upgrade.log`. Companion and runtime source match, excluding generated caches.
3. Verified identical before/after row counts and SHA256 hashes for 16 business tables: legacy orders/lines/audits, Website orders/events/mappings, branch locations, POS handoffs/headers/draft caches, ecommerce sale orders/lines/payment transactions/stock pickings/stock moves and captured adapter events. The archive remains **10 orders, three lines, 21 audit entries**. All six Website snapshots/events and all 31,233 mapping records are unchanged. Evidence: `/tmp/invoice-navigation-records-before.json` and `/tmp/invoice-navigation-records-after.json` (hashes/counts only).
4. Rebuilt and verified runtime ZIPs plus SHA256 files under `/tmp/website-adapter-release`: `ab_crm_website-19.0.1.0.0.zip`, `ab_crm_sales_workspace-19.0.1.30.0.zip`, and `ab_storefront_callcenter_adapter-19.0.1.0.0.zip`. Packages exclude tests, fixtures, demos, migrations and caches. The Sales Chatter packaged manifest also omits its development-only unit-test asset bundle; other packaged source bytes match the checkout. Reproducible helper: `/tmp/package_invoice_navigation.py`.

Upgrade logs contain no ERROR/CRITICAL entries. Existing unrelated schema/model warnings remain outside this change (callcenter draft-cache missing not-null constraints and ecommerce queue-monitor model notices). The user-managed callcenter/ecommerce PIDs remained 3712610/3712657 on 4092/4102. Temporary ports 5069/5072/5075/5076 were released. User-controlled **callcenter restart first, ecommerce restart second, then browser hard-refresh** remain required; the running processes were not restarted. Gateway source, checkout, payment, reservation and authentication implementations were unchanged. Portal chat integration and test-message recovery remain suspended.

### Hide invoice units in Sales Chatter — 2026-11-15

The invoice product table now shows exactly Product, Quantity, Price, Discount and Total. Only the Sales Chatter presentation changed; received unit values remain in snapshots and the ecommerce producer is unchanged. Updated existing English/Arabic browser assertions to verify five aligned columns and no displayed unit, including the narrow Arabic layout. Both focused browser tests passed, with zero failures/errors, on `callcenter_website_adapter_test_20261111` using HTTP/gevent 5069/5072 (`/tmp/invoice-hide-unit-tests.log`). XML column assertions, both Arabic gettext format checks and `git diff --check` passed. Existing translation entries were preserved; no new UI strings were introduced.

Applied the targeted `ab_crm_website` upgrade on `callcenter` with no HTTP, stop-after-init, workers=0 and cron=0 (`/tmp/invoice-hide-unit-upgrade.log`). Rebuilt and verified the Website runtime ZIP and SHA256 under `/tmp/website-adapter-release`. Browser hard-refresh is required for the updated template. No user-managed process restart or ecommerce update is needed for this presentation change.

### Delivery address order and invoice reference — 2026-11-15

Incoming Sales Chatter invoice cards display Delivery Address as `Governorate | detailed address` on one line, followed immediately by an Order Reference row. Recognized Egyptian snapshots use the governorate code from the received formatted address and the native country/state reference records; the street, city and postal details are retained. Unknown formats retain all received address text on one line. Long addresses scroll within their field, preserving the narrow Arabic layout. The template falls back to the received address if the display field is not available during runtime reload. Both Arabic catalogs translate Order Reference as `مرجع الطلب`. No source payload, producer, contact/POS address or stored invoice snapshot was changed.

Validation covered 22 distinct Website tests. The initial suite passed 21 and exposed one browser fixture missing the real Sales Chatter wrapper required for scoped styles (`/tmp/invoice-address-tests.log`). After correcting that fixture, the focused English card test passed with zero failures/errors (`/tmp/invoice-address-browser-final.log`); the Arabic layout/reference translation check and backend formatting/immutable-evidence/security checks passed in the original run. Changed Python/XML syntax, both Arabic gettext format checks and `git diff --check` passed.

The targeted `ab_crm_website` upgrade on `callcenter` succeeded (`/tmp/invoice-address-upgrade.log`) with stop-after-init, no HTTP, workers=0, cron=0 and temporary ports 5069/5072. A read-only ORM check verified all six existing invoice snapshots display the requested separator/order in both language contexts without changes (`/tmp/invoice-address-runtime-check.log`). Before/after SHA256/count comparisons for the same 16 business tables were identical (`/tmp/invoice-address-records-before.json`, `/tmp/invoice-address-records-after.json`). The Website runtime ZIP and checksum were rebuilt and verified under `/tmp/website-adapter-release`. Temporary ports were released. The user-managed process was not restarted; a **callcenter restart and browser hard-refresh** are required for the new Python display formatter. No ecommerce restart is needed.

### Correct Order Reference to the native storefront tracking reference — 2026-11-15

The row below Delivery Address now uses native `sale.order.ab_public_reference` (for example `NO-151126-E4CRGK`) rather than the internal `sale.order.name`. The internal number remains the invoice heading and the existing `reference` payload value. The ecommerce companion emits optional `public_reference`; both validators accept old payloads and validate the optional string. The consumer stores this in readonly, immutable Website order metadata and exposes it on invoice cards, including historical revision cards. Missing public references show a dash instead of substituting an internal invoice number. No new UI text was introduced; both Arabic catalogs include the existing Order Reference translation for the new metadata field.

Six existing received orders were matched to the read-only ecommerce source by configured endpoint/source UUID, order UUID and exact internal reference. A bounded administrative ORM update validated the caller and each record's account/company/branch before scoped elevation, then populated only the new public-reference metadata. All six stored invoice snapshots and all original gateway/source event envelopes were preserved. Exactly one matched the user's example. No migration, hook, source-database write, event replay or new invoice was introduced. Evidence: `/tmp/public-reference-metadata.log`, `/tmp/apply_public_references.py` and the private temporary source matching file.

Validation passed **16 callcenter tests** (`/tmp/public-reference-callcenter-tests.log`) and **three ecommerce tests** (`/tmp/public-reference-producer-tests.log`) with zero failures/errors. Coverage includes different public/internal references, duplicates, invalid optional values, old payloads, denied direct metadata mutation, immutable snapshots, English/Arabic invoice cards and native source capture/exchange behavior. Databases were the existing isolated `callcenter_website_adapter_test_20261111` and `storefront_website_adapter_test_20261111`, with temporary HTTP/gevent ports 5069/5072 and 5075/5076, workers=0, cron=0 and stop-after-init. Arabic gettext checks and `git diff --check` passed.

Upgraded only `ab_crm_website` on callcenter first, then mirrored and upgraded only `ab_storefront_callcenter_adapter` on ecommerce; logs are `/tmp/public-reference-callcenter-upgrade.log` and `/tmp/public-reference-ecommerce-upgrade.log`, with no ERROR/CRITICAL entries. Both runtime ZIPs/checksums were rebuilt and verified under `/tmp/website-adapter-release`. Sixteen before/after business-table count/hash comparisons match, excluding only the intended new public-reference field and its native write actor/timestamp on Website order metadata (`/tmp/public-reference-records-before.json`, `/tmp/public-reference-records-after.json`). All temporary validation ports were released. User-managed processes were not restarted: **restart callcenter first, then ecommerce, and hard-refresh the browser** to load the updated consumer/producer Python code. Future confirmed orders carry the native reference automatically.
