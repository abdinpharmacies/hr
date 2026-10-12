## d69c7c2c3adaaf4166bb66e1b9631f6a76c1f95e - emadco88 - 2026-10-12

Original commit subject: ab_sales/ FIX locking bill only on no return

User-facing changes:
- Keep cache-only bills as Draft and distinguish editable PrePending from locked, unresolved submission outcomes.
- Preserve invoice identities and reconcile server-confirmed Pending/Saved results without repeating stock changes.

Files changed:
- ab_sales/models/ab_sales_header.py
- ab_sales/models/ab_sales_line.py
- ab_sales/models/ab_sales_pos_api.py
- ab_sales/static/src/pos/pos_action.js
- ab_sales/static/src/pos/pos_action.xml
- ab_sales/views/sales_header.xml
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/changelog.d/2026-08-30-item-type-filters.md

## 73da4b14224601238f515da837e7e5ee292c1f0b - emadco88 - 2026-10-11

Original commit subject: ab_sales/ FIX delete empty bills

User-facing changes:
- Verify branch access, original submission work, invoice lines and external identity before discarding attempted empty drafts.
- Retain unsafe drafts and report deleted/retained counts for single and bulk removal.

Files changed:
- ab_sales/models/ab_sales_pos_api.py
- ab_sales/static/src/pos/pos_action.js
- ab_sales/static/src/pos/pos_action.xml
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/changelog.d/2026-08-30-item-type-filters.md

## Current changes before commit:

User-facing changes:
- Configure the employee draft pool using `ab_sales.pos_draft_limit`, defaulting to 10. Reconcile browser/server caches, retain the newest eligible drafts and keep locked work outside the pool.
- Distinguish numbered Empty slots (choose a branch), Ready slots (branch selected, blank bill) and Used slots (entered customer, lines or other bill data), with separate branch badges and capacity counters.
- Replace a confirmed Pending/Saved bill with a fresh Ready bill in the same available slot and branch, clearing customer, contract, delivery, search and line data and renewing its submission identity. Resolving a locked bill never evicts another draft when the pool is full.
- Delete Ready/Used bills from both caches and clear their branch. Delete All clears every removable slot while preserving protected invoices. Permanent removal markers and revisions prevent stale tabs from restoring deleted work.
- Suggest the permitted replica default branch, falling back to the first permitted sales branch. Preserve employee, service-user and replica restrictions; selecting an Empty slot creates no bill until branch confirmation.
- Treat blank branchless bills as Empty and reuse their slot on branch selection. Preserve branchless bills with entered data as Used.
- Serialize employee cache writes, preserve in-flight edits and retain local work on synchronization failures. Reconcile confirmed submissions without replaying the sale or falsely reporting a failed submission.
- Compare relational fields by numeric IDs when checking harmless no-op writes on locked invoices, allowing the employee wrapper to complete its audit while blocking real invoice edits.
- Maintain English source labels and both Arabic catalogs; keep development harnesses outside the runtime addon.

Verification:
- 23 rollback-only backend checks passed for branch defaults and access restrictions, same-slot Ready recovery, fresh identity and cleared data, repeated recovery, full-pool protection, deletion, stale snapshots and Delete All.
- Seven frontend checks passed for state classification, successful submission and cache-failure recovery, branch selection defaults, no permitted branches and branchless Empty-slot reuse.
- Six headed Playwright scenarios passed on an isolated database for Empty/Ready/Used layout, branch confirmation, customer-only Used bills, deletion/reload, confirmed Pending recovery and Delete All, with no browser errors. External submission was blocked.
- 26 earlier rollback-only checks passed for the employee-access submission wrapper and locked-invoice relational no-op fix. No additional live sale was submitted during lifecycle verification.
- Targeted module upgrades, JavaScript/Python/XML parsing and both Arabic catalog format checks passed. Arabic headed-browser checks verified translated state labels, counters and branch prompts without JavaScript errors.

Files changed:
- ab_sales/__manifest__.py
- ab_sales/data/pos_draft_limit.xml
- ab_sales/models/__init__.py
- ab_sales/models/ab_sales_pos_draft_cache.py
- ab_sales/models/ab_sales_pos_draft_slots.py
- ab_sales/models/ab_sales_header.py
- ab_sales/security/ir.model.access.csv
- ab_sales/static/src/pos/pos_action.js
- ab_sales/static/src/pos/pos_action.scss
- ab_sales/static/src/pos/pos_action.xml
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/changelog.d/2026-08-30-item-type-filters.md
- ab_sales/changelog.d/2026-10-12-draft-slots.md
