## b7584edd9e31bce6a1059665677c5cf62885e865 - emadco88 - 2026-10-12

Original commit subject: ab_sales/ fix multi-tab flickering with selective draft restoration

User-facing changes:
- Keep automatic backups separate from explicit restoration into each POS window.
- Add the New Bill/Restore Draft dialog and protected draft removal.

Files changed:
- ab_sales/changelog.d/2026-10-12-draft-slots.md
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/models/ab_sales_pos_draft_slots.py
- ab_sales/static/src/pos/pos_action.js
- ab_sales/static/src/pos/pos_action.xml

## Current changes before commit:

- Store one draft per stable, unique POS client token, with individual revisions, ownership, branch validation, and retained retirement/completion markers.
- Keep store-only Ready bills local. Back up meaningful Used bills automatically; clearing an ordinary saved bill to Ready retires the saved record and gives the local replacement a new identity.
- Share concurrent startup loading, reconcile only the current window's tokens, and ignore responses from an old employee session. Creating a Ready bill no longer performs a draft-cache save.
- Make repeated saves idempotent, report revision conflicts, and serialize only new capacity admissions through a small employee-scope revision marker. Preserve the configurable `ab_sales.pos_draft_limit` with ten as its fallback; do not evict existing excess drafts.
- Preserve local edits on failures, conflicts, and capacity rejection. Add explicit conflict resolution and a persistent backup status/retry control outside the collapsible sidebar; retry transient failures at 1, 2, and 5 seconds.
- Exclude live stock/display refresh metadata from edit comparison. Keep invoice-linked and unresolved submissions protected, and keep submission recovery in its dedicated status API.
- Restrict ordinary access to validated draft APIs instead of exposing other PIN employees' records through a shared Odoo user. Validate employee ownership in the no-PIN fallback too.
- Remove invalid legacy/incomplete draft cache records in batches on every installation or upgrade through an XML function (no `init()` override). Require owner, employee, store, token, and a structurally valid matching bill payload; preserve valid lifecycle records and log deletion counts by reason.
- Quietly skip incomplete server backups, retaining local bills without warnings or unchanged-payload retry loops; recheck after data or session changes without claiming backup success. Keep invalid-session, branch, and sales-prevention guards.
- Add English/Arabic text pairs in both catalogs. Bump the module to 19.0.2.0.0 for the per-draft schema restructuring; invalid old rows are now explicitly discarded on upgrade rather than converted. No manifest lifecycle hook is included.

Verification:
- Re-ran the ten backend regressions and eight frontend checks after cleanup changes. Playwright confirmed employee 164 can reload after two seconds with no warnings and enabled new-bill slots on the isolated database.
- Added cleanup verification: actual targeted upgrades with missing owner/employee/store/token/payload rows removed them, preserved three valid lifecycle states, and removed zero records on the repeated upgrade. Payload structure/mismatch checks and quiet missing-employee APIs passed.
- Added frontend verification for quiet skipped backups, local retention, no false acknowledgement, no unchanged-payload retries, and eligibility after edits/session changes. No user-facing strings were added by cleanup; both Arabic catalogs still pass format checks.
- Clean installation and targeted upgrades passed on isolated databases. The original development database and its existing draft records were preserved; no external invoice posting was performed.
- Ten backend scenarios passed: Ready/list behavior, idempotency, revision conflicts, retirement, capacity, removal, branch validation, submission protection, generic-model ACLs, and employee isolation.
- The installed sales-prevention module blocked all five draft APIs; the no-PIN fallback rejected other employees while accepting the caller’s linked employee.
- Three concurrent database scenarios passed: simultaneous duplicate creation, conflicting edits, and admission against a shared configured limit.
- Seven focused frontend checks passed for in-flight edits, selective restoration, retirement races, session changes, conflict dismissal/reload, and shared initialization.
- Six Playwright scenarios passed with employee 164: repeated two-second reloads, automatic Used backup, explicit two-window restore, conflict resolution, clear-to-Ready retirement, and bounded network retries with successful manual recovery. New slots remained enabled while backup was unavailable.
- Odoo POT export and Arabic form/model/web-translation runtime checks passed. Both PO files passed `msgfmt --check-format`.
- Diagnostic scripts and browser reports are outside the addon under `/opt/playwright/tasks/replica_addons/draft-records/` and `/opt/playwright/artifacts/replica_addons/draft-records/`.

Files changed:
- ab_sales/__manifest__.py
- ab_sales/data/pos_draft_cleanup.xml
- ab_sales/models/ab_sales_pos_api.py
- ab_sales/models/ab_sales_pos_draft_cache.py
- ab_sales/models/ab_sales_pos_draft_slots.py
- ab_sales/security/ir.model.access.csv
- ab_sales/static/src/pos/pos_action.js
- ab_sales/static/src/pos/pos_action.xml
- ab_sales/i18n/ar.po
- ab_sales/i18n/ar_001.po
- ab_sales/changelog.d/2026-10-17-draft-records.md
