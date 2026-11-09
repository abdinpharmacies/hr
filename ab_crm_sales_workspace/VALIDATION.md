# Header search and RTL/LTR Chatter review — 2026-11-08

Source delivery: `ab_crm_sales_workspace` **19.0.1.11.1**, optional `ab_crm_whatsapp_workspace` **19.0.1.1.2**. No live upgrade, user-process restart or customer/provider messages.

- Header/search interaction checks passed in **en_US, ar, ar_001**, at **1440×1000** and **390×844**. Channels are centered; search is at the outer edge. The expanding input opens toward the left in LTR and mirrors in RTL, without changing header/timeline geometry. Typing performs no search; Enter submits once. Clicking the native × clears query/results without a request and preserves the draft. Escape restores focus; outside click dismisses. Search guidance is translated and no redundant form buttons remain.
- Full Chatter review passed in all three locales at **desktop 1440×1000, tablet 900×900 and phone 390×844**: composer control placement and text direction, stable LTR phone prefixes, centered circular jump-to-latest, keyboard message menus within viewport, reply quotes, all 12 emoji choices and dismissal/focus, attachment-menu placement, translated controls, responsive template columns/stacking, template text/parameter direction, and drafts across channel switches. No horizontal overflow or browser page errors. These are browser viewport checks, not physical-device certification.
- Visual review found and fixed two defects: contact text showing around the narrow expanded search field, and English text/phone parameters inheriting RTL in the template editor. Final English and Arabic screenshots were inspected after both corrections.
- Targeted isolated module upgrade and browser regression: **35 HOOT tests / 183 assertions**, with zero failures/errors. The final run includes both addons and the new presentation changes. Evidence: `/tmp/chatter-header-search/final-browser-tests.log`.
- Full UI used synthetic `crm_chatter_bubbles_20261107`; regressions used `crm_whatsapp_sqlite_test_20261108`. Scripts/results/screenshots: `/tmp/chatter-header-search/ui_browser.mjs`, `ui-results.txt`, `full_review.mjs`, `full-review-results.txt`, and locale/viewport PNGs in the same directory.
- Existing English/Arabic strings were reused. Both catalogs per addon pass `msgfmt --check-format`; XML/manifests and whitespace checks pass. Runtime review packages exclude tests, test assets and caches.
- Validation used alternate ports **5069/5072** and **5085/5086**, zero workers/cron threads. Temporary processes were stopped and their ports released. The live 4092 process remained PID **595945**.

---

# Abdin Pharmacies saved replies — 2026-11-08

Reviewed and updated **44 active saved replies (22 Arabic/English pairs)** for **صيدليات عابدين / Abdin Pharmacies** in the existing callcenter intake branch. The CSV resource matches the saved records. This authorized content-only update used Odoo ORM and did not upgrade modules, restart Odoo or send customer messages.

- Preserved existing record IDs/XML IDs, names, active flags, branch/company scope and required placeholders. All bilingual parameter pairs match; all bodies fit the 4096-character limit.
- Preserved the three archived legacy replies. Message, operation and saved-reply record counts did not change.
- Fresh-transaction readback verified all 44 bodies and access for the three existing authorized agents.
- Replaced generic store branding; reviewed all wording for consistent polite Egyptian Arabic and concise English. Medicine-use/alternative questions remain pharmacist handoffs, with no new medical claims, fixed commercial promises or invented policies.
- Evidence and original content: `/tmp/abdin-template-review/`, including `update-result.json`, `before-records.json`, `verify.log` and the read/write verification scripts. No addon runtime code or translation catalog changed; these are explicit bilingual saved-message bodies.

---

# Embedded composer and search guidance — 2026-11-08

Source review delivery: `ab_crm_sales_workspace` 19.0.1.11.0 and `ab_crm_whatsapp_workspace` 19.0.1.1.1, plus the bounded Telegram video gateway extension required by the new attachment menu. No live database upgrade, gateway deployment, provider send or user-process restart was performed.

- Isolated targeted upgrade/regression on `crm_whatsapp_sqlite_test_20261108`: **80 Odoo tests, 0 failures/errors**, including **34 HOOT tests / 180 assertions**. After the final file-picker navigation guard, focused validation passed **2 Odoo tests** including **35 HOOT tests / 183 assertions**. Logs: `/tmp/chatter-composer-validation/odoo-tests.log` and `final-tests.log`.
- Gateway: **46 passed, 1 skipped** in `/tmp/chatter-composer-validation/gateway-tests.txt`. The skipped existing real audio-conversion test requires FFmpeg/ffprobe, absent on this host. Video codec and upload tests use mocked probe/provider responses; no real provider delivery or real codec conversion is claimed. Worker FFmpeg/ffprobe and the matching gateway update remain deployment prerequisites.
- Full browser UI on synthetic `crm_chatter_bubbles_20261107`: English, `ar`, `ar_001`, 1440×1000 and 390×844. Verified controls inside the message box, mirrored positions, centered translated composer placeholder, translated search placeholder without an external label, hover/click/keyboard/Escape/outside attachment menu behavior, file categories, location insertion preserving the draft without sending, and no horizontal overflow or page errors. Script/screenshots: `/tmp/chatter-composer-validation/ui_browser.mjs`, `*-composer.png`, `*-search.png`. Desktop English and mobile Arabic screenshots were visually reviewed.
- Location accepts bounded numeric coordinates and inserts a map URL into the composer. It is an ordinary text draft, not a native provider location object. Stale dialog/file-picker completion cannot populate another conversation. MP4 video is capped at 16 MB; access, private download, declared type/content, oversized payloads and queue snapshots were tested.
- POT exported from the isolated upgraded DB; both Arabic catalogs contain the new extracted terms and pass `msgfmt --check-format`. Python/XML/manifests and whitespace checks passed. All **227 protected file hashes** in `ab_sales`, `ab_whatsapp_api`, `ab_branch_api` and the task-start `ab_crm_messaging` tree remain unchanged. Previous unrelated changes are preserved.
- Temporary servers used **5069/5072** and **5085/5086**, workers=0 and max-cron-threads=0. Temporary processes were stopped; the live 4092 process remained PID **574948**.
- Runtime packages are in `/tmp/chatter-composer-validation/`, excluding Python/browser tests, test assets and caches. The task-only patch and starting source snapshots are retained there. The previously installed 44 bilingual pharmacy/cosmetics saved replies were not rewritten.

---

# Floating controls and bilingual saved replies — 2026-11-08 (19.0.1.10.1)

