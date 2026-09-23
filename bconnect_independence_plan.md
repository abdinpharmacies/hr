# Replace B-Connect using the existing AB inventory, purchase, and accounting models

## 1. Revised direction and evidence

Port and harden the Odoo 15 modules **`ab_inventory`, `ab_purchase`, `ab_purchase_ob`, `ab_product_source`,
and `ab_accounting`** for Odoo 19. Use their actual model names, field names, and suitable business logic as the
foundation for B-Connect independence.

This replaces the previous assumption that stock, purchasing, opening balances, and accounting needed entirely new model
families. Do not build competing `ab_stock`, `ab_stock_batch`, `ab_stock_opening`, or `ab_account` engines. Extend the
existing AB models; introduce additional models only for a capability they do not provide.

**Source baseline inspected on 2026-09-23**

- Local Git reference `origin/abdin15`: `82e766afcaeb376c7e9b691ee98beb5ec18189b6`.
- Working branch `pos19`, HEAD `3600e750`. The five module directories match that local remote-tracking reference (
  `git diff origin/abdin15 -- <five modules>` is empty). This is a source comparison, not evidence of Odoo 19
  compatibility or of the latest remote state.
- The previous `bconnect_independence_plan.md` was absent from the working tree. Its contents were recovered for review
  from Git object `15848040`; no stash was applied.
- Existing declarations and workflows below were inspected in `models/`, `models_accounting/`, manifests, and security
  files. The current POS contract was checked in `ab_sales/models/ab_sales_line.py` and
  `ab_sales/models/ab_sales_header.py`.
- **Existing** means present in inspected code. **Planned** means a new or changed contract required by this plan; it
  does not imply implementation is complete.

This document is an implementation plan. Importing the old source is the starting point, not a completed port.

## 2. Architecture and ownership retained from the previous plan

Keep the existing `ab_sales` POS window and its product search, UoMs, price badges, discounts, contracts, promotions,
batch display, and cashier navigation.

Each branch owns its operational inventory, sales, receipts, cash, and journal postings in its local PostgreSQL
database. Headquarters owns shared master-data governance and headquarters financial operations. A reporting database
consolidates passive copies from branches; local `ab_stock_report` snapshots provide fallback cross-branch visibility.

```text
Existing POS / Call center / Purchase / Transfer / Stock count
                             |
                   Authorized business document
                             |
       ab_product_source + ab_inventory_process + ab_inventory
                             |
              ab_accounting_je_header / ab_accounting_je_line
                             |
       One local transaction: document + stock + journal + outbox
                             |
                  Durable synchronization queue
                             |
                  Odoo reporting database
                             |
                ab_stock_report fallback snapshots
```

- Only the owning branch may post against its operational inventory. Reports, mirrors, and snapshots never post stock or
  financial entries.
- Headquarters receipt of a branch journal creates a reporting copy, not a second financial posting. Headquarters cash
  receipt is a separate acknowledged business event.
- The initial release supports one legal company and multiple branches. Add explicit company ownership where required;
  this is not a claim of existing multi-company isolation.
- Opening data is manually supplied and mapped by the user. No automated B-Connect extraction or historical transaction
  migration module is included.
- Preserve external product, branch, batch, and transaction identifiers for traceability. External databases remain
  read-only; native operation must not call legacy write flows.
- Local operation must continue when reporting or synchronization is unavailable.

## 3. Module responsibilities and dependency direction

| Module                                  | Decision                          | Responsibility in the revised plan                                                                                                                                       |
|-----------------------------------------|-----------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `ab_product_source`                     | Port and extend                   | Product receipt/source layers, expiry, source UoM, purchase/selling prices, tax components, and source identity.                                                         |
| `ab_inventory`                          | Port and harden                   | Signed inventory ledger, stock posting service, branch balances, pending acceptance, reservations, locations, and shortages.                                             |
| `ab_accounting`                         | Port and harden                   | Existing chart, document types, journal headers/lines, account permissions, balances, and statements; add period controls and immutable reversals.                       |
| `ab_purchase`                           | Port and extend                   | Existing supplier invoice, receipt approval, debit/credit notices, supplier claims, and accounting linkage. Add separate order/receipt tracking where needed.            |
| `ab_purchase_ob`                        | Port and extend                   | Manually mapped opening-stock documents, validation, approval, inventory posting, and linked opening accounting.                                                         |
| `ab_inventory_accounting`               | Planned small adapter             | Shared inventory valuation-to-journal orchestration for openings, sales issues, transfers, counts, and corrections. Reuse `ab_accounting`; do not create another ledger. |
| `ab_sales_inventory`                    | Planned adapter                   | Native inventory availability, allocations, sale issues, and customer returns behind the current POS contract.                                                           |
| `ab_sales_cashier`                      | Evolve                            | Native payment records, drawer balances, sessions, settlements, refunds, and accounting.                                                                                 |
| `ab_transfer` / `ab_transfer_inventory` | Evolve / planned adapter          | Retain transfer documents and screens; implement native reservation, dispatch, transit, receipt, and discrepancies.                                                      |
| `ab_stock_count`                        | Planned workflow module           | Blind counts, recounts, approvals, and adjustment documents posted through `ab_inventory_process`.                                                                       |
| `ab_sales_callcenter`                   | Planned workflow module           | Cross-branch availability, branch requests, acknowledgments, reservations, and cancellations; reuse `ab_branch_api` transport patterns.                                  |
| `ab_stock_report`                       | Evolve existing module            | Consolidated balances and complete, dated local fallback snapshots.                                                                                                      |
| `ab_inventory_sync`                     | Planned adapter                   | Inventory/report uploads, acknowledgments, versions, reconciliation, and durable business messages using existing queue infrastructure.                                  |
| `ab_cash_transfer`                      | Planned workflow module           | Branch-to-headquarters remittance, custody, receipt, discrepancies, and clearing entries in `ab_accounting`.                                                             |
| `ab_eplus_legacy`                       | Transitional isolation, if needed | Contain existing legacy backend behavior for unconverted branches. No new automated external writes.                                                                     |

