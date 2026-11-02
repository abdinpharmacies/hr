# Final implementation validation — 2026-11-01

The five implementation phases are complete. All eight review findings have verified corrections. [REQUIREMENTS.md](REQUIREMENTS.md) maps each supplied requirement to implementation and evidence. Earlier baseline evidence is retained below as historical context; the results in this section apply to the completed changes.

## Scope and environments

- Source: `/opt/odoo19/worktrees/rip_bconnect`, branch `branch19`. The pre-existing `AGENTS.md` modification and unrelated files were preserved. Changes are confined to this addon and `/tmp/ab_inventory_audit_validation`.
- Core upgrades/tests: `codex_inventory_audit_20261101`; optional native integration tests: `codex_inventory_audit_integrations_20261101`.
- Clean installations: `codex_audit_complete_clean_20261101` and final `codex_audit_release_clean_20261101`. The addon path was `/opt/odoo19/server/addons,/tmp/audit-clean-addons`, whose custom addons contain only the required dependency closure. External connectors were absent from the custom addon path, not merely disabled. The original 43-case core suite also passed on the clean connector-free database.
- Core configurations explicitly use `/opt/odoo19/server/addons,/opt/odoo19/worktrees/rip_bconnect`. Private credentials/configurations are excluded from both archives. No production database, user-managed process, connector or historical posting was changed.
- Validation HTTP used `127.0.0.1:5069`, gevent `5072`, workers/cron disabled. User ports and processes were untouched. Final cleanup evidence records release of both temporary ports.

## Final checks

| Check | Result / evidence |
| --- | --- |
| Original core suite | 43 tests passed; `final-core-release.txt` |
| Regression suite | 21 executions passed; 19 new cases plus two existing rollback cases, hence 62 distinct core/regression tests; `final-regressions.txt` |
| Connector-free core suite | 43 passed; `final-clean-core.txt` |
| Independent connections | Four races passed; duplicate posting, overlapping preparation, count confirmation and independent branches; `final-concurrency.txt` |
| Optional native integrations | Three tests passed; purchase receipt, opening receipt and sale/payment/return; `final-integrations.txt` |
| Clean install / targeted upgrade | Successful registry initialization and shutdown; `release-clean-install.log`, `release-targeted-upgrade.log` |
| Views and actions | 72 checks across normal/XML developer modes and `en_US`, `ar`, `ar_001`; `final-views.txt` |
| Translation catalogs | 462 current POT terms covered in each catalog; existing unused translations preserved; no missing/fuzzy active entries; `msgfmt --check-format` passed |
| Browser | Actual English/barcode and Arabic count confirmation with notes; selected attempts, stock/reservations/availability, expiry, barcode and units; Arabic component RTL in both locales; no final console errors |
| Reports | Actual posted PDF and ten-sheet XLSX in all three locales; reference count PDFs include product coverage; final HTML/PDF outputs and screenshots retained |
| Source/package checks | Python/XML parsed, manifest imports/data/assets checked; runtime package excludes development tests, credentials, caches and temporary artifacts |

Browser execution found a manager-only save failure caused by a hidden tax selection without tax-reference read permission. A module-owned read-only ACL for audit financial roles fixes it. The regression verifies that read is allowed while tax mutation remains denied. Missing unit type names in the deliberately minimal browser fixture appear as `False` in native unit display names; real unit labels are read from the existing product/UoM configuration, and the addon does not replace that model’s naming logic.

## Historical movement benchmark

`history_benchmark.py` creates and posts 1,000,000 historical movements for an unrelated product through the existing inventory ORM, plus the target product’s one movement. It compares the original saved ledger implementation with the optimized implementation on that same fixture, then rolls back. It asserts identical target count boundaries.

| Single-group boundary | Original ledger | Scoped aggregate ledger |
| --- | ---: | ---: |
| Movements loaded into Python | 1,000,001 | 1 |
| SQL queries | 1,017 | 16 |
| Elapsed seconds | 78.3723 | 1.5065 |
| Traced Python peak allocation, bytes | 973,276,160 | 74,561 |

The process RSS high-water mark was 2,420,988 KiB; that cumulative process peak does not reset between the two measurements. The timed boundary operation ran under the fixture’s existing branch lock; fixture creation time is excluded. Actual request-like lock-to-commit durations are separately measured below. The workload establishes that unrelated branch history is not loaded for a single group; it does not claim constant cost for a group that itself has a million relevant movements.

## 1,001-group fixture and locks

Both volume comparisons use 1,001 groups, 2,001 sources and 1,001 one-unit shortage adjustments. `volume-baseline-metrics.txt` and `volume-optimized-metrics.txt` record per-operation queries, loaded movement rows, elapsed time and sampled RSS. The baseline comparison swaps only the saved original ledger into the current workflow; this isolates the ledger change. Aggregate display, coverage, review, approval and posting load no movement rows after optimization. Export still loads the 2,001 relevant identities needed for count boundaries. Small-fixture aggregate queries increase slightly; the improvement is avoiding unrelated history at scale, not a claim that every small query is faster.

