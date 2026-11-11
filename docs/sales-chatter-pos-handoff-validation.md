> Historical feature and validation record. The [2026-11-11 retirement report](messaging-legacy-retirement.md) records the completed rollout and supersedes earlier pending-maintenance and historical-receipt backlog statements below.

# Sales Chatter Inbox and POS handoff — 2026-11-10

## Scope and implementation

Source: `/opt/odoo19/worktrees/callcenter19`, branch `callcenter19`.
Versions: `ab_crm_core` 19.0.1.1.0; `ab_crm_sales_workspace` 19.0.1.26.0.

CRM owns contact details, multiple phones and channel identities. `catalog_customer_id` remains the explicit reference to the registered POS customer; `is_ab_customer` is computed from that relationship. CRM saving and archival do not register or edit the core customer. Local POS suggestions do not initiate branch lookup. The explicit phone lookup uses the existing POS API and validates the selected branch before calling it.

The old Orders action ID and action tag resolve to Inbox. The menu formerly used for Orders now starts Create order. Legacy order-dialog assets are excluded from the backend bundle, and the old delivery chooser and workspace order state/loading are removed. Historical OMS models, records and APIs are retained. Previously modified order-dialog source files are preserved as inactive source.

The CRM POS action subclasses the registered POS component, retaining its template and native methods. It waits for authentication and native draft readiness, validates the originating employee, obtains details through RPC, creates a separate native draft, reserves the handoff, applies prefill once and persists through the native cache. The handoff/action carries record identifiers only; personal details and authentication tokens are not placed in URLs. Selected phone/location details remain editable invoice fields.

Relationship synchronization reads the selected ID from the employee-owned native draft or resulting invoice, checks contact/customer/branch/company access, and writes an audit with old/new values, user, employee and timestamp. Retry performs CRM synchronization only. Completed or saved drafts do not cause an automatic second invoice. Draft recovery remains owned by POS.

## Verification

Isolated database: `callcenter_pos_handoff_test_20261110`, cloned from an existing test database. Private configuration: `/tmp/sales-chatter-test.conf`. Interpreter: `/opt/odoo19/venv19/bin/python`; server: `/opt/odoo19/server/odoo-bin`. Addons paths match the callcenter runtime. HTTP/gevent ports: 5069/5072; workers and cron threads: zero. Tests stop after initialization and temporary HTTP servers are shut down.

Browser support uses pinned `websocket-client==1.8.0` only under `/tmp/sales-chatter-test-deps`; the user's Odoo environment is unchanged. External branch requests are mocked in full application checks; tests do not create external customers or submit invoices.

Passing evidence:

- 94 existing Python workspace regression tests, including archival, historical orders, permissions, messaging, multiple numbers and explicit catalog suggestions: `/tmp/sales-chatter-final.log`.
- Eight focused handoff server tests (102 backend tests in total): `/tmp/sales-chatter-handoff-final.log`.
- 72 HOOT tests, 436 assertions, including 10 new handoff tests: `/tmp/sales-chatter-browser-final.log`.
- Two full-asset application tests, English and Arabic: Inbox/Create order/Invoices labels, unchanged native POS authentication and registration, and existing Bill Wizard rendering: `/tmp/sales-chatter-final.log`.
- Targeted upgrades of CRM core and workspace; dependent CRM modules loaded normally. No `-u base`.
- Python/XML/JavaScript syntax, manifest/import checks, exact POT references, both Arabic gettext format checks and preserved previous translations.
- Protected modules have no source diff. No product, stock, pricing, customer-master or historical-order deletion/update operations were introduced.

Earlier logs record fixture/test-harness failures and the issues fixed before the passing runs: required customer codes in fixtures, browser dependency and readiness, explicit catalog-selection expectations, branch validation before fallback, Arabic JavaScript translation markers, and optional action context in component fixtures. The combined run's only remaining failure was its browser wrapper; the subsequent browser-only run passed all 72 tests. It is not reported as a fully passing combined run.

Runtime packages exclude tests, test assets and Python caches. Package checksums are in `/tmp/sales-chatter-release/SHA256SUMS`.

## Live activation — maintenance window confirmed

The user confirmed the callcenter PyCharm process was stopped. Ports 4092, 5069 and 5072 were checked before activation. A PostgreSQL custom-format backup, filestore copy and previous versions of both CRM source modules are at `/tmp/sales-chatter-live-backup-20261110-163730`.

The targeted `ab_crm_core,ab_crm_sales_workspace` live upgrade completed with exit code zero and no ERROR/CRITICAL entries in `/tmp/sales-chatter-live-upgrade.log`. Existing unrelated schema warnings about nullable native draft-cache fields and stale optional model metadata were retained; protected modules were not upgraded or modified.

Post-upgrade read-only registry checks confirmed installed versions 19.0.1.1.0 / 19.0.1.26.0, the readonly computed customer status, legacy action redirect, native Bill Wizard action and POS adapter asset inclusion. Legacy order-dialog assets are absent from the runtime backend bundle.

Odoo initially retained the old Arabic menu values. A scoped overwrite import containing only Inbox, Create order and Invoices corrected these model translations. Exact live menu checks now pass in English and the installed Arabic locale `ar_001`; standalone `ar` is not installed on live, and its source catalog was validated without installing a new language. Full English/Arabic application rendering passed on the isolated database.

The upgrade process exited and released its temporary ports. The user confirmed the PyCharm reload and browser refresh. The reloaded process (PID 1103105) listens on port 4092, loaded the callcenter registry successfully, and serves the login page with HTTP 200. Successful asset requests were recorded, with no ERROR/CRITICAL entries in the inspected startup log. Ports 5069 and 5072 are released. The user's process was not stopped or restarted by the agent.

No real external customer creation or invoice submission was performed. Those operations continue through the unchanged POS workflow. No bulk contact conversion or customer-master edits were performed.