Keep `ab_product`, `ab_store`, `ab_supplier`, `ab_customer`, `ab_costcenter`, and related foundations. Preserve `ab_uom`
and the product unit-conversion helpers.

The current dependency chain already establishes useful ownership:

```text
ab_product + ab_taxes -> ab_product_source
ab_product_source + ab_store -> ab_inventory
ab_costcenter + ab_store + accounting helpers -> ab_accounting
ab_inventory + ab_product_source + ab_accounting + ab_supplier -> ab_purchase
ab_purchase + ab_product_source + ab_inventory -> ab_purchase_ob
```

The planned `ab_inventory_accounting` adapter depends on `ab_inventory` and `ab_accounting`; those cores must not depend
on that adapter or on sales. Workflow adapters depend on the relevant workflow and core modules. `ab_purchase` already
owns purchase journal generation: refactor it to a single posting path, avoiding duplicate entries from an additional
adapter. `ab_purchase_ob` can depend on the common adapter to add opening accounting.

Audit the full dependency closure before declaring the modules installable. The local addon root lacks `ab_taxes` and
`web_domain_field`; verify configured addon paths before deciding whether to port them or replace their usage. Also
inspect `ab_base_models_inherit`, `ab_data_from_excel`, `abdin_et`, and payroll-related accounting references. Do not
install an entire legacy project merely to satisfy incidental imports. Separate optional integrations, use manifest
dependencies for required models, and add `ab_hr` if HR models or fields are used.

## 4. Existing model and field contracts to retain

### 4.1 Product sources: `ab_product_source`

Source: `ab_product_source/models/ab_product_source.py`. It inherits the abstract `ab_product_template` from
`ab_product`.

| Existing fields                                               | Meaning and reuse                                                                                                             |
|---------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------|
| `product_id`, `qty`, `uom_id`, `qty_large`, `product_uom_ids` | Inherited product and document quantity contract. `qty` is in the source UoM; it is not the current branch stock balance.     |
| `exp_date`, `price`, `purchase_price`                         | Source expiry, selling price, and purchase price in the source UoM.                                                           |
| `extra_discount_percentage`, `bonus`, `taxes_ids`             | Discount, bonus quantity, and tax definitions.                                                                                |
| `unit_taxes_value`, `unit_cost`                               | Existing computed tax and cost components. Preserve their commercial meaning; separately snapshot posted inventory valuation. |
| `product_code`, `source_model`                                | Product code relation and origin model reference.                                                                             |
| `available_qty`, `total_qty`, `is_pending`                    | Added by `ab_inventory`; their current computations need branch-aware replacement.                                            |

Retain `convert_price()`, `convert_cost()`, `qty_to_small()`, and `qty_from_small()` as recognizable interfaces, after
verifying conversion and rounding behavior. Retain the cost/price validation intent and two-stage tax calculation as
business logic to test:

```text
net_purchase_price = purchase_price * (1 - extra_discount_percentage / 100)
taxes_on_purchase = sum(net_purchase_price * percentage / 100)
                   for taxes where apply_on_total is false
taxes_on_total = sum((net_purchase_price + taxes_on_purchase) * percentage / 100)
                for taxes where apply_on_total is true
unit_taxes_value = taxes_on_purchase + taxes_on_total
unit_cost = net_purchase_price + unit_taxes_value
```

These describe the inspected implementation, not a final tax policy. Recoverable taxes, invoice discounts, and bonus
stock require explicit valuation treatment before posting.

**Planned extensions:** immutable global source identity, source database/branch provenance, physical lot reference
where available, receipt date, and legacy item/store/class mapping. Keep different receipt-cost layers separate even if
product, expiry, or selling price match. A transferred layer retains its origin identity while destination ownership is
local. Never equate E-Plus `c_id` or a remote Odoo integer ID with the destination `source_id`.

Protect posted source economics from edits that would recalculate historical inventory value. Price changes must record
`old_price`, `new_price`, `changed_by`, and `change_date`; changing a current selling price must not revalue old
movements. Product codes, barcodes, and external references remain restricted to Inventory Manager/System Administrator
roles.

### 4.2 Inventory: `ab_inventory`, `ab_inventory_header`, `ab_inventory_process`

Sources: `ab_inventory/models/ab_inventory.py`, `ab_inventory_header.py`, and `ab_inventory_process.py`.