The comparison ran alongside other disposable validation work, so its elapsed times are subject to contention. `final-lock-metrics-batched.txt` measures actual first branch-lock acquisition through transaction commit on a separate, identically shaped fixture. That script intentionally commits only its disposable fixtures to release locks between stages; it does not delete or repost them. Full branch-lock durations were:

| Operation | Seconds holding branch lock |
| --- | ---: |
| Prepare | 1.1966 |
| Export 1,001 groups | 2.4507 |
| Approve | 1.4944 |
| Post 1,001 adjustments | 54.6253 |

Posting executed 74,202 SQL queries in that request-like run. It still calls the existing inventory/accounting business services for each adjustment. The remaining posting window is a measured capacity constraint, not a correctness gap or a production throughput guarantee. The benchmark confirmation/review loops use internal helpers; public wizard permission and concurrent-count paths are exercised by the separate ORM/browser/concurrency tests.

## Packaging and boundaries

Production and development-validation archives are separate. The saved baseline used by the benchmark is included only in validation. The addon has no new demo data, cron jobs, installation hooks, production migration or connector dependency. Both Arabic catalogs ship with the runtime addon. All validations use disposable local databases. Active deployed sessions, older workbooks, historical coverage reconstruction and production rollout require separate planning and authorization; version-1 workbooks are rejected explicitly.

---

# Historical baseline evidence (before these corrections)

# Validation evidence

Validated on 2026-11-01 against the local Odoo 19 source and PostgreSQL, on `branch19`. No production database, external database or user Odoo process was changed. The original `AGENTS.md` modification was preserved. All new implementation files are under `ab_inventory_audit`.

## Installation and environments

- Final clean install: `codex_inventory_audit_clean_20261101`, 39 modules, no demo data, successful registry initialization and shutdown. Required dependency closure only; Sales, Purchase, Cashier and external connectors were absent.
- Targeted upgrades and core tests: `codex_inventory_audit_20261101`. Only `ab_inventory_audit` was upgraded; no `-u base`.
- Optional integrations: `codex_inventory_audit_integrations_20261101`, a disposable clone with `ab_purchase`, `ab_purchase_ob` and `ab_sales_inventory` explicitly installed. These are not addon dependencies.
- Explicit addons paths: `/opt/odoo19/server/addons,/opt/odoo19/worktrees/rip_bconnect`. Private validation configurations were verified before use and are excluded from delivery.
- Temporary HTTP bound only to `127.0.0.1:5069`; gevent port specified as `5072`, workers and cron threads disabled. User ports `4091` and `4092` were untouched. Temporary server stopped after browser/report checks.

## Automated checks

| Check | Actual result |
| --- | --- |
| Core ORM suite | 43 tests; 0 failures, 0 errors; final run 25.044 seconds |
| Independent-connection concurrency | 4 races passed |
| Optional native business integrations | 3 tests; 0 failures, 0 errors |
| Python/XML/manifest | 12 Python files parsed, 7 XML files parsed, all manifest data paths exist |
| Arabic catalogs | 392 entries each, 0 untranslated/fuzzy entries; `msgfmt --check-format` passed |
| Runtime languages | `en_US`, `ar`, `ar_001` action names and workflow labels verified |
| Reports | Actual count-sheet and results PDFs in all three locales; seven-sheet XLSX results; posted audit reconciliation verified |
| Browser | English count confirmation, barcode selection without increment, Arabic count confirmation, Arabic RTL, both Arabic catalogs, session tabs and fast-count reload; no final console errors |

Core tests cover full/partial overlaps and later coverage additions; independent branches; explicit zero versus uncounted; exact unit conversions; normalized price grouping and distinct source costs; largest-remainder ties; new and existing zero-reference surplus sources; expired stock; reservations and insufficient current stock; accepted discrepancy preservation after subsequent movements; source/tax/configuration changes; self-approval; duplicate and conflicting posting; accounting and inventory failure rollback; cancellation/corrections; preserved recount reasons; assignment and reviewer permissions; cross-branch/company headers and children; financial field protection; forged workflow/default contexts; immutable journals and journal lines; attachment access and public-sharing prevention; Excel preview/import, stale boundaries, foreign/duplicate rows and repeated import; report scope and session movement/attachment display.

The concurrency script uses separate database connections and committed fixtures only in the disposable core database. It races duplicate posting, overlapping preparation and count confirmation, then verifies independent branches. The losing same-record requests receive lock/serialization errors; retry after the successful commit returns the existing posting. Stock movement during an open physical count completed in 0.047 seconds, demonstrating that the count did not retain a branch lock.

