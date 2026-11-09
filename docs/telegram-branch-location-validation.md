# Telegram branch locations — implementation and validation

Implemented on `callcenter19` on 2026-11-08. Existing uncommitted messaging/UI work was preserved. The storefront was read for comparison only. No live database upgrade, gateway activation, webhook change, process restart or provider test send was performed.

## Delivered behavior

- `ab_crm_sales_workspace` **19.0.1.13.0** owns the company/fulfillment-store directory, review/activation, archive workflow, revisioned configuration history, CSV validation and branch sharing APIs.
- CRM conversation forms, OMS request forms, channel-order dialogs and Telegram chatter use the same scoped picker. Forms and order dialogs retain unsaved edits; the composer retains text, attachments and reply state. Current fulfillment stores are preselected where available. Navigation invalidates the picker; keyboard dismissal returns chatter focus to Attach.
- **Send location** queues one native Telegram venue. **Send branch details** separately queues the displayed name/address/verified phones/labelled hotline. English, `ar`, and `ar_001` previews support visible fallback. No WhatsApp location sending is enabled.
- `ab_crm_messaging` **19.0.1.6.0** includes optional location in immutable outgoing content. Coordinates, language, profile revision, source/reviewer, actor/employee and timestamp are frozen. Authenticated delivery reporting can attach the provider receipt once. Retries use the frozen content after directory edits.
- Gateway **1.3.0** dispatches [`sendVenue`](https://core.telegram.org/bots/api#sendvenue), preserving existing receipt, retry and uncertain-delivery handling. It rejects invalid points and incompatible media/reaction/template/contact payloads before transport.
- Configuration is manager/admin-only with company rules. Staff cannot read raw configuration through ORM/RPC: the directory APIs validate employee session, authorized conversation/assignment, company, allowed fulfillment stores and review state before scoped elevation. Sends reject stale revisions and conflicting idempotency-token reuse.
- All configuration and sharing actions retain actor/time evidence. Directory mappings are fixed after creation; content updates require another review. No routing, inventory, synchronized store fields or delivery details are changed by sharing a branch.

## Data and activation

`ab_crm_sales_workspace/resources/branch_locations_staging.csv` contains **42 bilingual rows in nine regions**, with distinct keys/coordinate pairs and the shared **19036** hotline. Individual public phones, company and fulfillment store codes are deliberately blank. These are comparison records, not authoritative live configuration. No profiles were installed or activated automatically. See `resources/branch_locations.md` for the import/review procedure.

Activation remains separate: upgrade Odoo consumers first, deploy gateway support, then explicitly enable gateway `accounts.<code>.location_enabled` and the matching Odoo account's **Telegram Branch Locations Enabled**. Both default to disabled. Existing global/account sending switches still apply. Authoritative store mappings, public-phone verification and profile review remain prerequisites for real use.

## Verification evidence

Artifacts and private test configuration are under `/tmp/branch-validation`; credentials/configuration are excluded from distribution packages.

| Check | Result | Evidence |
| --- | --- | --- |
| Gateway regression suite, PostgreSQL and SQLite | **157 passed, 1 skipped**; FFmpeg-dependent voice conversion skipped because FFmpeg/ffprobe are absent. Provider requests mocked. | `gateway-complete.log` |
| Fresh Odoo install | Passed, 44 modules loaded, only the requested addon and its dependencies installed. | `fresh-final.log` |
| Final targeted upgrade and full workspace suite | **77 test methods passed**, zero failures/errors, including import, stale preview, idempotency, assignments/company/store isolation, receipt assignment, frozen failed-send retry, uncertain-send denial and existing order/location/media regressions. | `final-suite.log` |
| Messaging/controller suite | **26 test methods passed**, zero failures/errors. Incoming locations and existing text/media/status workflows retained. | `messaging-final.log` |
| Browser components | **37 tests, 223 assertions passed**; final preview/focus adjustment rechecked. | `browser-release.log` |
| Runtime languages | English, `ar`, `ar_001` field labels, frontend terms and branch preview language verified; existing translations preserved, both catalogs pass gettext format checks. | `languages.log`, helper stdout |
| Full application UI | All **nine** locale/viewport combinations at **1440, 768, 390px** passed. Native preview, details, phone display, LTR coordinates, bounds, keyboard focus, cancellation, outgoing card without delivery action, composer/order drafts and CRM/OMS unsaved form edits checked. | `ui-final.log`, `native-*.png`, `picker-*.png` |

Databases: `crm_branch_test_20261108` (synthetic persistent UI fixtures), `crm_branch_final_test_20261108` (clean install/upgrade and workspace tests), `crm_branch_messaging_test_20261108` (isolated messaging). Validation used HTTP/gevent pairs **5069/5072**, **5075/5076**, **5077/5078**, with workers and cron disabled. No live HTTP was exposed externally. The reserved 4092 process was not stopped or restarted.

Initial failures led to early nonfinite-coordinate validation and a safe fallback when a requested language is not installed. Test-environment corrections included the existing temporary websocket dependency, exclusion of unrelated POS registry patches within browser test transactions, exact test-database HTTP routing, complete synthetic OMS fixtures, and browser assertions matching the final preserved-line-break preview. All reported final runs passed; earlier failed attempts are retained in the evidence directory. Fresh-install evidence and final test evidence are listed separately rather than treating the interrupted initial HTTP test routing attempt as a passing suite.

Runtime packaging excludes addon tests, static test assets, caches and local configuration. The gateway's required queue schema migrations remain included. A task-only patch is generated against the initial worktree snapshot so reviewers can distinguish these changes from pre-existing work.

Cleanup verified: all temporary HTTP/gevent ports are released. The original PyCharm-managed Odoo process remains listening on 4092 with PID 720461. Runtime and review archives are `/tmp/branch-validation/telegram-branch-locations-runtime.tar.gz` and `/tmp/branch-validation/telegram-branch-locations-review.tar.gz`.