| Existing model              | Fields/interfaces to retain                                                                                                                                    | Target meaning                                                                                                                               |
|-----------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------|
| `ab_inventory`              | `store_id`, `source_id`, `product_id`, `qty`, `source_uom_id`, `qty_in_source_unit`, `price`, `unit_cost`, `unit_taxes_value`                                  | Signed movements by branch/source. `qty` is an integer in the smallest stock unit; positive receives and negative issues.                    |
| `ab_inventory`              | `header_id`, `model_ref`, `res_id`, `header_ref`, `serial`, `status`, `location`, `source_id_balance`                                                          | Document traceability and acceptance status. `serial` is not a safe global identity. `location` is currently only text.                      |
| `ab_inventory_header`       | `header_id`, `model_ref`, `res_id`, `header_ref`, `store_id`, `line_ids`, `pending_main_count`, `pending_store_count`, `has_pending_main`, `has_pending_store` | Group movements and navigate to their originating document. Distinguish the source document's `res_id` from the inventory header's local ID. |
| `ab_inventory_process`      | `inventory_write(rec, qty, store_id, inventory_line=None, status='pending_main', sign=1)`; `change_inventory_status()`                                         | Existing abstract posting entry point. Preserve the recognizable interface while replacing unsafe internals with validated, atomic posting.  |
| `ab_product_source_pending` | `source_id`, `qty`, `product_id`, `bonus`, `purchase_price`, `price`, `uom_id`, `unit_cost`, `unit_taxes_value`                                                | Existing `_auto = False` pending-source report. Its source-only identity and aggregation are insufficient for branch isolation.              |

Use **`ab_inventory` as the movement ledger**, not as one editable balance row. No separate `ab_stock_move` family is
required. For an authorized branch/location/source:

```text
on_hand_small = sum(ab_inventory.qty where status == 'saved')
available_small = saleable_on_hand_small - active_reserved_small
```

These are planned balance semantics. The old all-status and `min(pending, total)` calculations do not implement them.
Pending inbound quantities are visible separately and cannot be sold. An outgoing pending document reserves stock; the
accepted/posted issue reduces stock once. All reads include branch scope, including computed fields, reports,
pending-source searches, and APIs.

Keep status keys `pending_main`, `pending_store`, and `saved`, with enforced meanings:

- `pending_main`: awaiting origin/HQ review; no on-hand effect.
- `pending_store`: awaiting owning-branch acceptance; no inbound on-hand effect.
- `saved`: accepted/posted movement included in the immutable stock ledger.

A document being `saved` and its stock being posted must no longer disagree. A direct sale/issue or approved opening may
post to `saved` through the authorized service without fabricating pending receipt steps.

**Planned structural repairs and additions**

- Retain `ab_inventory.header_id` by name but make it a real `Many2one('ab_inventory_header')`; it is currently an
  Integer used as a One2many inverse. Set the inventory header's `store_id` explicitly.
- Add structured `location_id` alongside the existing `location` note. Distinguish saleable, quarantine, damaged, and
  transit stock.
- Add operation identity, movement identity/sequence, posting user/date, reversal reference, frozen valuation amount and
  cost-UoM basis. Keep `model_ref`, `res_id`, and `header_ref` for document navigation.
- Extend `model_ref` through each owning workflow module, including sales, returns, transfers, and adjustments; validate
  the model/record/branch combination server-side.
- Give pending reports a branch dimension and stable branch/source identity. Replace the existing SQL view with an
  ORM-backed report if practical; any retained reporting SQL must be read-only and necessary, with no destructive schema
  workaround.
- Add only the missing supporting models in `ab_inventory`: proposed `ab_inventory_location`,
  `ab_inventory_reservation`, and `ab_inventory_shortage`. Reservations carry branch/source/location, quantity,
  originating request identity, and lifecycle; shortages carry uncovered quantity, provisional value, and reconciliation
  links.
- A balance projection may be introduced only if measured performance requires it. It must rebuild from posted movements
  and remain writable only by the posting service.

Do not modify Odoo system-managed quantity fields. All operational changes originate in approved receipts, sales,
transfers, adjustments, openings, returns, or reversal documents and pass through this inventory service.

### 4.3 Purchasing: `ab_purchase`

Sources: `ab_purchase/models/` and `ab_purchase/models_accounting/`.