- Targeted isolated workspace upgrade plus existing browser regression: **32 HOOT tests / 173 assertions**, all passed; enclosing HttpCase: 1 test, zero failures/errors. Database `crm_whatsapp_sqlite_test_20261108`, ports 5069/5072, workers/cron disabled, stop-after-init. Evidence: `/tmp/chatter-floating-validation/browser.log`.
- Full synthetic UI checked at 1440×1000 and 390×844 in `en_US`, `ar` and `ar_001`. Search icon center matches header center; opening/searching does not alter header height, timeline position/height or composer position. Search is absolutely positioned, focuses its input and dismisses with Escape/outside click. Latest control has equal width/height, 50% radius, a transparent outer container, centered placement and working navigation. Drafts remain intact, no horizontal overflow or page errors. Script/screenshots: `/tmp/chatter-floating-validation/ui_browser.mjs` and the six locale/viewport screenshot pairs in that directory. Uses only `crm_chatter_bubbles_20261107` synthetic fixtures.
- User-authorized data addition: **44 saved replies (22 EN + 22 AR)** in the existing `callcenter` branch `telegram-callcenter-intake`, using permission-checked ORM and module-owned XML IDs. Three existing saved replies at write time remain unchanged. Message and sending-operation counts were unchanged by the import. All new records were read back and verified; all 3 existing authorized branch users checked can read all 44. Evidence: `template-install.json`, `template-install.log`, `template-verify.log` in the same directory. No provider messages sent.
- Reused existing translated UI strings; both Arabic catalogs pass gettext checks. Catalog language pairs have matching required placeholders. XML/JavaScript syntax and whitespace checks pass. Protected addons and the optional WhatsApp addon are unchanged from this task's baseline.
- Runtime archive excludes development tests, test assets and caches. Source UI remains for review; only the explicitly requested saved-reply data was added to `callcenter`. No live addon upgrade or live process restart. Temporary server cleanup and port checks are recorded in the evidence directory.

---

# Chatter UI improvements — 2026-11-08 (19.0.1.10.0 / WhatsApp 19.0.1.1.0)

Implemented for review; no live upgrade, restart, activation or provider send.

- Final targeted upgrade and regressions on `crm_whatsapp_sqlite_test_20261108`: **79 tests, zero failures/errors, no skips**, including the browser HttpCase. The HOOT run contains **32 browser tests and 173 assertions**, all passed. Log: `/tmp/chatter-ui-validation/final-regressions.log`.
- Backend coverage includes template creation/update selection and archival without sends, employee-specific unread boundaries, read-only fetch/search/context operations, query-aware pagination, existing direct ORM/RPC permission checks, company/branch isolation, private media and immutable retry identity.
- Browser coverage includes first-template selection, searchable lists, repeated Save, refresh, dirty archival, Discard/Keep editing (including dialog close), read-only permissions, loading failures, required parameters, insertion without sends, explicit WhatsApp queueing, all twelve emoji selections/carets, native-menu exceptions, pointer/keyboard/chevron entry points, focus restoration, RTL/viewport bounds, search pagination and stale responses, draft preservation, private-thumbnail loading and URL cleanup including delayed responses after unmount.
- Full synthetic UI workflow passed at 1440×1000 and 390×844, with English, `ar` and `ar_001`: unread navigation, search pages of 50 plus 10 older matches, highlighted context, unchanged drafts and search-clear scroll position, emoji dismissal/caret, menus, template guards, stacked mobile templates and no page errors or horizontal overflow. Script and screenshots: `/tmp/chatter-ui-validation/ui_browser.mjs`, `templates-en.png`, `menu-en.png`, `search-ar.png`, `search-ar_001.png`, `templates-mobile-ar.png`, `templates-mobile-ar_001.png`, `chatter-mobile-ar.png`, `chatter-mobile-ar_001.png` in that directory.
- Full UI validation uses the existing synthetic `crm_chatter_bubbles_20261107` database and private fixture credentials. A test-only generic `ar` language record was added there to exercise that catalog alongside installed `ar_001`; session context was refreshed before rendering each language. Runtime translation delivery for both addons also passed separately on the regression DB. Both catalogs per addon pass `msgfmt --check-format`; existing translations are preserved.
- Python/XML parsing, JavaScript syntax, manifest paths/dependencies and whitespace checks pass. All **202 protected-addon file hashes** (`ab_sales`, `ab_whatsapp_api`, `ab_branch_api`) match the task-start snapshot. Existing unrelated work remains outside this task's edits.
- Runtime archives exclude Python/browser tests, test asset declarations and caches: `/tmp/chatter-ui-validation/ab_crm_sales_workspace-19.0.1.10.0.tar.gz` and `/tmp/chatter-ui-validation/ab_crm_whatsapp_workspace-19.0.1.1.0.tar.gz`. The task-only patch and initial source snapshots are retained in the same evidence directory.
- Final tests used free alternate ports **5085/5086**; synthetic UI used **5069/5072**, with zero workers/cron threads. Temporary servers were stopped and all four ports released. The live Odoo PID on 4092 remained **470878** throughout.

Earlier iterations caught and corrected a Sass `min()` compatibility issue, missing confirmation cancel callback, unsupported Owl expression, search-clear geometry and post-render caret timing. Final passing evidence above supersedes those exploratory logs. Tests use synthetic data and mocked provider operations; no live delivery or deployment is claimed. The deferred configuration, provisioning, worker/webhook, website/application chat and queue-migration work remains deferred.

---

# Message bubbles and navigation — 2026-11-07

Implemented in `ab_crm_sales_workspace` 19.0.1.8.0. This entry covers the current source change; historical deployment statements below do not apply to it. No live callcenter upgrade, user-process restart, real provider send, gateway protocol change or external database access was performed.

## Results

| Check | Actual result / evidence |
| --- | --- |
| Clean install with optional WhatsApp adapter | `crm_chatter_bubbles_fresh_20261107`, 58 workspace methods, zero failures/errors; `/tmp/chatter_bubbles_final_install.log` |
| Targeted workspace upgrade with optional WhatsApp adapter | `crm_chatter_bubbles_clean_20261107`, 58 workspace methods, zero failures/errors; `/tmp/chatter_bubbles_final_upgrade.log` |
| Messaging regressions in their own database | `crm_chatter_receipts_20261107`, 23 methods, zero failures/errors, including WhatsApp window and out-of-order receipt handling; `/tmp/chatter_bubbles_messaging.log` |
| Focused Odoo HOOT tests | 11 tests / 29 assertions passed; `/tmp/chatter_bubbles_hoot_final.log` |
| Browser navigation and layout | Channel/account highlight, draft retention, disabled Edit/Delete, dropdown Escape, quote navigation without history/draft loss, English/Arabic and 390px layout; zero JavaScript errors; `/tmp/chatter_bubbles_browser.mjs`, `/tmp/chatter_bubbles_ui_final.log` |
| Browser media | Image/audio/PDF viewer controls, ready document download, pending download guard, image quote thumbnail and supported reaction picker; zero JavaScript errors; `/tmp/chatter_media_browser.mjs` |
| Translation | Odoo POT `/tmp/chatter_bubbles.pot`: all 361 exported terms covered in both catalogs, including 14 new terms, no missing/empty/fuzzy terms; both `msgfmt --check-format` checks passed. Runtime Arabic header and RTL rendering verified. |
| Static checks | Python/XML parsing, JS syntax, manifest paths/dependencies/metadata, test-only asset registration and `git diff --check` passed. |
| Packaging | `/tmp/sales-chatter-messages-19.0.1.8.0.tar.gz`; runtime-only artifact excludes Python/frontend tests, caches and test asset registration. Source retains all development tests. |

