# Purchase accounting review pilot

## Current status — 2026-10-18

The development database `rip_bconnect` now has active **Review Logs Only**
configurations for branch codes **29** and **140**, effective **2026-10-18**.
Purchasing was enabled for branch 140 with explicit user approval. Existing store
replication protection was restored and independently verified after the change.
The review schema was already installed, so no upgrade or application restart was
needed.

The full synthetic pilot is retained separately in `ab_purchase_review_test`:
eight documents, seven pending review logs, no new journals, and 110 passing
scenario assertions. Synthetic master data was not inserted into `rip_bconnect`,
whose product/UoM replication restrictions remain in place. Account mappings and
business calculation approval remain outstanding.

See the [current pilot results and acceptance items](../ab_independence_dev_plans/10_purchase_review_pilot_status.md)
for exact amounts, environment details and durable evidence. The historical
implementation and validation notes below describe the earlier 2026-10-15 work.

Implemented on 2026-10-15 for the next purchase milestone. The pilot branches are
store code **29** (فرع العتبة) and store code **140** (مخزن افتراضي).
Codes identify the business branches; no database row IDs are hardcoded.

## Behavior

Each company/branch configuration can select **Review Logs Only**. Finalizing a
new purchase receipt, supplier return, financial debit/credit notice or
non-purchase receipt then captures an immutable accounting review snapshot.
The normal document and inventory workflow still runs. Opening balances are
excluded. Existing configurations default to **Post Journals**.

A snapshot retains the source reference, branch, company, supplier, commercial
lines, unit factors, prices, discounts, taxes, totals, proposed debit/credit
entries, actor and capture time. Missing mappings and detected discrepancies are
shown for manual review. Review mode does not require complete journal mappings.
The proposals follow the existing adapter calculations; they are not approved
accounting policy or posted journals.

Reviewers can add a note and mark a log Reviewed or Needs Attention. These
actions do not post journals. Captured values cannot be edited or deleted through
ORM/RPC, including by administrators. Source documents remain governed by their
existing module controls; later source edits do not rewrite the captured snapshot.

Company rules apply to every log. Branch users see their assigned inventory
stores; purchase managers, accounting managers and system administrators have
the existing elevated branch scope. Accounting reviewers can update review
notes/status within their allowed scope. Other authorized readers cannot do so.
Opening the source document also requires access to that document.

Document locking, a unique source key and the surrounding transaction prevent
duplicate stock/log effects on approval retries. A failed capture rolls back the
new approval and its stock effect. Conflicting repeat snapshots are rejected.

## Next steps for the pilot

1. Upgrade only `ab_purchase_accounting` in the chosen development database,
   using the worktree addons path and the project's normal configuration.
2. As an accounting manager, create an active purchase accounting configuration
   for each pilot branch in the intended company. Select **Review Logs Only**
   and an activation date on or before the new test documents. Confirm the
   effective configuration before approving any document.
3. Create fresh test purchase invoices for codes 29 and 140, with agreed
   products, supplier, quantities, bonus quantities, discounts and taxes.
   Submit and accept them using the existing purchase workflow.
4. Open **Accounting → Accounting Review Logs**. Compare invoice totals,
   calculated amounts, proposed entries and stock changes. Record discrepancies
   in the review note and mark the log accordingly.
5. Repeat with a partial supplier return and financial notices; verify physical
   returns affect stock once and financial notices do not affect stock.
6. Agree the calculations and missing controls with the business reviewer before
   expanding the pilot. Full accounting controls and automatic posting rollout
   remain a later project milestone.

There is no historical backfill. Changing a configuration later does not post
previously saved review-only documents. Documents before the activation date
continue through the existing adapter configuration checks.

## Validation evidence

Validation used the isolated database `ab_purchase_review_test`, not the running
`rip_bconnect` database. The isolated PostgreSQL data directory and evidence are
under `/tmp/ab_purchase_review_validation`; temporary files are not permanent
project records. No external B-Connect writes were performed.

- Fresh installation and targeted module upgrades passed on Odoo 19.
- 62 functional checks passed: receipts, bonus/discount/tax calculations,
  returns, financial notices, non-purchase receipts, opening exclusion,
  immutable snapshots, permissions, branch/company isolation, rollback,
  retries and the unchanged journal-posting mode.
- Four independent-session concurrency checks passed: competing approval
  rejection, a single review log, a single stock effect and no review-mode journal.
- Two final regression checks passed for the domain API and exclusion of archived
  configurations even when the caller disables the default active-record filter.
- Both Arabic catalogs passed `msgfmt --check-format`; runtime action, form and
  generated table translations passed in `ar_001`, the installed Arabic locale.
- Two accepted receipts and two returns are retained in the isolated database
  for codes 29 and 140. Their products, supplier and tax data are synthetic;
  they are test examples, not historical business evidence.

Evidence scripts and outputs: `check_review.py` / `check_review.out`,
`check_concurrency.py` / `check_concurrency.out`, and
`check_language.py` / `check_language.out`, plus `check_final.py` /
`check_final.out` in that temporary directory.
Fixtures are outside the addon package. Browser interaction was not tested.

At the end of the 2026-10-15 implementation, `rip_bconnect` had not been upgraded,
configured or seeded by that work. Development activation was subsequently
completed as recorded above; business review remains outstanding.