| Existing model                | Important existing fields                                                                                                                                                                                                                                                             | Logic to reuse                                                                                                                                                        |
|-------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `ab_purchase_header`          | `supplier_id`, `store_id`, `doc_code`, `doc_date`, `invoice_type`, `line_ids`, `status`, `net_invoice`, `net_tax`, `total_price`, `total_purchase_price`, `total_cost`, `total_tax`, `total_extra_discount`, `total_extra_discount_percentage`, `net_invoice_eq_total_cost`, `active` | Supplier invoice capture, reconciliation of entered totals, document validation, receipt review.                                                                      |
| `ab_purchase_line`            | `header_id`, delegated `source_id`, `line_purchase_price`, `line_price`, `line_cost`, `line_taxes_value`, `confirm`, `net_qty`, `notice_qty`, `disc_tax_no_effect_value`                                                                                                              | Source-layer creation, paid/bonus quantities, discounts and tax calculations. `net_qty` and `notice_qty` currently return placeholders and need real implementations. |
| `ab_purchase_notice_header`   | `supplier_id`, `purchase_header_id`, `purchase_header_ids`, `notice_type`, `doc_code`, `doc_date`, `status`, `line_ids`, `total_cost`, `total_taxes_value`                                                                                                                            | Supplier debit/credit notice workflow and original invoice references.                                                                                                |
| `ab_purchase_notice_line`     | `header_id`, `source_id`, `product_id`, `qty`, `bonus`, `invoice_qty`, `invoice_bonus`, `available_qty`, `available_bonus`, `last_inventory_id`, `uom_id`, `line_cost`, `line_taxes_value`                                                                                            | Source-linked returns and separate paid/bonus return quantities.                                                                                                      |
| `ab_product_supplier_origin`  | `supplier_code`, `product_id`, `costcenter_id`, `origin`                                                                                                                                                                                                                              | Supplier/product classification: `local`, `local_45`, `imported`, `cash`.                                                                                             |
| `ab_purchase_claim`           | `je_header_id`, `costcenter_id`, `je_line_ids`, `distribution_line_ids`, `claim_value`, `is_closed`, `instant_cash`, `claim_month`, `claim_deliver_date`, `total_claim`, `total_taxes`                                                                                                | Link supplier invoices/notices to claim and settlement work, retaining supplier cost-center identity.                                                                 |
| `ab_purchase_claim_dist_line` | `claim_id`, `account_id`, `value`, `payment_type_id`, `supplier_bracket_id`, `due_date`, `credit_days`, `discount`, `discount_value`                                                                                                                                                  | Payment distribution and supplier term calculations.                                                                                                                  |
| `ab_purchase_claim_line`      | `claim_id`, `account_id`, `debit_val`, `credit_val`, `doc_type`, `claim_supplier_id`, `actual_supplier_id`, `payment_type_id`, `other_type`                                                                                                                                           | Existing compensation/payment detail structure; confirm which active screens need it before exposing it in the port.                                                  |

Preserve `eplus_serial`, `eplus_serial_header`, `eplus_serial_g_return`, `eplus_g_header_serial`,
`eplus_total_disc_on_inv`, and `last_update_date` where already declared. They are historical mapping fields, not
prerequisites for native transactions. Scope legacy uniqueness by source identity where needed and allow multiple native
documents without a legacy ID.

Preserve the purchase status keys `prepending`, `pending`, `saved`, and `rejected`; define authorized transitions and
aggregate partial receipt state explicitly. Existing `btn_submit_inventory()` creates inventory for **`qty + bonus`**,
then sets the header to `pending`; branch acceptance must complete receipt posting exactly once.

The existing purchase header represents a supplier invoice/receipt workflow, not a complete purchase-order and
partial-receipt system. Keep it as the supplier invoice record. **Planned additions in `ab_purchase`** are
`ab_purchase_order_header` / `ab_purchase_order_line` and `ab_purchase_receipt_header` / `ab_purchase_receipt_line`,
with explicit links to invoice lines and source layers. These are gaps, not existing models. Multiple receipt events
must not overwrite one original invoice-line movement.

Retain the current notice sign convention: `credit_notice` produces a negative stock movement and `debit_notice` a
positive movement **when physical goods move**. Add an explicit financial-only path for price corrections; a financial
notice must not create fictitious quantity. Restore return limits using original accepted receipts minus prior returns,
separately for paid and bonus units, within the correct branch. Do not infer the branch from an unrestricted search for
`last_inventory_id`.

### 4.4 Opening balances: `ab_purchase_ob`

Sources: `ab_purchase_ob/models/opening_balance_header.py` and `opening_balance_line.py`.

- Keep `ab_purchase_ob_header`: `store_id`, `line_ids`, `description`, `status` (`pending` / `saved`), `total_price`,
  `total_cost`, `total_tax`, `lines_count`, and `active`.
- Keep `ab_purchase_ob_line`: `header_id`, delegated `source_id`, and `header_status`. Product, quantity, UoM, expiry,
  cost, price, and taxes come through `ab_product_source`.
- Extend these records with opening-run identity, cutoff date, approval and reconciliation evidence, and legacy mapping
  provenance. Do not introduce competing stock-opening models.
- `btn_submit_inventory()` is the entry point to harden. The inspected method marks the header `saved` while calling
  `inventory_write()` with its default `pending_main`; it must instead post approved opening movements to `saved`
  exactly once.
- The actual opening header does **not** inherit the purchase/accounting delegate and does **not** currently generate
  opening journals. The opening entry in the delegate's `MODEL_MAP` is not evidence that accounting is implemented. Add
  an explicit journal link and posting through `ab_inventory_accounting`.
- Validate every supplied branch, product, UoM ratio, expiry policy, source identity, quantity, cost, and duplicate key.
  Reject unknown mappings. Do not silently substitute the old default expiry or default branch.
- Opening stock posting and its journal must be coordinated with the manually supplied general-ledger opening balances
  so inventory value is recognized once, not twice.

### 4.5 Accounting: `ab_accounting`

Sources: `ab_accounting/models/ab_accounting_account_guide.py`, `ab_accounting_account_levels.py`,
`ab_accounting_je_header.py`, `ab_accounting_je_line_common.py`, `ab_accounting_je_line.py`, and the delegate/reference
helpers.

