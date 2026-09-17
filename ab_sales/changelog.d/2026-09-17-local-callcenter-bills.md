# ab_sales: local callcenter bills

## Recent commit

Commit: `0a49e3d65783810874090f6419609e981d940d86`

Author: Hossam Elsheikh

Date: 2026-09-17T10:53:37+03:00

Original commit subject: ab_sales/bills search only shows callcenter created bills

- Restricted branch bill browsing to callcenter-origin records and refreshed submission-log statuses.

Files changed:

- `ab_sales/BRANCH_API_WORKFLOW.md`
- `ab_sales/__manifest__.py`
- `ab_sales/changelog.d/2026-09-17-callcenter-only-bills.md`
- `ab_sales/changelog.d/2026-09-17-callcenter-order-status.md`
- `ab_sales/i18n/ar.po`
- `ab_sales/i18n/ar_001.po`
- `ab_sales/models/__init__.py`
- `ab_sales/models/ab_sales_branch_rpc_config.py`
- `ab_sales/models/ab_sales_header.py`
- `ab_sales/models/ab_sales_pos_api.py`
- `ab_sales/models/branch_bills.py`
- `ab_sales/models/branch_services.py`
- `ab_sales/models/callcenter_origin.py`
- `ab_sales/static/src/bill_wizard/bill_wizard_action.js`
- `ab_sales/views/ab_sales_branch_api_views.xml`

## Current changes before commit:

- Preserve the original submission error alongside recovery failures; avoid the misleading blanket advice that the branch must be unavailable. Pair with branch 19.0.5.3.1's zero-serial recovery fix and detailed conflict diagnostics.

- Recover failed sale/return responses through the branch reconciliation API. Retrieve confirmed results with the same token/payload; preserve drafts during outages and the original error after proven rollback. Require the new advertised branch capability and bump to 19.0.3.4.1.

- Fix branch submission rejection by excluding local status from the sale API payload. Correct previously rejected cached requests on manual retry without changing tokens, items, prices or branch identity.

- Save local sales headers, customer snapshots, lines and original submission requests before branch calls; preserve offline drafts and retry the same request/token manually.
- Keep request contents and original prices unchanged across retries, including later product price changes; delegate uncertain-outcome reconciliation to the branch API before retrying.
- Read sales and returns locally in Bill Wizard, including drafts, details and printing. Open Bills and Sales Return as separate native tables.
- Refresh only Pending sales by branch/database identity and eplus_serial, updating only status. Retain local values on outages, missing rows and invalid replies; isolate failures by branch.
- Enable the existing status cron at a five-minute interval on module upgrade; add explicit search refresh without branch calls during pagination or detail browsing.
- Enforce local header/line branch rules, invalidate permission caches on reassignment, and allow manager/admin access within server-authorized branches.
- Preserve return submission snapshots in the successful transaction; archive local bills and keep archived returns in receipt arithmetic.
- Replace remote search sessions with local pagination, remove the obsolete transient ACL, update workflow documentation, and maintain both Arabic translation files.

Files changed:

- `ab_sales/BRANCH_API_WORKFLOW.md`
- `ab_sales/__manifest__.py`
- `ab_sales/changelog.d/2026-09-17-local-callcenter-bills.md`
- `ab_sales/data/ir_cron.xml`
- `ab_sales/i18n/ar.po`
- `ab_sales/i18n/ar_001.po`
- `ab_sales/models/__init__.py`
- `ab_sales/models/ab_sales_branch_api_client.py`
- `ab_sales/models/ab_sales_branch_rpc_config.py`
- `ab_sales/models/ab_sales_header.py`
- `ab_sales/models/ab_sales_pos_api.py`
- `ab_sales/models/ab_sales_ui_api_bill_wizard_inherit.py`
- `ab_sales/models/branch_bills.py`
- `ab_sales/models/branch_services.py`
- `ab_sales/models/local_bills.py`
- `ab_sales/security/ir.model.access.csv`
- `ab_sales/security/local_bill_rules.xml`
- `ab_sales/static/src/bill_wizard/bill_wizard_action.js`
- `ab_sales/static/src/bill_wizard/bill_wizard_action.xml`
- `ab_sales/static/src/bill_wizard/local_bill_list.js`
- `ab_sales/views/ab_sales_return.xml`
- `ab_sales/views/local_bill_views.xml`
- `ab_sales/views/sales_header.xml`

Validation:

- Verified original and recovery errors survive the real callcenter adapter and local-draft path; branch regression uses the actual SQL predicate with a zero-ID sentinel. New message passes both Arabic PO checks and runtime translation. Latest scripts: `/tmp/branch_recovery_diagnosis`.

- Targeted disposable-database upgrade and real callcenter ORM tests with mocked branch transport: lost-response recovery, exact token/payload replay, original-error preservation after rollback, offline/busy draft retention, payload mismatch and foreign branch rejection. No callcenter SQL access or blind resubmission.
- New recovery messages translated in both Arabic files; runtime Arabic message/form and five-minute cron verified. Recovery scripts/results: `/tmp/branch_reconciliation_validation`.

- Reproduced `Unsupported sale field: status` with the branch provider's actual field validator; verified corrected new submissions and cached-request retries on the isolated database. Automatic recovery tests supersede the earlier uncertain-operation preflight rejection.

- Targeted ab_sales upgrade on disposable database `codex_callcenter_local_bills`; no deployed database upgrade or external database writes.
- Mocked branch transport with real ORM checks for offline browsing/printing, durable product-line drafts, manual retry, duplicate requests, identity validation, 201-bill batching, missing/invalid rows, later-batch rollback, and cross-branch access.
- Verified reassignment and inherited admin access, refresh-before-status filtering, frozen pricing, uncertain-outcome safeguards, cron activation/interval, and Arabic form/field translations.
- Odoo JavaScript asset compilation; native-list search/pagination/failure/race checks; Python/XML/JS syntax, PO format, and git diff checks.
- Validation scripts and outputs remain outside the addon in `/tmp/callcenter_local_bills_validation`.

Deployment: deploy and target-upgrade branch ab_branch_api 19.0.5.3.1 first, then
callcenter ab_sales 19.0.3.4.1; restart the corresponding workers and retest Branch
Connections. Live deployment has not been performed.
