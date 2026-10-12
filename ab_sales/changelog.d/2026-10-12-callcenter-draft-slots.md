# Callcenter draft slots and bill-lock recovery

## Source commits reviewed (pos19)

- Commit: `f1b069027a4c9de79473ac4f809695a6972760c2`
- Author: emadco88
- Date: 2026-10-11 17:45:41 +0300
- Original commit subject: ab_sales/ FIX flickering on mutli tabs
- Stop unchanged status refreshes from echoing browser cache events.

Files changed (relevant excerpt):
- `ab_sales/static/src/pos/pos_action.js`

- Commit: `73da4b14224601238f515da837e7e5ee292c1f0b`
- Author: emadco88
- Date: 2026-10-11 18:30:05 +0300
- Original commit subject: ab_sales/ FIX delete empty bills
- Remove eligible draft cache entries while retaining unresolved invoices.

Files changed (relevant excerpt):
- `ab_sales/models/ab_sales_pos_api.py`
- `ab_sales/static/src/pos/pos_action.js`
- `ab_sales/static/src/pos/pos_action.xml`

- Commit: `d69c7c2c3adaaf4166bb66e1b9631f6a76c1f95e`
- Author: emadco88
- Date: 2026-10-12 06:00:11 +0300
- Original commit subject: ab_sales/ FIX locking bill only on no return
- Distinguish safe preparation failures, active submission, and uncertain outcomes.

Files changed (relevant excerpt):
- `ab_sales/models/ab_sales_header.py`
- `ab_sales/models/ab_sales_line.py`
- `ab_sales/models/ab_sales_pos_api.py`
- `ab_sales/static/src/pos/pos_action.js`

- Commit: `f95f158b6856eef96b4c0d439003dcc21512aef7`
- Author: emadco88
- Date: 2026-10-12 10:18:02 +0300
- Original commit subject: ab_sales: add configurable POS draft slots and fix submission recovery
- Add employee draft limits, numbered Empty/Ready/Used slots, and revision-aware deletion.
- Preserve branch selection with a fresh draft identity after confirmed submission.

Files changed (relevant excerpt):
- `ab_sales/models/ab_sales_pos_draft_slots.py`
- `ab_sales/models/ab_sales_pos_draft_cache.py`
- `ab_sales/data/pos_draft_limit.xml`
- `ab_sales/static/src/pos/pos_action.js`
- `ab_sales/static/src/pos/pos_action.xml`
- `ab_sales/static/src/pos/pos_action.scss`

## Current changes before commit:

- Adapt the source behavior to the existing callcenter branch API and durable local invoice workflow; retain frozen retry payloads, tokens, and request revisions.
- Configure editable draft slots through `ab_sales.pos_draft_limit`, default 10; show Empty, Ready, Used, locked, and protected overflow bills separately.
- Keep the newest editable drafts when reducing the limit. Discard excess cache-only contents from `ab_sales_pos_draft_cache` and browser storage, with deletion markers preventing stale-tab restoration. Never delete persisted invoices.
- Replace confirmed submissions once, server-side, with a fresh Ready draft for the same branch when capacity permits. Clear customer, contract, product, and submission identity data.
- Add branch-options and removal APIs; extend cache load/save responses with revision, slot limit, deletion markers, and authoritative lock/removal information. Enforce user, employee, and branch scope; restrict direct cache access to administrators.
- Remove cache feedback loops, coalesce status reads, preserve unsent edits and object identity, ignore older cache responses, and force fresh recovery reads after submission errors.
- Expose actual submission progress and attempted state; restore editing after safe failures or explicit rejection while retaining ambiguous locks. Accept harmless Many2one no-op writes on locked invoices.
- Merge new English/Arabic UI strings into both Arabic catalogs using an Odoo-exported POT.
- Fix standard POS Manager and Salesperson roles being rejected because their screen-based permission payload omits `allow_sale`. Share the session check between draft cache and submission status APIs, preserving explicit custom denial, session ownership, and branch restrictions.
- Display the actual authorization failure in a persistent banner, preserve local bills, stop authorization retry loops, and provide Retry draft sync for recovery. Ignore responses from a previously selected employee scope.

Files changed:
- `ab_sales/models/ab_sales_pos_api.py`
- `ab_sales/__manifest__.py`
- `ab_sales/models/__init__.py`
- `ab_sales/models/ab_sales_pos_draft_cache.py`
- `ab_sales/models/ab_sales_pos_draft_slots.py`
- `ab_sales/models/local_bills.py`
- `ab_sales/data/pos_draft_limit.xml`
- `ab_sales/security/ir.model.access.csv`
- `ab_sales/static/src/pos/pos_action.js`
- `ab_sales/static/src/pos/pos_action.xml`
- `ab_sales/static/src/pos/pos_action.scss`
- `ab_sales/i18n/ar.po`
- `ab_sales/i18n/ar_001.po`
- `ab_sales/changelog.d/2026-10-12-callcenter-draft-slots.md`

## Verification

- Isolated callcenter database copy; targeted `ab_sales` upgrade, with external branch calls blocked or stubbed and cron workers disabled.
- Backend checks cover limits, overflow, cache deletion, concurrent access, employee/branch separation, persisted invoice protection, active locks, safe failures, timeout recovery, frozen retries, and duplicate prevention.
- Frontend method checks cover stable object identity, in-flight typing, stale response rejection, transient state exclusion, coalesced refreshes, and fresh submission recovery reads.
- Headless Playwright checks cover rendered slot transitions, duplicate-tab synchronization and deletion, validation/ambiguous/rejected/confirmed outcomes, and Arabic rendering with a configured seven-slot limit. Duplicate tabs settle with zero follow-up RPC calls over three seconds; three unchanged status refreshes produce zero slot DOM mutations and no browser errors.
- Arabic catalogs pass `msgfmt --check-format`; POS action differs at runtime between `en_US` and `ar_001`.
- Harnesses and reports: `/opt/playwright/tasks/callcenter19/pos-slots/` and `/opt/playwright/artifacts/callcenter19/pos-slots/`.
- Follow-up regression checks cover standard screen-based roles (the original fixtures used custom permissions), explicit permission denial, invalid/locked/foreign sessions, unauthorized branches, reload, employee cache separation, visible authorization failure, retained local drafts, and manual retry recovery.
- Follow-up results: eight backend cases and sixteen headless browser cases passed, with no browser errors. Arabic runtime errors and the retry button were also verified. Reports: `/opt/playwright/artifacts/callcenter19/slot-role-fix/`.
- Live callcenter database and PyCharm-managed processes were not upgraded or restarted.