| Existing model                                                                                     | Existing fields/interfaces to retain                                                                                                                                                                                                                                             |
|----------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `ab_accounting_account_guide`                                                                      | `name`, `code`, `parent_id`, `parent_path`, `linked_account_id`, `currency_id`, `internal_type`, `internal_group`, `nature`, `include_initial_balance`, `reconcile`, `has_store`, `has_costcenter`, `has_due_date`, `calc_balance`, `max_negative_value`, `related_to`, `active` |
| `ab_accounting_account_first_level`, `ab_accounting_account_second_level`, `ab_accounting_account` | Existing classification hierarchy and `linked_account_id` mapping; avoid creating a parallel chart.                                                                                                                                                                              |
| `ab_accounting_doctype`                                                                            | `name`, `internal_type`; retain document-type classification.                                                                                                                                                                                                                    |
| `ab_accounting_je_header`                                                                          | `account_id`, `doctype_id`, `line_ids`, `store_id`, `costcenter_id`, `is_posted`, `is_frozen`, `posted_date`, `all_confirmed`, `total_debit_val`, `total_credit_val`, `total_net_val`, `active`                                                                                  |
| `ab_accounting_je_line` / abstract `ab_accounting_je_line_common`                                  | `header_id`, `account_id`, `with_account_id`, `debit_val`, `credit_val`, `net_val`, `store_id`, `costcenter_id`, `doc_no`, `explain`, `due_date`, `settlement_date`, `is_confirmed`, `active`                                                                                    |
| `ab_accounting_je_header_delegate_common`                                                          | `je_header_id`, `je_header_ro_id`, and the existing delegation pattern.                                                                                                                                                                                                          |
| Header/line extensions in `ab_accounting_je_res_header.py`                                         | `res_header_ref`, `res_header_id` for links back to purchase/other business headers.                                                                                                                                                                                             |
| `ab_accounting_je_line_qry`                                                                        | Existing reporting projection for statements and account dimensions; harden branch filtering and verify against posted entries.                                                                                                                                                  |
| `ab_accounting_auth_group`, `ab_accounting_account_auth`, `ab_accounting_allowed_field_auth`       | Existing business account/document/field permissions; supplement with Odoo 19 ACLs, record rules, and protected workflow methods.                                                                                                                                                |

Keep `btn_post_je()`, `_check_validation()`, `btn_confirm_je()`, and the reviewer/freeze concepts. Keep `is_posted`,
`is_frozen`, and `is_confirmed` with their separate meanings; do not introduce an unrelated journal-state system that
disagrees with them.

Planned changes:

- Add fiscal-period closing, explicit posting identities, origin database, business-event reference, and linked
  reversal/correction journals. Do not claim these already exist.
- Enforce balanced debit/credit values using configured currency rounding and reject negative debit/credit values.
  Replace the current `< 0.99` balance tolerance and the purchase helper that silently zeroes any negative amount
  between `-1` and `0`.
- Preserve required account, branch, cost-center, due-date, and explanation validation. Treat account mappings as
  configuration validated before branch activation; no hardcoded account or branch IDs in posting logic.
- Posted economic entries are immutable, including for administrators. `btn_reverse_je()` currently archives an original
  line and adds a replacement inside the same header; replace that behavior with a separate balanced reversal journal
  linked to the original.
- Keep audit evidence visible. Archiving a posted line must never silently remove financial impact from balances.
  Correct posted dimensions through an auditable correction/reclassification operation.
- Preserve `je_header_id` on purchase documents, but remove cascade deletion and write-through changes to posted
  journals. Purchase `line_ids` are purchase lines; journal lines are always `je_header_id.line_ids`.
- Keep supplier mapping through `ab_supplier.costcenter_id` and existing claim relations. Do not substitute native Odoo
  `account.move` or a new custom accounting engine in this plan.

## 5. Shared posting, valuation, and identity rules

### Atomic and repeatable posting

A business document, its `ab_inventory` rows, corresponding `ab_accounting` journal, and outgoing durable queue event
commit together in one local transaction. Retry with the same operation identity returns the existing result; the same
identity with different content is rejected.

Use globally stable operation/source identities and explicit database provenance. Local `model_ref` / `res_id`
references remain useful, but are not global replication keys. A unique movement key must include an event and
line/allocation identity so partial receipts, split allocations, and reversals are possible. Mutable `status` must not
allow a second copy of an already posted event.

Lock and revalidate affected branch/source/location allocations before posting. Locks for first-time balance creation,
concurrent reservations, and duplicate submissions must also be covered. Keep posted rows immutable; pending proposals
may be changed only through their authorized document workflow. Do not rely on `search()` followed by `create()` as
duplicate prevention.

Treat `inventory_write()` as a business posting service, not an unrestricted balance setter. Remove its ability to
rewrite `saved` rows and remove `store_id or 78`. Validate branch ownership before any narrowly scoped elevation. Never
trust caller-supplied `sudo_confirm`, `eplus_replication`, or other context flags as authorization.

### Units, costs, and bonus stock

- Preserve integer smallest-unit `ab_inventory.qty`. A transaction in a larger UoM may be fractional only if conversion
  yields an exact allowed smallest-unit quantity; reject invalid conversion factors and fractional smallest units
  instead of truncating.
