# Standalone acceptance evidence

Verified initially on 2026-09-24 and reverified with direct store relations on 2026-09-27 against the local Odoo 19 source and PostgreSQL. Production databases and external databases were not used. Purchase/sales/HR code was not changed. No service restart or production upgrade was performed.

## Environment and reproducibility

- Initial isolated installation: `ab_accounting_plan02_verify`.
- Second clean installation of the rebuilt addon: `ab_accounting_plan02_clean`.
- Direct-store revision: fresh installation and targeted upgrade of `ab_accounting_direct_store_verify`, loading the repository addon directly.
- Installation used `-i ab_accounting --without-demo=all --stop-after-init`.
- Targeted upgrades used only `-u ab_accounting --without-demo=all --stop-after-init`; no `-u base`.
- Test scripts and fixtures are outside the addon under `/tmp/ab_accounting_validation/` (original port) and `/tmp/ab_accounting_direct_store/` (current direct-store revision); they are not shipped in the production package.
- The standalone installed module graph excludes purchase, sales, HR, `ab_hr`, `abdin_et`, `ab_data_from_excel`, `ab_base_models_inherit`, `ab_purchase`, and `ab_sales`.

Applied to `/opt/odoo19/custom-addons/ab_accounting` on 2026-09-27 after filesystem write access was restored. All 26 files initially matched the staged, tested implementation byte-for-byte. A targeted upgrade on `ab_accounting_plan02_clean` then loaded the addon directly from the repository. Additional runtime checks verified the repository import path, native forms/lists, isolated module graph, two-decimal Float comparison and Arabic action translation. Both translation catalogs and Python/XML parsing passed again. The README role table was changed to a list to avoid Odoo's module-description parser errors. Production databases and services remain unchanged.

## Automated acceptance

106 assertions/scenarios passed on the direct-store revision: the original 96 checks were rerun with existing `ab_store` records, plus 10 focused checks. There is no `ab_accounting_branch` model or mapping screen; journals, items, periods, openings, reports and user assignments refer directly to shared stores.

Checks across the external suites:

| Suite | Checks | Coverage |
|---|---:|---|
| Core posting | 44 | Clean schema; Float arithmetic; identity retries; negative, non-finite and excess-precision rejection; one-cent imbalance; posting audit; period overlap/closure/reopening; posted header/item write, unlink, archive, reparent and relational-command protection under sudo/context flags; full reversal; openings; balances without current activity; branch/company/role restrictions |
| Security and exports | 26 | Whole-journal visibility; hidden totals; document grants; attachment access; source navigation; business reversal boundary; forged defaults; reviewer authority; cost-center dimensions; transactional rollback; read-only Reports; native PDF and numeric XLSX parity |
| Concurrent transactions | 7 | Identical requests; changed requests; conflicting identity across branches; item edit vs posting; duplicate full reversal; period closure vs posting; subsequent closed-period rejection |
| Native screens and edge cases | 13 | Unsupported currency argument; business event reversal restrictions; archived-account history; inactive accounts/branches; unarchiving; atomic multi-journal posting; native default precision; Auto JE configuration denial; compiled forms/lists; runtime Arabic; all 240 rows retained; Float field precision |
| Opening concurrency | 2 | Closing an opening run vs adding a draft; no closed run acquiring an unposted journal |
| Shared authorization | 2 | Explicit Always Show grants and Prevent Enquiry override without partial totals |
| Context isolation | 2 | Stable generated request/retry despite native action defaults; period audit defaults cannot be forged |
| Direct stores | 10 | No mapping model; direct relations across all accounting models; all active stores selectable; derived item store IDs; posting still requires assigned stores; independent company periods; cross-company opening/report rejection; secured company movements on a shared store |

Accounting coordinates mutations using ordered store-row locks and a no-op tuple update. The tuple update changes no store values or audit fields; it forces stale PostgreSQL snapshots to retry the complete caller transaction. No shared-store schema extension or mapping record is introduced.

Concurrency suites use separate PostgreSQL cursors/threads with an already-established snapshot and Odoo's whole-transaction retry wrapper. Both schedules were observed for edit/post races: either the edit commits and unbalanced posting is rejected, or posting commits and the edit is rejected. Closing a period can follow an already-committed posting, but new postings after closure fail.

A failure inside the posting service leaves no partial journal. A simulated subsequent source-operation failure rolled back both the business record and the posted journal in the enclosing transaction.

## Rendering and translations

- Odoo-generated PDF rendered successfully and was visually inspected after adding the module-owned landscape paper format and table styling. The sampled report has readable columns, no clipping/overlap, and ordinary two-decimal numbers.
- XLSX cells matched `get_report_data()` row-for-row and used `#,##0.00`; strings are written as strings, not formulas.
- The current module POT was exported through Odoo 19 to `/tmp/ab_accounting_direct_store/ab_accounting.pot`.
- All 249 currently exported strings have translations in both `i18n/ar.po` and `i18n/ar_001.po`. Existing msgids and unrelated translations were preserved; missing entries/references were merged. One existing newline-format defect was repaired.
- Both catalogs pass `msgfmt --check-format`.
- After loading Arabic and a targeted upgrade, the action changes from `Journals` in `en_US` to `قيود اليومية` in `ar_001`, and the journal form contains translated posting text.
- Every Python source parses and every XML file parses. Odoo installation/upgrade validates registered fields, ACLs, record rules and views.

## Limits and handoff

This is standalone accounting acceptance. No real purchase or sales adapter was integrated or tested. Adapter owners must implement the transaction and account-mapping contract in `POSTING_CONTRACT.md`; real adapter acceptance remains a separate gate.

This clean-install design includes no migration of existing Odoo 15 production data, replay, hooks, automatic openings or default-account seeding. Multi-company integrations need an explicitly authorized service user and must retry the complete business transaction on serialization conflicts. Reports include every matching row in memory; production-scale load testing was not performed.