Screenshots: `/tmp/chatter-bubbles-en.png`, `/tmp/chatter-bubbles-ar.png`, `/tmp/chatter-bubbles-mobile-ar.png`, `/tmp/chatter-bubbles-media.png`.

The HOOT suite checks every outgoing receipt presentation, absence of incoming ticks, timezone/date rollover, dropdown keyboard dismissal/focus, invisible/obscured read suppression, separate drafts/attachments, stale navigation, reaction eligibility, clipboard/download failure feedback, unavailable quotes and preview URL cleanup. Python tests cover server-side destination/session authorization, same-phone/different-customer denial, non-mutating fetch/focus/history, monotonic acknowledgements and originals outside the current page.

## Reproduction and validation limits

Interpreter `/opt/odoo19/venv19/bin/python`, server `/opt/odoo19/server/odoo-bin`, addons `/opt/odoo19/server/addons,/opt/odoo19/worktrees/callcenter19`. Private isolated config `/tmp/chatter_bubbles.conf`. All jobs explicitly used `--workers=0 --max-cron-threads=0`, HTTP/gevent 5069/5072 or 5073/5074; installs/upgrades used `--stop-after-init`. Database names and filters were explicitly selected. The browser fixture database is `crm_chatter_bubbles_20261107`.

Install: `-i ab_crm_sales_workspace,ab_crm_whatsapp --test-tags /ab_crm_sales_workspace`. Upgrade: `-u ab_crm_sales_workspace --test-tags /ab_crm_sales_workspace`. Messaging-only database: `-i ab_crm_telegram,ab_crm_whatsapp --test-tags /ab_crm_messaging`.

HOOT runs at `/web/tests?debug=assets&headless&loglevel=2&preset=desktop&filter=ab_crm_sales_workspace&timeout=15000`. The existing POS patches access `ab_sales.pos` before it is registered under HOOT’s dependency ordering. For this isolated test run only, database `ir.asset` exclusions in `web.assets_unit_tests_setup` removed `ab_sales/static/src/pos/zz*patch.js` and `ab_employee_access_sales/static/src/pos/ab_employee_access_sales_pos_patch.js`. No shared source or production bundle was changed. These exclusions are needed to reproduce the focused suite until the unrelated POS test-loading issue is fixed.

Early runs found a missing name in a new test fixture, a Sass mixed-unit expression and test-harness setup/visibility issues; these were corrected before the passing results above. Running the messaging suite in a workspace-installed database fails its existing account fixture because it lacks the workspace-required intake mapping. Its final passing run used the separate messaging-only database. Synthetic notification dismissal was synchronized before media interactions. Test counts above are method counts, excluding Odoo setup/teardown statistics.