- Separate commercial `ab_product_source.unit_cost` from frozen inventory valuation per smallest unit. Related/computed
  prices on old ledger rows cannot be the historical valuation source.
- Existing purchase calculation uses paid `qty` for purchase value, taxes on `qty + bonus`, and receives `qty + bonus`.
  Preserve this behavior as a test case while agreeing the tax policy and invoice-discount allocation.
- Allocate the approved capitalizable receipt value over all received smallest units, including bonus quantity.
  Recoverable tax belongs in the tax account, not inventory valuation. Record allocated header discounts and rounding
  residues explicitly.
- Example before taxes/discounts: 10 paid packs at 100 plus 2 bonus packs, 10 small units per pack, means 120 received
  small units and 1,000 inventory value. The stock-unit cost is 1,000 / 120; multiplying 120 by the full paid-pack cost
  would overvalue stock.
- Later invoice differences create valuation adjustments linked to the source and journal, apportioned between stock
  still held and quantities already sold. Returns use original issue valuation plus traceable corrections.

## 6. Business workflows using the reused models

### Existing POS, returns, and controlled shortages

`ab_sales_inventory` reads branch-local `ab_inventory` balances grouped by `source_id` and obtains source data from
`ab_product_source`. Preserve `inventory_json = {"data": [...]}` and existing keys `store_id`, `product_id`,
`source_id`, `qty_in_small_unit`, `qty`, `price`, `cost`, and `exp_date`.

In the native path, `source_id` is the local `ab_product_source` ID, never an E-Plus `c_id`. `qty_in_small_unit` is
eligible stock in small units and `qty` remains in the large-unit basis expected by the current POS. Normalize `price`
and `cost` to that same POS basis; source prices may have been entered in another UoM. Keep legacy serial keys only as
optional mapping metadata, and prevent native IDs from reaching legacy SQL write paths.

Retain matching-selling-price allocation first, then the current other-price/expiry ordering, with stable identity as
tie-breaker. Re-read and validate actual availability at submission; browser JSON is display context. Persist exact
source allocations for stock, cost, and later returns. Service products have no physical stock movement; expired,
quarantined, and damaged stock cannot be sold normally.

Final sale submission posts the stock issue and revenue/valuation journal. Cashier settlement posts the payment and
clears the outstanding settlement balance. Drafts and pending call-center requests post neither stock issues nor
revenue. Customer returns reference original sale allocations and remaining returnable quantities; unsuitable goods
enter quarantine. Posted cancellations create reversals.

Keep permitted shortage sales with a mandatory reason. Allocate real available stock first, record uncovered quantity in
`ab_inventory_shortage`, and show the deficit in branch balances. Preserve the current 85% of selling-price fallback as
an explicitly provisional, unit-normalized estimate. Do not invent a physical source layer. Later approved receipts
settle shortages oldest first by branch/product, consume the quantity used to settle the deficit, and post the
difference between provisional and actual cost without rewriting the sale or original journal.

### Purchasing, receiving, notices, and supplier claims

Reuse `ab_purchase_header` / `ab_purchase_line` for supplier invoices and their source layers. Add order and receipt
tracking for partial delivery and three-way matching. An invoice must not create a second stock receipt when linked
receipt records have already posted.

For separate receipt/invoice timing, goods receipt debits inventory and credits goods-received clearing; the supplier
invoice clears that liability into supplier payable with configured tax and differences. For a simultaneous
receipt/invoice, retain the inspected accounting shape: supplier credit `net_invoice`, inventory debit
`net_invoice - net_tax`, and tax debit `net_tax`, subject to approved tax/valuation policy. Choose one path per event
and prevent both from firing.

Reuse debit/credit notices and supplier claims, including payment terms and distribution calculations. Link corrections
to original receipt sources and journals. Supplier return quantities and values must reconcile to actual
received/remaining stock; financial-only notices adjust value without moving goods.

### Transfers

Retain `ab_transfer` documents and one stable transfer UUID across source and destination databases. Source reserves and
dispatches through `ab_inventory_process`; destination validates and posts received quantities once. Preserve original
source identity, expiry, price basis, and carrying value when mapping a local destination `ab_product_source`.

Dispatch moves source inventory value into transit; receipt clears transit into destination inventory. Partial receipts,
damaged goods, missing quantities, and rejections stay explicitly open for reconciliation. Cancellation after dispatch
requires a return/reconciliation document. A mirror upload is not authorization to receive goods.

During mixed rollout, operators post the legacy side in its existing application and record matching references. Keep
this controlled manual bridge; no automatic E-Plus write bridge is included.

### Stock counts

`ab_stock_count` owns count sessions, blind counts, recounts, and approval. For the first release, block movements in
the branch/location/product counting scope until approved or cancelled. Approved differences create signed
`ab_inventory` adjustment rows and journal entries. Never replace balances directly.

### Cash and headquarters remittance

`ab_sales_cashier` owns payment/session records and expected drawer balances calculated from cash movements. Closing
records counted cash and approved differences.