The optional integration scenarios exercise a pending purchase receipt becoming saved during counting, an opening receipt after the accepted boundary, and native sales with employee login, payment, return and refund. The native sale/return/audit reconciliation ends at the expected 89 smallest units. These scenarios do not contact external connectors.

## Representative volume

Fixture: 1,001 products/count groups, 2,001 sources, 1,001 exported attempts. Every group has a one-unit shortage in the posting stress case, producing 1,001 adjustments. The fixture transaction is rolled back. Timings are local measurements, not service guarantees.

| Operation | Seconds | SQL queries |
| --- | ---: | ---: |
| Prepare | 1.0470 | 1,105 |
| Read posted/reserved/available quantities | 0.1983 | 7 |
| Export and start attempts | 1.6994 | 1,068 |
| Confirm all groups | 2.7651 | 2,002 |
| Review all groups | 5.9656 | 5,098 |
| Approve | 0.7751 | 2,050 |
| Post 1,001 nonzero adjustments | 56.7913 | 73,151 |

Preparation, export, approval and posting hold transactional branch locks. Confirmation/review totals above use internal helpers in the benchmark transaction; ordinary users confirm/review through validated wizard calls, covered separately by the ORM suite. The measured posting window is substantial because the existing inventory service is invoked for each persistent adjustment. A large live adjustment batch requires capacity and operating-window assessment. No shared inventory-engine redesign was made.

## Evidence and limits

The companion validation bundle contains the scripts, output summaries, final POT, browser screenshots and generated PDF/XLSX examples. It excludes configuration credentials and browser login secrets. Test scripts run through `odoo-bin shell` using a dedicated disposable configuration; they are not shipped in the production addon. Concurrency and browser fixtures intentionally commit only in those disposable databases; other suite/volume fixtures roll back.

Installation logs contain inherited addon warnings; forced concurrency tests log the expected serialization conflict. Pure helper error tests without an Odoo request language can log translation fallback warnings; browser and ORM workflow labels were checked in the configured locales. No failure is hidden by a production migration or hook.

This evidence does not establish complete delivery of remote branch movements, propagation of audit adjustments to branch databases, production throughput or a live pilot. Synchronization, backup/reconciliation for cutover, deployment and live posting require a separate authorized rollout.

## View-opening regression correction

The user runtime log `/opt/odoo19/logs/rip_bconnect.log` showed `TypeError: unsupported operand type(s) for +: NoneType and str` while loading the count-group and accounting-configuration views. Odoo 19's file-based XML developer loader concatenates `field_arch.text` with the child architecture. Four compact architecture fields had no leading text, unlike the other module views.

Reproduced all four failures before the fix (`line_list`, `line_form`, `config_list`, `config_form`). Added leading whitespace inside those four architecture fields. Canonical XML comparison with blank text removed proves the view structure, fields, permissions, actions and labels are unchanged. No stock, accounting or workflow Python was changed.

After correction, all seven file-based views loaded, and 72 `get_views` checks passed across seven explicit views and five window actions in normal/XML developer modes and `en_US`, `ar`, `ar_001`. The earlier runtime browser checks did not exercise XML developer mode; this regression check now covers that gap. The production package and validation companion were refreshed.

The matched user runtime (`rip_bconnect`, source checkout above, HTTP port 4097, process started with `--dev=xml`) also passed 48 view/action checks using its active `en_US` and `ar_001` languages in both modes. These checks used an explicit PostgreSQL read-only transaction and rolled back; no runtime upgrade, restart or language activation was performed. The `ar` catalog remains validated in the isolated database.

## New-audit form and role regression correction

The runtime log showed the allowed-company error on `ab_inventory_audit/onchange`, before an audit or branch was selected. Reproduced with an authorized manager in the same company: `_compute_movement_history()` called the saved-record reporting scope check for a `NewId` form record. This was premature form computation, not a missing audit role.

Unsaved forms now return empty movement history and attachment panels; saved-record authorization is unchanged. Three new tests cover initial/selected/cleared/default branch values, unsaved edits of existing drafts, saved cross-branch panel denial and counter/reviewer creation denial. The complete ORM suite passes 43 tests. Six additional onchange checks passed against the matched runtime's administrator and same-company branch in English and Arabic through an explicit read-only transaction. The effective administrator account has the audit groups; its lack of individual branch assignments is intentionally permitted by the administrator path, while company isolation remains enforced.

No group assignments, company records, branch mappings or accounting permissions were changed. The runtime currently uses `--dev=xml`, which does not reload Python model changes. The operator must restart their existing Odoo process once to activate this Python fix; no database upgrade is needed. The agent did not stop or restart that process.
