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

## f95f158b6856eef96b4c0d439003dcc21512aef7 - emadco88 - 2026-10-12

Original commit subject: ab_sales: add configurable POS draft slots and fix submission recovery

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

## 148b8cf0767dcc9279dd791142ff861fc2346888 - emadco88 - 2026-10-12

Original commit subject: ab_sales/ UPD remove redundent create new bill button, as you can create new bill by clicking the empty slot, or you can use ready slot

User-facing changes:
- Remove the redundant sidebar New Bill / + button in expanded and collapsed layouts. Create bills by selecting a numbered Empty slot.
- Keep the central Create Bill button and existing branch selection, slot limits and deletion behavior.
- Remove styles used only by the removed sidebar button. No new or changed source strings; existing Arabic translations are preserved.

Verification:
- Seven headed browser scenarios passed on the isolated database, including branch-picker cancellation, exact-slot creation, Ready/Used selection, deletion and full capacity. Sidebar button absence was verified in expanded/collapsed English and Arabic layouts; no browser errors occurred.
- XML structure checks retain the Empty-slot and central Create Bill controls. Both Arabic catalogs pass format validation; no source strings were added or changed.
- Targeted local `ab_sales` upgrade completed successfully. No live sale or production deployment was performed.
- Screenshots and reports: `/opt/playwright/artifacts/replica_addons/remove-new-bill/`.

Files changed:
- ab_sales/static/src/pos/pos_action.xml
- ab_sales/static/src/pos/pos_action.scss
- ab_sales/changelog.d/2026-10-12-draft-slots.md

## Current changes before commit:

User-facing changes:
- Open New Bill / Restore Draft tabs from an empty slot. Restore one saved draft into the clicked slot without changing its identity or opening unrelated drafts.
- Show saved draft branch, customer, items, total, update time and lock status. Prevent duplicate restoration of already-open bills; provide confirmed individual and bulk deletion with protected invoices retained.
- Keep automatic saving while separating per-tab workspaces from the shared saved draft pool. Reload resumes the tab's local bills; other saved bills are opened explicitly through the restore dialog.
- Remove storage-event blanket locks and save/response feedback. Save changed bills, preserve typing during requests, and retain local drafts on failures or capacity rejection without a retry loop.
- Keep submission safety signals, deletion tombstones, branch/employee scope, server slot limits and own-bill completion recovery. Remote deletion of another bill preserves the selected bill's inputs.
- Add scoped single-draft restore validation and completion replacement identifiers to cache responses; no schema changes, hooks or external database writes.
- Add English source labels and Arabic translations in both catalogs, including accessible deletion tooltips.

Verification:
- 13 focused frontend checks passed for save acknowledgment, in-flight edits, selective restore, duplicate prevention, independent slot mapping, failures, session changes, deletion and completion safety.
- Eight rollback-only backend checks passed for restore identity, protected submissions, bulk deletion, tombstones, stale revisions, capacity and branch/user/employee access boundaries.
- Seven English browser scenarios and an Arabic RTL dialog check passed on `codex_pos_lifecycle_clean_20261012`; no browser errors. Multi-tab verification confirmed no automatic pulls or repeated save loop. External submission was blocked during English browser tests.
- Targeted `ab_sales` upgrades completed on the isolated database; logs retain the pre-existing unavailable `ab_hr_effects` dependency report. No production database upgrade or live sale was performed.
- Exported the Odoo 19 module POT, appended missing Arabic entries without rewriting unrelated translations, and passed both `msgfmt --check-format` checks. English/Arabic menu differences and Arabic dialog labels/tooltips were verified at runtime.
- Python/JavaScript/XML parsing and `git diff --check` passed. Test harnesses and reports remain outside the production addon under `/opt/playwright/tasks/replica_addons/manual-draft-restore/` and `/opt/playwright/artifacts/replica_addons/manual-draft-restore/`.

Files changed:
- ab_sales/models/ab_sales_pos_draft_slots.py
- ab_sales/static/src/pos/pos_action.js
- ab_sales/static/src/pos/pos_action.xml
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/changelog.d/2026-10-12-draft-slots.md