`ab_cash_transfer` owns a separate dispatch/custody/receipt workflow. Branch dispatch posts cash to cash-in-transit;
headquarters acknowledgment posts transit to headquarters cash/bank. Unreceived amounts and discrepancies remain
visible. Every side has its own event identity; headquarters receipt and passive journal replication must not
double-post the remittance.

### Reporting, synchronization, and call center

Reuse existing queue infrastructure and the `event_uuid`, `db_serial`, and revision conventions after checking their
actual coverage. Resolve source/branch/product references using stable identity mappings, never by assuming integer IDs
match between databases.

Balance responses carry branch, product, on-hand/reserved/available quantities, source timestamp, revision,
completeness, and source system. Cross-branch browsing uses the reporting server then the last complete local
`ab_stock_report` snapshot. Show snapshot age; unknown/incomplete data must not appear as zero. Replace snapshots
atomically, including explicit zero balances, and reject older revisions.

The call center submits a uniquely identified request to the selected branch. Only that branch validates and creates
`ab_inventory_reservation` records. Unreachable branches remain pending confirmation; cached availability is never a
reservation. Persist cancellation requests, handle acceptance/cancellation races, and retry uncertain submissions with
the same identity.

Inventory and accounting projections at headquarters remain passive. Reconciliation compares branch movement/value
totals and journal totals with uploaded copies without executing operational workflow methods.

## 7. Required repairs before reusing the legacy code

These are observed source issues to address during implementation, not claims that this document fixes them.

| Evidence in inspected source                                                                                                                                    | Required repair / acceptance condition                                                                                                                   |
|-----------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------|
| `ab_inventory_process.inventory_write()` uses `store_id or 78`, omits inventory-header branch, and inconsistently returns a header record versus an integer ID. | Require a validated branch, set header ownership, and use consistent ORM references.                                                                     |
| Inventory header references use `P{id}` / `N{id}` / `O{id}`, while `btn_to_store()` searches `PUR-{id}`; sales and openings also reuse `O`.                     | Preserve the `header_ref` field but derive one collision-safe canonical reference from document/event identity and use it consistently.                  |
| `ab_inventory` duplicate constraint is `Check(1=1)`. Purchase accounting can still run after the base submit method returns early.                              | Real database uniqueness plus transaction-safe idempotency across inventory and journals; repeated posting creates no rows.                              |
| Opening headers become `saved` while movements remain `pending_main`.                                                                                           | Post approved opening stock and accounting atomically and make status agree with posted effects.                                                         |
| Source balances, pending-source SQL, and notice `last_inventory_id` omit branch filters.                                                                        | Branch-scope every read and report; verify two branches holding the same product/source cannot see or consume each other's rows.                         |
| Source writes can update movement quantity from source `qty` without its small-unit conversion; several overrides return from inside a loop.                    | Remove write-through to posted stock, normalize units, and support multi-record operations correctly.                                                    |
| Return quantity checks are commented out; purchase duplicate checks largely use onchange; placeholder net/notice quantities remain.                             | Enforce invariants through server-side posting/constraints, including RPC/import paths; implement actual returnable quantities.                          |
| Related inventory costs change with editable source fields; default expiry is an arbitrary future June date.                                                    | Snapshot posting value and validate real expiry/no-expiry policy; never fabricate opening batch facts.                                                   |
| Journal helpers allow broad admin/context bypasses, posted edits/deletion, and in-place line reversal.                                                          | Immutable posted entries, explicit balanced reversal journals, protected scope and state transitions for all roles.                                      |
| Journal balance tolerance is `< 0.99`; purchase helper clamps negative values below one unit to zero.                                                           | Currency-aware balancing and explicit rounding differences; reject invalid amounts rather than silently discarding value.                                |
| Pending and accounting SQL-view setup uses destructive drop/rebuild patterns; `extra_funcs.py` contains a foreign-key-dropping helper with an explicit commit.  | Do not carry schema workarounds or explicit commits into business workflows. Prefer ORM reports; review any necessary existing reporting SQL separately. |
| Purchase branch-group rules include unrestricted domains; opening record rules are empty; inventory/source ACLs are not a complete branch policy.               | Replace with module-owned Odoo 19 groups/privileges, bounded ACLs, and parent/child record rules. Test effective group combinations.                     |
| Source/journal delegation uses cascade deletion; current modules include Odoo 15 APIs, view syntax, and optional helper assumptions.                            | Preserve field names while repairing relation semantics and porting the code; fresh installation must prove dependency and registry correctness.         |

Security must cover source layers, inventory headers/lines, purchase/notice/claim/opening headers and children,
journals, reports, controller endpoints, and queued operations. UI domains are not record rules. Check manager/admin
privileges before inherited branch-role restrictions; elevated access must still respect operation ownership and
posted-data invariants. Keep groups, ACLs, privileges, and record rules in `security/`; do not create groups or
memberships in Python.

## 8. Delivery sequence and acceptance gates

### Phase 0 — Confirm and port the dependency foundation

Inventory the imported modules, model inheritance, field delegation, active imports, and required helper modules.
Preserve useful technical names. Port Python first, security next, then XML/actions, required runtime data, and tests.
Convert Odoo 15 APIs/views/assets to the repository's Odoo 19 conventions, including `models.Constraint`,
`fields.Domain`, `<list>`, expression modifiers, and supported display/search methods verified against the local Odoo 19
source.