The UI does not activate WhatsApp, Website or Application sending. Website/Application tabs require a real installed account integration and authorized existing conversation. Telegram remains limited to Sent; WhatsApp Delivered/Read continue to depend on provider evidence, separate from employee reading, following the [WhatsApp receipt definitions](https://faq.whatsapp.com/665923838265756/). No real-provider pilot or production-scale performance benchmark was performed. Browser audio/PDF checks verify viewer selection and controls with synthetic media; they are not codec compatibility certification.

---

# First-release implementation validation — 2026-11-05

This section supersedes earlier claims about claiming conversations, transient notification cursors and visible provider evidence. Earlier evidence below is retained as history.

Implementation is verified in isolated databases. Callcenter rollout is pending a coordinated restart of the user's PyCharm-managed process, which currently runs with `--dev=xml` rather than Python auto-reload. No callcenter upgrade, user-process restart, delivery-switch change, old-message resend, external database write or live test message was performed during this validation.

## Verified behavior

- Authorized PIN employees share conversations and orders without claiming; historical assignments remain untouched. Session, employee, branch and company checks apply on the server. Order revision, stale-editor and price auditing checks are retained.
- One sticky alert per conversation persists per Odoo user/employee/company. Exact acknowledged message IDs are stored separately from read positions, preventing concurrent or late-committing incoming messages from being lost behind a numeric watermark. Conversation pages are drained without dropping backlogs.
- Alerts survive refresh/re-login, ordinary reading does not dismiss them, logout hides them, and dismissal synchronizes across tabs. Successful alert navigation focuses its latest customer message after rendering and media layout. Unsent drafts and older-history scroll are preserved.
- One footer/timestamp per message shows normalized statuses. Telegram stops at Sent. Staff reads are not customer receipts; presence is never inferred. Protected administrative diagnostics retain raw evidence. Retry requires definitive retryable failure and is bounded to three attempts; uncertain outcomes and invalid media are not retried.
- Contacts support Add/Edit/Delete/Refresh, autofocus/debounced search, pagination, normalized-phone duplicate selection, and contacts without conversations. Edits use local CRM overrides; archival preserves messages, verified identities, orders and incoming alerts. Catalog customers and channel destinations are unchanged.
- Customers and Messages/Notes inherited architectures load under `--dev=xml`. All 19 installed CRM/OMS menu actions load list/form/search architectures and pass browser list/form checks, using synthetic records for immutable ledgers rather than weakening create access.

## Evidence

| Check | Result / evidence |
| --- | --- |
| Clean install with installed CRM/OMS module set | `crm_chatter_release_clean_20261105`, 53 methods, zero failures/errors; `/tmp/chatter_release_clean_install.log` |
| Final targeted upgrade with `--dev=xml` | `crm_chatter_release_clean_20261105`, 55 methods, zero failures/errors; `/tmp/chatter_release_final_tests.log` |
| Messaging regressions | `crm_chatter_messaging_release_20261105`, 23 methods, zero failures/errors; `/tmp/chatter_release_messaging_final.log` |
| Browser interaction | `/tmp/chatter_release_browser.mjs`: grouped sticky alerts, refresh persistence, focus from Orders, contact create/edit/archive, Arabic RTL and mobile |
| Long-history and tabs | `/tmp/chatter_release_advanced_browser.mjs`: 65-message additions, older-history scroll, filtered/already-open focus, draft retention, cross-tab dismissal, signed-out backlog, footer/timestamp cardinality |
| CRM/OMS menus | `/tmp/chatter_release_menu_browser.mjs`, 19 list/form actions; `/tmp/chatter_release_views3.log` and helper output cover list/form/search architectures |
| Screenshots | `/tmp/chatter-release-en.png`, `/tmp/chatter-release-ar.png`, `/tmp/chatter-release-mobile-ar.png`, `/tmp/chatter-release-long-history.png` |
| Localization | Final Odoo POT export `/tmp/chatter_release_verified.pot`; both Arabic catalogs cover all terms without fuzzy/empty translations; `msgfmt --check-format` passes; runtime action verified as Sales Chatter / محادثات المبيعات |
| Static/package checks | Python/XML parsing, JS syntax, manifest data paths, imports, dependencies, developer metadata; runtime artifact excludes tests, fixtures, caches and demos |

Tests use the project interpreter `/opt/odoo19/venv19/bin/python`, `/opt/odoo19/server/odoo-bin`, and addons `/opt/odoo19/server/addons,/opt/odoo19/worktrees/callcenter19`. Separate private configurations set exact database filters. Test/upgrade processes use `--workers=0 --max-cron-threads=0 --stop-after-init` and explicit free HTTP/gevent pairs 5069/5072 or 5073/5074. Browser servers were tracked and stopped; the user's 4092 process was not stopped or rebound.

Early test runs exposed stale claim assertions, an HTTP database-filter mismatch, catalog metadata and Sass compilation issues; these were corrected before the passing runs. One browser assertion originally measured scroll before the older-message render completed; the corrected test waits for rendering, then measures preservation through polling. A read-only ledger form needed a synthetic existing record rather than an unauthorized create attempt. None of those failed runs is represented as passing evidence.

No real Telegram/WhatsApp delivery pilot or production-scale performance benchmark was run. Deferred WhatsApp/Website activation, RAG, fulfillment submission, stock/payment operations and external databases remain outside this release.

Provider semantics were checked against the [Telegram Bot API](https://core.telegram.org/bots/api) and [Meta's delivered-status example](https://www.postman.com/meta/whatsapp-business-platform/request/vm6dfdv/status-message-delivered-business-delivered-from-user). The existing authenticated WhatsApp status path remains responsible for delivery/read evidence; this release does not activate it.

## Rollout

Affected modules only: `ab_crm_sales_workspace` 19.0.1.7.0 and `ab_crm_messaging` 19.0.1.4.0. Runtime package: `/tmp/sales-chatter-first-release-20261105.tar.gz`.

After coordinating the PyCharm reload, run the targeted upgrade with the verified callcenter config/database and alternate ports:

```bash
/opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin \
  -c /opt/odoo19/conf/callcenter19.conf -d callcenter \
  -u ab_crm_messaging,ab_crm_sales_workspace --stop-after-init \
  --workers=0 --max-cron-threads=0 --http-port=5069 --gevent-port=5072 \
  --logfile=/tmp/chatter_first_release_callcenter_upgrade.log
```

The existing callcenter process must load the new Python modules before using the new assets. No temporary agent server should bind port 4092 without explicit authorization. Compare account switches, existing message/operation IDs and business-record counts before/after upgrade; do not resend existing operations.

---

# Screenshot layout correction and live activation — 2026-11-05

This entry supersedes the earlier placement of Orders below the chat and earlier statements that live activation had not been performed.

- Compared the two user-provided screenshots with `ab_whatsapp_api` and the mapped POS checkout. Corrected the collapsing chat layout, contact previews, composer, automatic selection, scroll behavior and separate Orders action. The scoped order editor now follows POS proportions and retains its existing protected business operations.
- **44 backend tests, zero failures/errors** on `crm_chatter_login_fresh_20261104`, targeted `-u ab_crm_sales_workspace --test-tags /ab_crm_sales_workspace`; log `/tmp/chatter_layout_tests.log`.
- Browser checks on `crm_chatter_repair_ui_20261105` passed: full-height chat, automatic selection, enabled composer with content, separate Orders navigation, employee/company-scoped unsent draft retention, branch/product lookup, quantity/total, saving, close guard, saved replies, Arabic RTL and mobile order layout. Final script: `/tmp/chatter_layout_browser.mjs`. No JavaScript errors. An initial SCSS mixed-unit expression was corrected and the compiled bundle was verified in the passing run; test selector races were also corrected.
- Screenshots: `/tmp/chatter-layout-chat-en.png`, `/tmp/chatter-layout-chat-ar.png`, `/tmp/chatter-layout-orders-en.png`, `/tmp/chatter-layout-editor-en.png`, `/tmp/chatter-layout-editor-ar.png`, `/tmp/chatter-layout-editor-mobile-ar.png`.
- Exported the module POT and verified every exported term in both Arabic catalogs; gettext format, Python/XML/JavaScript syntax, manifest paths and action/menu ownership passed. Live menu labels verified as `Orders` / `الطلبات`.
- Live diagnosis found an unset Odoo outgoing flag, gateway sending disabled, a legacy customer name equal to its Telegram destination, and no saved profile name. The customer label now falls back to the confirmed phone when a genuine name is unavailable. Profile capture applies to new inbound events; historical evidence was not invented or rewritten.
- User explicitly approved restarting Odoo and enabling delivery of both queued contact requests. Applied targeted workspace upgrade to `callcenter` (`/tmp/chatter_layout_callcenter_upgrade.log`), enabled the matching account through ORM, restarted callcenter Odoo on 4092, and enabled/restarted the managed gateway worker and receiver. Live Odoo HTTP returned 200; the account's messaging/outgoing flags are true and labels no longer expose destination IDs.
- Both existing queued contact requests reached Odoo `accepted` with provider references and no errors. Gateway rows reached `done`, `status=accepted`, `sends=1` each. The second receipt recovered through the normal worker lease cycle; an attempted bounded recovery script stopped at its precondition because the worker had already completed it, without making any writes. No new test messages or manual retries were sent. Provider acceptance is not customer-read evidence.
- Existing database warnings about legacy model declarations and POS draft-cache constraints remain outside this change. No changes were made to POS, WhatsApp, shared widgets, sales/pricing/stock business logic or unrelated worktree edits.

Validation servers used isolated configurations, cron disabled and ports 5069/5072. Live upgrade/shell commands used 5073/5074 with no live HTTP listener. The temporary browser server was stopped after checks; the authorized live Odoo and messaging services remain running.

---

# Sales Chatter channel-order repair — 2026-11-05

Source implementation verified on isolated databases; **not deployed or verified against live Telegram**. This section supersedes earlier contact-linking, composer and order-layout descriptions below.

- Workspace suite: **42 tests, 0 failures/errors**, including eight added regressions. Targeted upgrade of `ab_crm_sales_workspace,ab_crm_messaging,ab_crm_telegram` on `crm_chatter_login_fresh_20261104`; final log `/tmp/chatter_repair_final_tests.log`. Runner statistics count setup/teardown separately (46); 42 is the actual result count.
- Messaging/Telegram regression: **23 tests, 0 failures/errors**, on `crm_messaging_validation_20261103`; `/tmp/chatter_repair_messaging_tests.log`.
- Authenticated Playwright: synthetic Call Center user and employee/PIN on `crm_chatter_repair_ui_20261105`, port 5069. English and Arabic RTL checks cover branch search, the shared POS product card, keyboard quantity entry, F2 focus, barcode lookup, price filters, units and conversion, quantity controls, branch repricing, draft switching, window controls, guarded close, template dialog, attachments, audio playback/cancellation/track cleanup, emoji, attachment-only queueing and failed-queue draft preservation. Mobile Arabic layout has no horizontal overflow. Actual browser full-screen entry/exit and category filters also pass.
- Recovery: a server-revoked employee session preserves composer and unsaved order edits for re-authentication by the same employee. A simulated ownership-loss response cancels recording, releases microphone tracks and disables Send. Tests never send provider messages; queued messages exist only in the isolated browser database.
- Contacts: before claim, after claim, expired session, event replay, repeated contacts, unique/ambiguous/no match, third-party shares, invalid phones, conflicting identities, scoped candidate selection and direct evidence forgery are covered. Chat-detail reads do not invoke identity linking. Customer approval, branch and valid-line requirements remain; missing phone verification or catalog matching does not prevent acceptance.
- Security and integrity: existing company/branch, employee ownership, direct ORM/RPC, stale-edit, immutable snapshot, price audit and no-sales-side-effect regressions pass. A separate two-cursor check proves concurrent claims cannot acquire the same lock. Manager catalog controls are absent for Call Center staff and present for administrators; CRM evidence views render translated English/Arabic labels.
- Business counts after browser tests: `ab_sales_header`, `ab_sales_callcenter_rpc_log`, `ab_sales_pos_draft_cache`, `ab_oms_request`, `ab_oms_attempt` are all **0**. Native sale/invoice/payment/stock models are not installed in that database. No POS action, POS persistence or fulfillment bridge is invoked by the workspace.
- Both Arabic catalogs contain every exported workspace term; original translations/msgids are preserved. All six changed-module catalogs pass `msgfmt --check-format`. Python/XML parsing, JavaScript syntax, manifest references, developer metadata and runtime package exclusions pass.

CRM/OMS ownership audit: existing models, XML IDs, actions and menus remain. The Sales Chatter action owns channel orders; OMS Requests/Lines/Submissions retain their separate lifecycle. Existing CRM conversation/customer/message forms now expose identification evidence, matching review, staff read history and channel-order history. Existing Messaging Delivery remains the diagnostics entry point. No redundant navigation was removed without evidence.

Evidence scripts: `/tmp/chatter_repair_browser.mjs`, `/tmp/chatter_repair_interactions.mjs`, `/tmp/chatter_repair_interactions_ar.mjs`, `/tmp/chatter_repair_composer.mjs`, `/tmp/chatter_repair_recovery.mjs`, `/tmp/chatter_repair_final_audit.py`. Screenshots: `/tmp/chatter-repair-en.png`, `/tmp/chatter-repair-ar.png`, `/tmp/chatter-repair-mobile-ar.png`, `/tmp/chatter-repair-interactions-en.png`, `/tmp/chatter-repair-interactions-ar.png`, `/tmp/chatter-repair-composer-final-en.png`, `/tmp/chatter-repair-composer-final-ar.png`. Credentials remain in a private test-only file and are excluded from delivery.

Validation used `/opt/odoo19/venv19/bin/python`, the mapped callcenter worktree, cron/workers disabled, and alternate ports 5069/5072, 5073/5074 or 5075/5076. Initial browser checks exposed an unsupported F2 hotkey registration and a mixed-unit SCSS compilation error; both were corrected before final passing runs. Early browser assertions that raced Owl rendering were changed to wait for the actual rendered state. The cloned test database received its corresponding test filestore before final checks.

Release-version targeted upgrade also passed (`/tmp/chatter_repair_release_upgrade.log`). Runtime package: `/tmp/sales-chatter-repair-20261105.tar.gz`; it contains the three affected addons, requires their existing dependencies, and excludes tests, validation reports, fixtures, credentials and caches. A review diff against the preserved starting snapshot is `/tmp/sales-chatter-repair.patch`.

Cleanup verified: temporary ports 5069/5072/5073/5074/5075/5076 are released. The original user-managed process, PID 1942312, remains on port 4092.

Live limits: the Call Center role is authorized, but no authenticated live employee session/credentials or identified Telegram test recipient was supplied. Consequently the original live Send-button cause, live gateway availability and Telegram provider acceptance remain **unverified**. No live outgoing switches, credentials or business data were changed. No live upgrade or restart was performed; a targeted upgrade and user-managed reload are still required to use the new Python registry in Callcenter. Notification delivery for the access question failed on both Telegram and desktop; no successful delivery is claimed.

---

# Order popup and messaging implementation — 2026-11-05

Implemented in source and verified in isolated databases. **Not upgraded into `callcenter` and not activated for live outbound traffic.** The user-managed Odoo process on 4092 was not restarted. The supplied plan described the screenshot layout, but the screenshot itself was unavailable in this context; browser checks validate the specified layout rather than a pixel comparison.

| Check | Result |
| --- | --- |
| Fresh installation | `crm_chatter_popup_fresh_20261105`: 31 tests, zero failures/errors before the final three regression additions |
| Final targeted upgrade | `crm_chatter_login_fresh_20261104`: **34 tests, zero failures/errors** (`/tmp/chatter_popup_final_tests3.log`) |
| Shared messaging/controller suite | **23 tests**, verified separately without workspace fixture dependencies; final log `/tmp/chatter_popup_final_messaging.log` |
| Gateway/queue/provider suite | **82 passed, no skips**, all provider traffic mocked; real local FFmpeg conversion and duration checks included |
| Browser | English and Arabic RTL, branch search, product-name search, adding lines, quantities/totals, delivery-only edits, guarded close, template placeholder insertion, image previews/removal, recording playback/cancellation, logout microphone cleanup, explicit queueing and mobile layout passed |
| Read/notification behavior | Polling continues while the dialog is open; hidden messages do not advance employee read positions. Unclaimed reception and Odoo-outage durability remain covered by backend/gateway tests |
| Translation/static checks | Every exported term translated in both catalogs; gettext format, Python/XML/JavaScript syntax, manifests and author/developer metadata passed |
| Shared source preservation | No changes to `ab_sales`, `ab_whatsapp_api`, `ab_widgets`, `ab_customer`, `ab_product` or `ab_store` |

Regression coverage includes branch isolation, atomic failed-save rollback, branch repricing and old/new audit, stale editors including acceptance/reopening, accepted identity snapshots, no sales/submission/payment/stock side effects, contact prompting once, ambiguous/no customer matches, third-party/typed confirmation, direct ORM denial, private media and immutable content, server limits, saved-reply manager enforcement, scoped cancellation refusal after leasing, and provider evidence.

Browser scripts and synthetic screenshots: `/tmp/chatter_popup_browser_final.mjs`, `/tmp/chatter_composer_browser.mjs`, `/tmp/chatter-popup-en.png`, `/tmp/chatter-popup-ar.png`, `/tmp/chatter-popup-mobile-ar.png`, `/tmp/chatter-composer-en.png`. Test conversations contain synthetic content only. A browser test queued synthetic messages only in the isolated Odoo database; no gateway uses that database and no provider send occurred.

Validation used `/opt/odoo19/venv19/bin/python`, the worktree addons path, isolated configs, cron disabled and ports 5069/5072 or 5073/5074. Temporary servers were stopped and ports 5069/5072/5073/5074 were released. The original user-managed Odoo PID 1554823 remained on 4092. Production config and the running user service were not changed. The initial combined test run used a mismatched database filter and incompatible messaging fixtures; the suites were separated. A later attempt used a database with browser fixtures and hit duplicate test logins; the final run uses the unseeded isolated database. Browser testing exposed and fixed product-card-name lookup and microphone cleanup. The remaining Starlette/HTTPX warning is from existing gateway test tooling.

Runtime update archive: `/tmp/callcenter-popup-update-20261105.tar.gz` (86 files). It contains the three changed addons and gateway runtime files; tests, fixtures, caches and protected configuration are excluded. Existing dependent addons must already be available.

## Rollout prerequisites

- Review and perform a targeted upgrade of `ab_crm_messaging,ab_crm_telegram,ab_crm_sales_workspace`, then reload the user-managed Odoo process and deploy the gateway worker/receiver code. No live upgrade or service restart was performed here.
- Install the OS `ffmpeg` package on the worker host. This machine lacks system `ffmpeg`/`ffprobe`; validation used the distro binaries extracted under `/tmp/chatter-ffmpeg`. The worker rejects invalid/unconvertible recordings before provider submission, with explicit media-validation evidence.
- Both the Odoo account **Outgoing Sending Enabled** and gateway `sending_enabled` must be explicitly activated for the separately approved pilot. Automatic contact prompting additionally requires **Automatic Contact Request**. All new account flags default off.
- Before that pilot, inspect the two previously identified live requests and use `action_cancel_unsent(reason)` only if they are still never-leased, never-submitted queued attempts. Their live IDs/states were not supplied in this context and no live request was cancelled. History is retained. Do not retry uncertain sends.
- WhatsApp/Meta submission and approvals remain in the existing integration; this work does not add a second sender. Telegram exposes provider acceptance, not customer read/last-seen evidence.

---

# POS-style login correction — 2026-11-04

This correction supersedes the earlier custom login form and token-entry wizard below.

- The Chatter popup now matches the POS layout: one searchable employee field, PIN, close control and Employee Login button. It uses the existing `ABMany2one` selector with eligible Call Center profile IDs. Its component and session remain independent from POS.
- The token is entered only through standard Odoo System Parameters. The configuration wizard has no `bot_token` or `branch_id` field. Connection preparation remains under Sales → Configurations → Telegram Connection; there is no setup button in Chatter.
- 24 focused Odoo test methods passed with zero failures/errors on `crm_chatter_login_fresh_20261104` (`/tmp/chatter_simple_login_final_tests.log`). Tests include filtered employee selection, rejection of direct login by a non-Call-Center employee, token absence from the wizard, administrator-only parameters and account-bound credential access.
- English and Arabic browser checks passed with no JavaScript errors: selector search/login, logout, RTL, no Telegram workspace control for staff or admin, no token/Intake configuration fields and connection preparation from an existing system parameter. `/tmp/chatter_simple_browser.mjs` and `/tmp/chatter-simple-login-en.png`, `/tmp/chatter-simple-login-ar.png`, `/tmp/chatter-simple-connection-en.png`, `/tmp/chatter-simple-connection-ar.png` contain synthetic isolated evidence.
- Both Arabic catalogs passed `msgfmt --check-format`; Python/XML parse, JavaScript syntax and manifest references passed. `ab_sales`, `ab_whatsapp_api` and shared employee-login components were not edited.
- The development company identifier was read from its already configured messaging branch: company 1. Its token parameter is `ab_crm_sales_workspace.telegram_token.1.tg-callcenter`. No real token was provided or changed.

Development upgrade: `/tmp/chatter_simple_callcenter_upgrade.log`. Reload the user-managed Odoo process before using the changed Python models. The live Telegram pilot remains pending; manual token and gateway steps are in [DEVELOPMENT.md](../crm_messaging_gateway/DEVELOPMENT.md).

---

# Chatter login and Telegram system parameter update — 2026-11-04

This update supersedes the POS-session and external-only-token setup described in earlier evidence below. The implementation is installed in `callcenter`; the real Telegram pilot remains **not live**.

- Fresh install: `crm_chatter_login_fresh_20261104`, 26 test methods, zero failures/errors (`/tmp/chatter_login_fresh.log`).
- Targeted upgrade: same isolated DB, 26 methods, zero failures/errors (`/tmp/chatter_login_upgrade_final.log`). Includes real bearer HTTP token retrieval, account mismatch rejection and `Cache-Control: no-store`.
- Gateway: 56 tests passed against the isolated PostgreSQL queue. Provider calls remain mocked.
- Browser: separate employee/PIN popup; immediate workspace access; POS storage untouched; Chatter logout revokes its token; notifications appear while viewing the Sales dashboard and open their conversation; draft/scroll preservation and older-message pagination pass. No browser errors.
- Arabic: translated employee popup, workspace and Telegram Setup verified with actual RTL direction under `ar_001`; workspace is RTL with no horizontal overflow. Both Arabic catalogs have 213 translated entries; fresh exported strings and `msgfmt --check-format` pass.
- Admin with legacy core integration role can use the staff workflow after employee login. Dedicated messaging service users remain blocked from staff actions. PIN throttling, eligibility changes, shared-login employee ownership, company/intake permissions and token-read isolation are covered.
- Telegram Setup uses a masked input, clears it after saving, creates a disabled account and stores its token in an administrator-only system parameter. The gateway's `token_source=odoo` loads it into process memory without persisting it in gateway JSON.
- Development business counts remain unchanged: 44 sales headers, 91 callcenter RPC log records and zero OMS submission attempts. No payment or native stock tables are installed. No `ab_sales` or `ab_whatsapp_api` source changes.

Browser evidence uses synthetic fixtures only in `crm_chatter_session_test_20261104`: `/tmp/chatter_session_browser.mjs`, `/tmp/chatter-session-en.png`, `/tmp/chatter-session-ar.png`, `/tmp/chatter-login-ar.png`, `/tmp/chatter-telegram-setup.png`, `/tmp/chatter-telegram-setup-ar.png`. The token used there is deliberately synthetic, never a real Telegram credential.

Final development upgrade logs: `/tmp/chatter_login_callcenter_upgrade.log`, `/tmp/chatter_login_callcenter_final_rtl.log`. Temporary validation servers were stopped. The user-managed Odoo process was not stopped or restarted. Reload it to load the changed Python registry. The real BotFather token must be entered in **Sales → Configurations → Telegram Setup**. Queue-role provisioning still needs local administrator credentials; bot verification, a participant and explicit activation approval remain required. See [the updated runbook](../crm_messaging_gateway/DEVELOPMENT.md).

---

# Sales Chatter verification — 2026-11-04

**Implemented and installed in development; not live.** The real Telegram pilot has not run. No provider message was sent or received by these checks.

| Check | Result |
| --- | --- |
| Gateway, polling, provider and PostgreSQL queue tests | **55 passed**, no skips; provider HTTP mocked |
| Final clean Odoo installation | `crm_chatter_verified_20261104`: **20 tests**, 0 failures/errors |
| Final Odoo upgrade, including source timestamps | Same isolated database: **20 tests**, 0 failures/errors |
| Messaging regressions and real bearer HTTP controller tests | Separate `crm_messaging_validation_20261103`: **23 tests**, 0 failures/errors |
| Concurrent claims | Two independent PostgreSQL transactions: the second claim is excluded by the row lock; same-login/different-employee rejection also passes |
| Direct ORM/RPC ownership | Missing/wrong employee sessions cannot create/edit/approve Telegram messages or bypass customer confirmation; ownership enforced on retry |
| Browser | English LTR and Arabic RTL; no horizontal overflow or JS errors; menu immediately after POS; search, both pagination controls, 64-message history, source color and draft preservation across refresh/switching verified |
| Translations | Both Arabic catalogs preserve existing terms; added terms translated; gettext format checks pass |
| Development deployment | Targeted install/upgrade completed against `callcenter`, using alternate ports; user-managed process was not restarted |
| Business-record check | Sales headers **44**, callcenter submission logs **91**, OMS attempts **0** before and after; no changes. Native payment/stock tables were absent from the queried database |
| Source preservation | `git diff -- ab_sales ab_whatsapp_api` remains empty; unrelated uncommitted addons and AGENTS.md preserved |

Odoo runner statistics include setup/teardown; counts above use actual test-method result summaries. The first controller run exposed an unsupported request-body accessor and an inactive system-user fixture; both were corrected before the passing runs. A direct-RPC test initially expected a different missing-session exception; the workspace now consistently raises AccessError. An early browser assertion ran before asynchronous selection completed; the final run waits for the selected conversation and verifies both drafts.

The new tests cover durable offset commit/replay, competing receiver locks and recovery, webhook/polling exclusion, webhook ownership checks, per-conversation ordering, uncertain-send blocking, literal-loopback HTTP, encoded database-name rejection, controller bearer/account/envelope guards, history pagination, menu placement and direct employee ownership. Existing suites cover exact phone matching, returning identities, customer confirmation, company/branch isolation, accepted revisions, price audits and sales non-submission.

## Development state and blockers

Requested bot: `@abdin_callcenter_bot`. Its identity is **not verified** without the privately entered BotFather token. Intake maps to the existing Al Ataba replica (serial 102), with default store code **140** and existing allowed fulfillment store codes **29/140**. A disabled dedicated service user and seven-day API key were prepared in mode-0600 protected configuration; no messaging account was activated.

The separate live queue could not be provisioned: the Odoo PostgreSQL role lacks CREATEROLE, and local sudo requires the user's password. The masked setup commands are in [the runbook](../crm_messaging_gateway/DEVELOPMENT.md). The existing process on 4092 returned **404** for the new versioned route and needs a user-managed reload. A Telegram participant and explicit live activation approval remain outstanding. An Odoo Call Center user still needs an authorized employee session; no PINs were reset.

No supervised live gateway/receiver/worker is running. Isolated queue tests are not evidence of live connectivity. No public hostname or tunnel is required for polling. Notification delivery for the setup question succeeded after initial sandbox failures, but automatic reply routing could not identify the turn; the question was also presented in Codex. The notification reply window expired without a submitted setup answer.

## Evidence and reproduction

- `/tmp/crm_chatter_verified_fresh.log`: clean install, 20 methods.
- `/tmp/crm_chatter_verified_upgrade.log`: final workspace/controller upgrade, 20 methods.
- `/tmp/crm_chatter_messaging_final.log`: messaging regressions, 23 methods.
- `/tmp/crm_chatter_callcenter_timestamp.log`: targeted development deployment.
- `/tmp/chatter_browser.mjs`, `/tmp/chatter-en.png`, `/tmp/chatter-ar.png`: isolated browser checks and synthetic screenshots.
- `/tmp/chatter_callcenter_baseline.json`: sanitized before/after business counts.

Gateway command: `MESSAGING_TEST_DSN_FILE=/tmp/crm_messaging_test_dsn /tmp/crm_gateway_venv/bin/python -m pytest tests -q`, from `crm_messaging_gateway`. Only its isolated test queue is reset.

Odoo uses `/opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin`, verified worktree addons, isolated config `/tmp/crm_chatter.conf`, targeted `-i`/`-u`, `--stop-after-init --workers=0 --max-cron-threads=0`, with explicitly selected free HTTP/gevent pairs. Reserved ports 4091/4092 were never used by temporary servers. Temporary browser servers are stopped after verification; ports 5069/5072/5073–5078/5088 are released. The original user-managed Odoo PID on 4092 is unchanged.

Known environment warnings: the existing callcenter registry reports missing constraints on `ab_sales_pos_draft_cache` and legacy model declarations. These pre-existing areas were not modified. Gateway test tooling reports a Starlette/HTTPX deprecation warning. No production-load benchmark was performed.

---

## Earlier implementation evidence

The historical report below predates this polling/controller implementation and is retained for context. The current state and blockers above supersede its deployment prerequisites and initial UI limits.

# Validation — 2026-11-04

The source implementation is verified in isolated databases. Production callcenter data was inspected read-only; no production module upgrade, public webhook registration, deployment or live provider message was performed. The user's Odoo process on port 4092 was preserved.

| Check | Evidence |
| --- | --- |
| Fresh install | `crm_workspace_final_fresh_20261104`, `-i ab_crm_sales_workspace`: 14 test methods, 0 failures, 0 errors |
| Targeted upgrade | Same isolated database, `-u ab_crm_sales_workspace,ab_crm_messaging,ab_crm_telegram`: 14 test methods, 0 failures, 0 errors |
| Existing messaging regression | `crm_messaging_validation_20261103`: 20 test methods, 0 failures, 0 errors |
| FastAPI/provider/PostgreSQL suite | 33 passed; all provider HTTP requests mocked |
| Actual concurrent claims | Two independent PostgreSQL transactions against synthetic pilot records; second claim raises Odoo `LockError` while the first holds its row lock |
| Synthetic retained-order pilot | Incoming contact, ownership check, claim, normalization, CRM contact, product, accepted revision, reopening, price/quantity changes and order history exercised |
| No submission | Synthetic pilot counts: `ab_sales_header=0`, `ab_sales_callcenter_rpc_log=0`, `ab_oms_attempt=0`; acceptance tests compare pre/post counts. Payment/stock modules are not installed in these validation databases, and the workspace has no calls into their operations |
| English browser | Workspace beside POS, conversation selection, order editing, saving, acceptance, reopening and price/history display verified; no browser console errors |
| Arabic browser | `ar_001` labels verified; workspace direction `rtl`; no horizontal overflow at 1440px; three panels and order fields inspected visually; Telegram source color `rgb(50,160,220)` and only one contacted-channel icon |
| Translations | 141 workspace terms, 17 Telegram terms and 101 messaging terms in each Arabic catalog, with no missing/fuzzy translations; `msgfmt --check-format` passed for all six files |
| Runtime language | Same action is `Sales Operations` in `en_US` and `عمليات المبيعات` in `ar_001`. Odoo maps generic Arabic to its supported `ar_001` runtime language; both source catalogs are supplied |
| Static checks | Python and XML parse, JavaScript syntax, manifest data paths, author/developer metadata, dependency ownership and production package exclusions verified |
| Source preservation | `git diff -- ab_sales ab_whatsapp_api` is empty; existing unrelated uncommitted addons and AGENTS.md retained |

Tests cover owned/third-party/typed phone evidence, exact normalization, unique/duplicate/no-match catalog results, returning identity, deduplication, unread positions, branch/company restrictions, forged employee sessions, different employees sharing an Odoo user, provider-service denial, claim conflicts, acceptance prerequisites, multiple historical orders, immutable revisions, cancellation and price auditing. The gateway suite also verifies bot identity before webhook registration.

## Reproduction and logs

Interpreter: `/opt/odoo19/venv19/bin/python`; Odoo: `/opt/odoo19/server/odoo-bin`; addons: `/opt/odoo19/server/addons,/opt/odoo19/worktrees/callcenter19`.

Private isolated configuration: `/tmp/crm_workspace.conf`. Test runs use `--stop-after-init --no-http --workers=0 --max-cron-threads=0 --http-port=5069 --gevent-port=5072`; independent messaging regression used 5073/5074. Browser validation used a tracked temporary server on 5081/5082 after the primary test runs. Agent-created browser tabs and servers were closed after validation.

- `/tmp/crm_workspace_final_fresh.log`
- `/tmp/crm_workspace_final_upgrade2.log`
- `/tmp/crm_workspace_verified.log` — final guards and 14-test result
- `/tmp/crm_workspace_messaging_regression.log`
- `/tmp/crm_workspace_browser_final.log`
- `/tmp/crm_workspace_arabic_wide.png`

Gateway command, from `crm_messaging_gateway`:

```bash
MESSAGING_TEST_DSN_FILE=/tmp/crm_messaging_test_dsn /tmp/crm_gateway_venv/bin/python -m pytest tests -q
```

Odoo runner statistics include setup/teardown (16 for the workspace); the count above uses the actual 14-method result summary. An early targeted-upgrade attempt against the separate browser-fixture database collided with its deliberately seeded test login; the final upgrade suite ran successfully on the clean validation database. Early implementation/test failures were corrected before the reported passing runs.

## Deployment prerequisites and limits

Read-only callcenter inventory found 270 stores, 62 replica records, 477,010 customers, 104,266 products, two active/ready branch RPC configurations and 91 historical RPC logs (35 success, 56 error). No raw request/response contents or credentials were inspected or exported. The production config points to this worktree and has no `db_serial` entry. CRM/OMS core and employee-access modules are installed, but the messaging account table is absent. No operational mapping was guessed or changed.

Activation requires an explicitly selected existing intake replica/default store, authorized CRM staff/service membership, protected bot/API credentials, HTTPS hostname/certificate/routing, bot identity verification, a targeted authorized deployment, and explicit live-pilot authorization. A live Telegram pilot remains unperformed. The host helper and deployment templates are prepared; real protected bot configuration and public DNS/TLS cannot be completed without those deployment inputs.

The initial UI shows the latest 100 conversations and 200 messages per selected stream. All historical records remain stored. Tests do not establish production-load performance. The gateway test tooling emits a Starlette/HTTPX deprecation warning; runtime provider requests are unaffected.

WhatsApp source review and the subsequent integration plan are in `docs/sales-operations-whatsapp-next-plan.md`. `ab_whatsapp_api` remains unchanged and unactivated by this task.

## 2026-11-08 compact Chatter (19.0.1.9.0)

- Targeted upgrade and workspace/WhatsApp bridge regressions: **76 tests passed**, zero failures/errors, on isolated `crm_whatsapp_sqlite_test_20261108` using this checkout. Log: `/tmp/chatter-compact-validation/final-regressions.log`.
- Final focused browser run: **20 tests, 63 assertions passed**. Covers compact timezone/date formatting, icon-only channels, removed helper lines, warning/retry controls, preserved message DOM identity, older-message refresh, channel preview styling/download, native keyboard-focus styling and existing RTL/draft behavior. Log: `/tmp/chatter-compact-validation/browser-final.log`.
- Added ORM coverage for latest reaction replacement/removal, reactions excluded from timeline/pagination/sidebar preview, synthetic attachment-caption suppression and retry retaining the same message/operation. Existing permission, branch/company, immutable history, uncertain-send and bounded-retry regressions pass.
- The first reaction-filter attempt excluded ordinary sends without incoming events; the regression exposed this and the final domain uses explicit `not any`. The CSS test uses native keyboard focus because synthetic hover events do not activate browser pseudo-classes.
- English, `ar`, and `ar_001` runtime checks passed for the new field and retry label, including Arabic frontend translation delivery and RTL locale direction. Both catalogs pass gettext format checks. Python/XML parsing and whitespace checks pass.
- All 202 protected-addon hashes remain unchanged. Existing unrelated work and the WhatsApp bridge source are preserved. Runtime packaging omits Python/browser tests and test asset declarations; artifact: `/tmp/chatter-compact-validation/ab_crm_sales_workspace-19.0.1.9.0.tar.gz`.
- Validation uses alternate ports 5069/5072 with zero workers/cron threads and stop-after-init. The live Odoo/gateway processes and database were not upgraded or restarted. No real provider sends were made. Apply the module through the normal runtime upgrade/reload workflow to load the changes there.
