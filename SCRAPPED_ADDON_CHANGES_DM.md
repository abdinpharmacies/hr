# Development memo: addon changes reversed after the pull

Date: 2026-10-19
Branch: `branch19`

## What "reversed" means

The workspace started at `38676b8e`. A fast-forward pull brought it to
`3815a24a`. Commit `b68b8b34` then restored the complete contents of
`ab_inventory`, `ab_purchase`, `ab_product_source`, and `ab_taxes` from
`38676b8e` and was pushed to `branch19`. The other pulled modules were kept.
The restoration changed 64 files across those four addons. The incoming work
still exists in Git history; it was reversed in the current tree, not erased.

This memo describes the **difference between those two revisions**, rather
than treating every older item in a module changelog as a newly reversed change.

## `ab_inventory`: stock engine expansion

- Added a current balance projection by company, store, product, source, and
  location, plus a posting sequence. The previous implementation used the
  latest saved movement's closing balance for a store and source.
- Added reservation, return, shortage, cost-correction, and projection-repair
  records. New service methods included `source_stock`, `available_stock`,
  `reserve_stock`, `release_reservation`, `post_reserved`,
  `return_allocations`, `transfer_location`, `check_integrity`, and
  `rebuild_projection`.
- Added deterministic source allocation for sales, authorized shortage sales
  with reasons, reconciliation of shortages on later receipts, and returns
  against the original sale allocation.
- Added location transfers, integrity review and audited projection repair.
  Posting also checked reserved stock and used configurable fractional stock
  precision instead of only integer smallest-unit quantities.
- Expanded company, store, and role checks, inventory operation screens,
  reports, and both Arabic translation catalogs.

The principal new files were `models/stock_state.py`,
`models/integrity_review.py`, and `views/stock_state.xml`. The main work is in
commit `90527434` (`feat(ab_inventory): add atomic balances, reservations and
shortage reconciliation`).

## `ab_product_source`: identity, lots, and price audit

- Added immutable UUID source identities, company and store scope, source
  provenance (origin model, record, and database), optional legacy and parent
  references, and binding of a source to its business document.
- Added a physical-lot model separated from receipt cost/source records.
  Explicit expiry or approved no-expiry handling replaced assumptions about
  missing dates.
- Added product stock configuration and quantity conversion/precision checks,
  including safeguards around unit and service classification changes after
  stock activity.
- Added price history with old/new price, actor, and timestamp, plus access
  controls and views for lots, configuration, and history.
- Added company/store record rules, source roles, and both Arabic catalogs.

The new models were in `models/physical_lot.py`,
`models/price_history.py`, and `models/source_foundations.py`. The main work is
in commit `d85cc8f6` (`feat(ab_product_source): add scoped lots, provenance,
unit validation and price history`).

## `ab_purchase`: receipt economics, returns, and data entry

- Made `ab_taxes` an explicit dependency. Added company rules for purchases,
  lines, notices, and notice lines.
- Bound receipt sources to their store, company, and purchase origin. Added
  frozen tax and valuation snapshots at receipt/notice approval, with checks
  against changing saved documents or deleting purchase invoices and notices.
- Allocated invoice discounts and bonus quantities into receipt cost. Return
  calculations reused the purchase tax policy and checked cumulative paid and
  bonus return limits.
- Distinguished physical supplier credit returns from financial-only notices.
  Financial notices did not create stock movements; physical returns did.
  Added the associated form actions and views.
- Extended the Data Entry screen with store-code lookup, exact supplier-code
  lookup, no-expiry handling, and tax-policy calculations. The incoming UI
  also replaced the multi-tax checkbox selection with a single-tax selector;
  that detail should be reviewed before reusing the UI change.
- Expanded access checks and Arabic translations.

Relevant commits are `4b903c45` (tax dependency), `f09e6a59` (store and
supplier lookup), `848e9fb9` (grid width), `eac9729f` (physical versus
financial notices), and `c38c0449` (receipt valuation and supplier returns).

## `ab_taxes`: purchase tax policy

- Added a company-scoped `ab_purchase_tax_policy` with bonus taxation,
  before/after-tax discount timing, rounding precision, and an approval
  reference.
- Added tax-component and inventory-cost calculations, input validation,
  policy access rules, a configuration view, and Arabic translations.

The main work is commit `8106c840` (`feat(ab_taxes): add configurable purchase
tax policies and cost calculations`).

## Current integration consequence

The pulled `ab_sales_inventory` module was **not** reversed. Its native sales
and POS paths call the removed inventory service methods (`reserve_stock`,
`post_reserved`, `source_stock`, `available_stock`, and
`return_allocations`). They also use product stock conversion methods that
were part of the reversed `ab_product_source` work. Those paths are therefore
incompatible with the current four-addon versions and need reconciliation
before native sales is enabled or tested as a complete flow.

## How to inspect the original changes

```text
git diff 38676b8e 3815a24a -- ab_inventory ab_purchase ab_product_source ab_taxes
git show 90527434
git show d85cc8f6
git show c38c0449
git show 8106c840
```

This is a Git-history inventory, not a fresh runtime validation or a request
to restore the changes. The earlier module changelogs describe historical
tests, but those results were not rerun for this memo.