Use clean installations by default. Do not add hooks, development-database migrations, automatic module installation
from Python, demo data, or direct SQL repairs. No deployed production schema migration is identified by this plan.

**Gate:** targeted clean installation of the five modules and required dependencies succeeds; delegated source/journal
fields resolve correctly; allowed/denied branch access works; no optional payroll/helper dependency breaks the registry.

### Phase 1 — Harden stock and accounting; implement approved openings

Repair `ab_product_source`, `ab_inventory`, and `ab_accounting`; implement the common adapter and complete
`ab_purchase_ob` posting. Add reservations, immutable valuation, source/operation identity, reversals, and period
controls where required.

The user supplies mapped opening data and configured accounts. Take a dedicated backup before import. Validate
branch/product/UoM/source mappings and reconcile opening quantities, inventory value, cash, and financial balances
before approval. No historical extraction is needed.

**Gate:** repeated opening submission has one effect; all approved openings are saleable as appropriate; stock rebuilds
from posted `ab_inventory` rows; stock value agrees with the inventory control account; unbalanced or duplicate openings
fail atomically.

### Phase 2 — Complete native purchase and supplier operations

Port existing purchase/notices/claims and connect them to the hardened posting service. Add partial receipt/order
tracking, receipt/invoice matching, branch acceptance, and original-source return limits. Ensure restocking is ready
before the branch POS pilot.

**Gate:** paid/bonus receipt, partial delivery, invoice, supplier return, financial-only notice, claim, and payment
distribution reconcile in quantity and value; repeated submission and reversed documents never duplicate stock or
journals.

### Phase 3 — Existing POS and cashier on native inventory

Implement `ab_sales_inventory`, native payments, returns, and shortage reconciliation. Remove unconditional SQL Server
calls/dependencies from native workflow cores; installing an adapter alone does not prevent inherited legacy methods
from running.

**Gate:** the current POS completes sale, payment, return, cancellation, reservation, and permitted shortage cycles with
B-Connect connections unavailable; concurrent last-unit sales cannot oversell without explicit shortage authorization.

### Phase 4 — Reporting, call center, transfers, counts, and remittance

Evolve `ab_stock_report`, add synchronization/call-center adapters, and complete native transfer/count/cash-transfer
workflows.

**Gate:** reporting outage shows dated fallback, branch outage leaves requests pending, retries create no duplicate
business effects, partial transfers and remittances retain transit balances, and every stock/cash change has an
authorized originating document and balanced journal.

### Phase 5 — Pilot and branch waves

For each branch: take a dedicated backup, stop legacy posting, load and approve final mapped openings at the agreed
cutoff, reconcile quantities/values/cash/journals, activate the native backend, and disable its legacy posting paths.
Monitor synchronization lag, shortages, transit, supplier balances, and journal reconciliation.

After native posting begins, do not switch back automatically to stale legacy balances. Recovery requires reconciliation
of intervening operations.

Retire remaining B-Connect dependencies in dashboards, smart transfers, recycling, customer lookup, and master-data
synchronization before declaring complete independence. The five reused modules provide the core, but do not by
themselves replace every external integration.

## 9. Verification and implementation discipline

Required business verification:

- Unit conversion round trips, invalid ratios, fractional larger units, and integer smallest-unit enforcement.
- Multiple source prices/expiries/costs, paid/bonus receipts, allocated discounts, tax separation, and late invoice
  differences.
- Two branches with overlapping product/source references; isolation on records, reports, RPC, controller calls, and
  queue handlers.
- Manager/admin access with inherited branch groups, plus posted-data immutability even for administrators.
- Concurrent last-unit sales/reservations, simultaneous first receipt, duplicate posting, interrupted posting, and
  conflicting retry payloads.
- Partial receipts/returns, financial-only notices, credit/debit signs, original valuation, and absence of duplicate
  invoice stock effects.
- Shortages followed by partial/full replenishment and valuation correction.
- Partial/duplicate transfer receipts, counting-scope locks, mixed legacy/native manual transfers, and cash-in-transit
  discrepancies.
- Reordered uploads, explicit zero snapshots, incomplete snapshots, cancellation races, and reporting outage fallback.
- Journal balancing, period closing, separate reversals, supplier claims, and opening stock/general-ledger
  reconciliation.
- A complete branch business cycle with B-Connect connections unavailable.

During implementation, maintain module-specific `changelog.d` files from inspected relevant commits and current diffs.
Preserve team/company author ownership and the required developer metadata for newly created modules. Keep production
addon packages runtime-only, with test evidence retained outside the final package.

Keep English UI source strings and both `i18n/ar.po` and `i18n/ar_001.po`. For translation work, export the module POT
from Odoo 19, merge without deleting unrelated translations, validate with `msgfmt --check-format`, and verify an Arabic
action/menu/view differs from `en_US` after the targeted upgrade. Run only targeted installation/upgrades on isolated
test ports; never `-u base` or stop the PyCharm-managed process for this work.

**Completion means:** branches sell, return, purchase, receive, transfer, count stock, settle cash, remit funds, and
produce accounting entirely in Odoo using the reused AB model families. Local operation survives reporting outages,
reporting copies remain passive, and no active branch business cycle needs B-Connect.
