# AB Independence: Nine Development Plans for a Four-Developer Team

## 1. Scope and architecture

Prepare **10 planning documents**:

- **One master plan** defining shared contracts, dependencies, team ownership, and release gates.
- **Nine implementation plans** covering your eight requested work items plus the necessary native POS/cashier integration.

The ninth plan is necessary because adding an ending balance will not, by itself, replace E-Plus calls inside sales, returns, and cashier operations.

This file contains the complete master plan and all nine implementation plans together for distribution.

### Confirmed decisions

- Reuse `ab_inventory`, `ab_product_source`, `ab_purchase`, `ab_purchase_ob`, `ab_taxes`, and `ab_accounting`.
- Retain the existing POS window.
- Add **`ab_purchase_accounting`** and **`ab_sales_accounting`** as optional accounting adapters.
- Preserve the existing journal models: **`ab_accounting_je_header`** and **`ab_accounting_je_line`**.
- Installing an adapter enables automatic journal creation and posting when a supported business operation is finalized.
- Installation does not create transaction journals, backfill historical documents, or generate opening balances.
- You manually supply inventory openings and opening journals for cash/POS, suppliers, customers, inventory value, and other accounts.
- Later non-purchase receipts receive automatic journals through `ab_purchase_accounting`.
- Use a current inventory balance table plus an `ending_balance` column on posted inventory movements.
- Preserve fractional quantities for products that permit them.
- Purchase tax calculation is included. Sales-tax calculation is deferred.
- “Sales notices” means physical customer returns for this release. Standalone customer debit/credit notes are deferred.
- Purchasing initially retains the existing invoice/receipt-approval workflow. Separate purchase orders and partial-receipt applications are deferred.
- The accounting UI uses native Odoo lists, forms, search views, actions, and reports.

### Module boundaries

| Module | Owns | Must not own |
|---|---|---|
| `ab_taxes` | Tax definitions and purchase calculation rules | Journal posting or stock posting |
| `ab_product_source` | Source identity, product/UoM, expiry, commercial prices and costs | Current stock balances |
| `ab_inventory` | Movements, current balances, reservations, shortages, integrity checks | Purchase/sales journal generation |
| `ab_purchase` | Purchase documents, receipt approval, supplier returns/notices | Accounting models or automatic journals |
| `ab_purchase_ob` | Inventory openings and approved non-purchase receipts | Automatic opening journals |
| `ab_accounting` | Accounts, journals, posting service, periods, reversals, accounting UI | Purchase/sales-specific business logic |
| `ab_purchase_accounting` | Purchase, supplier return/notice, and non-purchase receipt accounting | A second inventory or journal engine |
| `ab_sales_inventory` | Native POS, return, and cashier integration | Account mapping and journal construction |
| `ab_sales_accounting` | Sales, returns, payments, refunds, and related cost corrections | Stock allocation or sales-tax calculation |

The previously proposed broad `ab_inventory_accounting` adapter is **not part of this release**. Journal ownership belongs to the two requested accounting adapters. Future transfer/count accounting must be assigned explicitly when those workflows are planned.

## 2. Shared contracts that must be agreed before concurrent implementation

### Automatic journal contract

Both adapters call one posting service in `ab_accounting`.

Each journal request identifies:

- Originating database, company, and branch.
- Business document and event type.
- Unique operation identity.
- Posting date and currency.
- Debit/credit lines, account mappings, and partner/cost-center dimensions.
- Original event where the operation is a return, reversal, or correction.

The service validates permissions, period status, required dimensions, and currency-aware balancing.

**Exactly-once business effect:**

- Repeating an identical operation returns its existing journal.
- Reusing an operation identity with different amounts or scope raises an error.
- Economic corrections create linked adjustment/reversal journals.
- Posted journals cannot be edited or deleted, including through administrator or context-flag bypasses.

Business approval, stock posting, journal posting, and any existing synchronization outbox capture occur in **one local transaction**. If an installed adapter cannot post its required journal, the whole operation fails.

Journal headers and lines are created through ordinary business posting methods—not installation hooks or computed fields.

### Optional installation and activation

- `ab_purchase` and native sales/inventory operations must work without accounting adapters.
- When an adapter is installed, its required mappings must be complete before supported operations can be finalized.
- Each branch has an explicit accounting activation cutoff.
- Historical finalized documents are not automatically replayed.
- Draft documents finalized after activation are eligible for automatic posting.
- Opening documents remain explicitly excluded from automatic journal generation.
- Adapter installation uses manifest dependencies; no Python auto-installation.

Use explicit journal links instead of delegated journal inheritance. Preserve `je_header_id` where useful, add links for multiple events/reversals, and avoid cascading deletion of financial records.

### Inventory balance contract

Keep `ab_inventory` as the signed movement ledger.

Add **`ab_inventory_balance`** for current balances, scoped by:

```text
company + branch + product + location + source/cost layer
```

The balance row stores:

- On-hand quantity.
- Reserved quantity.
- Available quantity.
- Last posting sequence/revision.

Each posted `ab_inventory` movement stores its **`ending_balance`**, representing the scoped on-hand quantity immediately after that movement.

Posting must:

1. Validate the business document and branch.
2. Lock or safely create the relevant balance rows.
3. Revalidate available stock and reservations.
4. Create the movement and update balances atomically.
5. Store its posting sequence and ending balance.

A backdated document retains its business date but receives the next posting sequence. It does not silently rewrite earlier movement snapshots.

The POS reads the balance table. It does not calculate stock by summing all historical movements.

The integrity checker independently compares:

- Posted ledger totals against current balance rows.
- Movement-by-movement running totals against stored ending balances.
- Reservation records against reserved quantities.

Repairs are explicit, authorized, audited operations. They must not invent quantity adjustments merely to hide a projection error.

### Units, source identity, and valuation

- Normalize stock quantities into the product’s smallest stock unit.
- Support configured fractional quantities; reject invalid precision instead of rounding silently.
- Provide one tested conversion contract between legacy `ab_uom` and current sales `ab_product_uom`.
- Snapshot the conversion basis and actual valuation used at posting.
- Give each source a stable identity independent of local integer IDs.
- Preserve optional legacy item, branch, class, and database references.
- Keep separate receipt-cost layers where costs differ.
- Selling-price changes do not revalue historical stock movements.

Authorized shortages remain separate from physical source layers. Their negative quantities must appear once in availability, with provisional valuation and later reconciliation.

## 3. The nine implementation plans

### Plan 01 — Port and decouple `ab_purchase`

**Owner:** Developer C  
**Depends on:** Shared source, tax, and inventory contracts; completed implementations for final integration.

**Deliverables**

- Port Python, security, XML views, actions, and required dependencies to Odoo 19.
- Remove the direct dependency on `ab_accounting`.
- Extract journal generation, journal delegation, accounting fields/views, supplier claims, financial reports, and accounting-specific security into `ab_purchase_accounting`.
- Preserve purchasing document model names and existing business identifiers.
- Retain invoice capture, validation, receipt review, source creation, paid/bonus quantities, and supplier returns/notices.
- Preserve the existing purchase status keys, with explicit authorized transitions.
- Pending receipt documents do not increase saleable stock. Final branch acceptance posts stock once.
- Create immutable inventory posting events through `ab_inventory_process`.
- Replace placeholder returnable quantities with accepted receipts minus previous returns.
- Separate physical supplier returns from financial-only price corrections.
- Remove hardcoded branch fallbacks and source-to-stock write-through behavior.
- Expose business posting extension methods for the optional accounting adapter.

**Acceptance**

- Clean install and complete purchase/return workflow without `ab_accounting`.
- Paid and bonus quantities produce correct source layers and stock.
- Repeated approval does not duplicate inventory.
- Returns cannot exceed eligible quantities.
- Branch users cannot access another branch’s documents or lines.

**Deferred:** separate purchase orders, partial receipts, and three-way matching.

### Plan 02 — Port `ab_accounting` and build the new UI

**Owner:** Developer B  
**Depends on:** Shared journal contract; otherwise independent of inventory and purchasing.

**Deliverables**

- Port the existing account hierarchy, document types, journal models, and permissions.
- Remove incidental legacy dependency requirements; keep only dependencies actually required by active functionality.
- Implement the shared journal posting service.
- Replace the `< 0.99` balancing tolerance with currency-aware checks.
- Remove silent amount clamping and broad administrator/context bypasses.
- Add posting identities, period locks, source references, and separate balanced reversals.
- Preserve reviewer/freeze concepts without allowing changes to posted economic values.
- Support manual opening journals with branch, account, partner/cost-center, date, and opening-run reference.
- Provide opening balance reconciliation reports.

**Native Odoo UI**

- Journal headers with status, totals, branch, source document, and posting/reversal actions.
- Journal line entry with account, debit, credit, dimensions, and clear validation.
- Account hierarchy and account configuration.
- General ledger, trial balance, account statements, and opening-balance filters.
- Direct navigation between generated journals and their business documents.
- English source labels and Arabic translations.

**Acceptance**

- Clean installation without purchase or sales modules.
- Manual and generated journal posting use the same controls.
- Unbalanced, duplicate, unauthorized, or closed-period entries fail.
- Posted entries remain immutable; reversals are separate and traceable.
- Reports reconcile to posted lines and include manually entered openings.

### Plan 03 — Build `ab_purchase_accounting`

**Owner:** Developer C  
**Depends on:** Plans 01, 02, 06, and 07; stock valuation contract from Plan 05.

**Dependencies:** `ab_purchase`, `ab_purchase_ob`, `ab_accounting`, with direct dependencies declared for any additional models used.

**Deliverables**

- Move purchasing accounting functionality out of `ab_purchase`.
- Preserve supplier claims and settlement/reporting functionality under this adapter.
- Add explicit journal relations and inherited accounting views.
- Generate journals automatically at final approval of purchases and supplier returns/notices.
- Use the approved purchase tax/value snapshot, not a fresh calculation from potentially changed source fields.
- Post physical returns using original receipt valuation.
- Financial-only notices adjust value without creating stock quantity.
- Handle later cost corrections through linked adjustment entries.
- Generate journals for approved non-purchase receipts using their configured offset accounts.
- Explicitly exclude opening-stock documents from automatic journals.

**Posting ownership**

| Event | Accounting treatment |
|---|---|
| Accepted purchase | Inventory and configured tax against supplier balance |
| Physical supplier return | Reverse the applicable supplier, tax, and inventory amounts |
| Financial-only notice | Adjust the appropriate supplier/value accounts without stock quantity |
| Non-purchase receipt | Inventory against the approved receipt-type offset account |
| Opening inventory | Manual opening accounting; no automatic duplicate |

**Acceptance**

- Installing the adapter enables future automatic journals.
- Existing finalized documents are not backfilled.
- Each supported event creates one balanced financial effect.
- Missing mappings roll back stock/document posting.
- Manual inventory opening values are not posted a second time.
- Purchase accounting screens and claims are absent when the adapter is absent.

### Plan 04 — Build `ab_sales_accounting`

**Owner:** Developer B  
**Depends on:** Plans 02 and 09; allocation/valuation contract from Plan 05.

**Dependencies:** `ab_sales_inventory`, `ab_sales_cashier`, and `ab_accounting`.

**Deliverables**

- Generate sale, physical return, payment, and refund journals.
- Final sale submission posts revenue/settlement and stock-cost effects.
- Cashier collection clears the settlement balance into the configured cash/payment account.
- Returns reverse the relevant sale and original issue valuation.
- Refunds reverse the relevant payment effect.
- Handle approved cashier differences using configured accounts.
- Generate linked cost corrections when provisional shortage costs become actual.
- Add journal links to sales, return, and payment records.
- Use existing customer/contract payer allocations so combined receivables equal the sale total.

**Boundaries**

- No new sales-tax calculation or assumed tax rates.
- No standalone customer debit/credit-note application in this release.
- No opening journal generation.
- No stock allocation inside this adapter.

**Acceptance**

- Sale, payment, return, and refund create distinct, nonduplicated events.
- Repeated cashier requests cannot collect or journal twice.
- Returns use original cost and remaining returnable quantity.
- An incomplete accounting configuration blocks finalization atomically.
- Revenue and cost are not reposted when the cashier collects payment.

### Plan 05 — Port `ab_inventory` and implement stored ending balances

**Owner:** Developer A  
**Depends on:** Plan 08 and the shared quantity contract.

**Deliverables**

- Port the inventory models and fix the header relation to a real `Many2one`.
- Replace ineffective duplicate constraints and unsafe reference generation.
- Remove default branch `78`.
- Implement `ab_inventory_balance`, reservations, posting sequences, and movement `ending_balance`.
- Replace integer-only quantity handling with controlled fractional precision.
- Store product ownership explicitly so shortages do not require a fabricated physical source.
- Add structured locations for saleable, quarantine, damaged, and transit stock.
- Freeze posted quantities, conversion bases, and valuation.
- Keep pending inbound stock separate from on-hand stock.
- Restrict posting, reversal, and status transitions to authorized workflows.
- Add an integrity report and explicit balance-projection rebuild action.
- Provide batch availability and posting APIs for purchasing and POS.

**Shortages**

- Preserve authorized shortage sales with a mandatory reason.
- Use the existing 85% selling-price estimate as explicitly provisional cost.
- Reconcile later receipts against shortages oldest first by branch/product.
- Expose cost-correction events to the sales accounting adapter.
- Prevent double consumption or double counting of the deficit.

**Acceptance**

- Concurrent last-unit sales/reservations remain correct.
- Simultaneous first receipts cannot create duplicate balance rows.
- Repeated events have one effect.
- Current balances and movement ending balances match independent ledger calculations.
- Pending stock is not saleable.
- Projection repair preserves original movement quantities and values.

### Plan 06 — Port `ab_taxes` for purchasing

**Owner:** Developer A  
**Depends on:** None of the purchase or accounting engines.

**Deliverables**

- Port tax definitions and configuration screens.
- Provide deterministic purchase-tax calculations shared by sources and purchase documents.
- Preserve percentage and “apply on total” concepts.
- Explicitly distinguish tax included in inventory cost from separately posted tax.
- Define configurable treatment of discounts, bonus quantities, and rounding.
- Store the approved tax calculation on finalized business documents.
- Prevent changes to tax settings from altering historical transaction values.
- Keep government tax-invoice retrieval/submission functionality outside this delivery’s active calculation path.

**Acceptance**

- Approved examples cover exempt purchases, normal taxes, compound calculations, discounts, bonus stock, and returns.
- Header totals reconcile to line/tax/rounding components.
- Purchase operations do not require an external tax-service connection.
- `ab_sales` does not acquire a new tax-calculation dependency.

**Business input:** Finance supplies approved example invoices and tax treatment; the implementation does not infer rates or policy.

### Plan 07 — Port `ab_purchase_ob` for openings and other receipts

**Owner:** Developer C  
**Depends on:** Plans 05 and 08.

**Deliverables**

- Support two explicit document purposes:
  - **Opening inventory**.
  - **Non-purchase receipt**.
- Require branch, source details, quantities, UoM, value, date, and receipt reason.
- For non-purchase receipts, configure receipt types used by the accounting adapter to select offset accounts.
- Remove unnecessary purchase/accounting coupling from the core module.
- Stage manually supplied openings, validate them, and post approved movements once.
- Preserve source provenance without requiring E-Plus identifiers for new sources.
- Link opening documents to an opening-run/cutoff reference.
- Restrict opening mode after the branch’s opening run is closed.
- Reverse posted mistakes through linked corrective documents.

**Boundaries**

- This module records receipts that are not supplier purchases.
- It does not replace transfer receipts, sales returns, or stock-count approvals.
- Operators must not record the same arrival through both this module and its owning workflow.

**Acceptance**

- Approved openings immediately appear in the correct inventory balances.
- Repeated import/approval does not duplicate stock.
- Opening stock creates no automatic journal.
- A later non-purchase receipt creates a journal only when `ab_purchase_accounting` is installed and configured.
- The module works without the accounting adapter.

### Plan 08 — Port `ab_product_source` for every inventory origin

**Owner:** Developer A  
**Depends on:** Plan 06 and existing product foundations.

**Deliverables**

- Support purchase receipts, openings, other receipts, transfer-in provenance, and approved adjustments.
- Retain useful product, price, cost, expiry, discount, bonus, and tax fields.
- Add stable source identity, source type, originating document, branch/database provenance, and optional legacy mappings.
- Remove fabricated default expiry dates.
- Define explicit no-expiry handling for applicable products.
- Separate physical lot identity from receipt-cost-layer identity.
- Freeze source economics used by posted movements.
- Record price-change history.
- Provide tested conversion methods for both UoM systems.
- Remove source edits that directly overwrite inventory movements.

**Acceptance**

- Every supported source origin can create a valid source without a purchase invoice.
- Equal expiry/price does not incorrectly merge distinct cost layers.
- Conversion round trips preserve allowed quantities.
- Invalid factors and forbidden fractions are rejected.
- Editing source metadata cannot rewrite historical inventory valuation.

### Plan 09 — Connect existing sales and cashier to native inventory

**Owner:** Developer D  
**Depends on:** Plan 05; shared source/UoM contract from Plan 08.

**Deliverables**

- Implement `ab_sales_inventory` while preserving the POS window.
- Replace native-path E-Plus reads/writes for availability, source allocation, sales, returns, and cashier settlement.
- Read availability from `ab_inventory_balance`.
- Preserve the existing POS inventory payload shape through an adapter.
- Select matching-price sources first, then the existing fallback price/expiry ordering.
- Revalidate and persist exact allocations at posting.
- Exclude expired, quarantined, and damaged stock from normal sale.
- Implement branch-owned reservations and authorized shortage handling.
- Create native payment/refund records and cashier balances.
- Expose finalized business events consumed by `ab_sales_accounting`.
- Preserve current promotions, contracts, employee permissions, price badges, and UoM behavior.
- Isolate legacy backend behavior so a native operation cannot also execute E-Plus posting.

**Acceptance**

- A full sale/payment/return/refund cycle works with SQL Server unavailable.
- POS searches and batch reads do not aggregate the full movement ledger.
- Double-clicks and request retries cannot duplicate stock or payments.
- Cashier settlement does not consume stock a second time.
- The existing POS extensions remain functional.
- Historical-return requests without imported original transactions follow an explicit manual process rather than guessing allocations.

## 4. Four-developer distribution and concurrency

### Ownership

| Developer | Primary plans | Shared-file ownership |
|---|---|---|
| **A — Inventory foundations** | 06 Taxes → 08 Product Source → 05 Inventory | Product/UoM conversion changes required by these plans |
| **B — Accounting** | 02 Accounting/UI → 04 Sales Accounting | Accounting core and shared journal API |
| **C — Purchasing** | 01 Purchase → 07 Openings → 03 Purchase Accounting | Purchase extraction, receipt workflows, purchase adapter |
| **D — POS and integration** | 09 Native Sales/Cashier; release integration | `ab_sales`, `ab_sales_cashier`, native POS integration |

This groups tightly related work and avoids two developers editing the same core module simultaneously.

### What can run concurrently?

| Stage | Developer A | Developer B | Developer C | Developer D |
|---|---|---|---|---|
| **Start** | Tax/source foundation | Accounting port, API, UI | Purchase decoupling and Odoo 19 port | POS dependency inventory and native adapter development |
| **Foundation integration** | Inventory balances/posting | Accounting validation and opening UI | Purchase stock integration, opening/other receipt workflow | POS stock integration and native cashier |
| **Accounting adapters** | Concurrency and integrity verification | Sales accounting | Purchase accounting | End-to-end POS/cashier integration |
| **Release candidate** | Stock reconciliation | Journal reconciliation | Purchase/opening reconciliation | Install matrix, outage tests, full business-cycle verification |

Developers C and D can begin using **development-only contract tests and fakes** while A completes inventory. These are not production fallback implementations.

Accounting adapters can be designed against the journal contract early, but final acceptance waits for real business posting integration.

### Coordination rules

- Freeze the first version of posting, UoM, balance, and journal contracts before implementation branches diverge.
- Each developer owns edits in their assigned modules.
- Changes to another developer’s core contract go through that owner.
- Developer C performs the purchase/accounting extraction once; B supplies accounting contracts without separately refactoring purchase files.
- Developer D owns base sales/cashier changes; B implements journal behavior in `ab_sales_accounting`.
- Merge a working vertical slice early: source → receipt → inventory balance → journal.
- Do not wait until all nine plans are finished to test integration.
- Developer D coordinates release verification; each owner fixes defects within their modules.

## 5. Release gates, manual openings, and remaining roadmap

### Required release gates

1. **Independent installation**
   - Accounting without purchasing/sales.
   - Purchasing and openings without accounting.
   - Native sales/inventory without sales accounting.
   - Each accounting adapter with its declared dependencies.
   - All modules together.

2. **Operational integrity**
   - Branch isolation on headers, lines, sources, balances, journals, and APIs.
   - Duplicate/conflicting request protection.
   - Concurrent stock allocation and first-balance creation.
   - Correct fractional units, multiple source prices, bonus stock, and returns.
   - Atomic rollback when accounting fails.
   - Ledger totals equal stored balances and ending-balance snapshots.

3. **Financial integrity**
   - Manual openings reconcile to control accounts and branch dimensions.
   - Purchase and sales events post exactly once.
   - Cash collection/refunds do not repost revenue or stock.
   - Posted values remain immutable.
   - Period locks, reversals, and shortage corrections work correctly.

4. **POS and performance**
   - Existing POS workflow completes with B-Connect unavailable.
   - Representative branch data proves that POS balance reads use current balance rows rather than ledger-wide totals.
   - Compare response times with the existing POS baseline and reject a performance regression before pilot activation.

### Manual opening procedure

For each branch:

1. Take a backup and establish the cutover time.
2. Load and approve physical opening stock through `ab_purchase_ob`.
3. Enter manual opening journals in `ab_accounting`, including supplier/customer and POS/cash dimensions.
4. Reconcile stock quantity, stock value, cash, supplier, customer, and other opening accounts.
5. Close the opening run and activate automatic accounting for new operations.
6. Confirm that opening inventory has not produced a duplicate financial opening.

Opening balances establish the starting position. New journal amounts are calculated from each new transaction and its source allocations; reports combine those movements with the approved openings.

### Work retained for later independence phases

The following remain part of the larger B-Connect independence roadmap, outside these nine implementation plans:

- Reporting-server consolidation and `ab_stock_report` fallback.
- Call-center request/acknowledgment workflows.
- Native branch transfers and transit accounting.
- Stock counts and adjustment accounting.
- Cash remittance to headquarters.
- Separate purchase orders and partial receipts.
- Sales-tax calculation and standalone customer financial notices.
- Retirement of remaining dashboard, recycling, customer, and master-data dependencies.

Completing these nine plans establishes native branch purchasing, inventory, sales, cashier, and accounting. It does not by itself complete every cross-branch and reporting requirement.

### Planning document set

The combined content in this file can be distributed as the following document set:

```text
00_master_coordination_plan.md
01_ab_purchase_plan.md
02_ab_accounting_plan.md
03_ab_purchase_accounting_plan.md
04_ab_sales_accounting_plan.md
05_ab_inventory_plan.md
06_ab_taxes_plan.md
07_ab_purchase_ob_plan.md
08_ab_product_source_plan.md
09_ab_sales_inventory_plan.md
```

Every implementation plan follows repository requirements: clean installation by default, no lifecycle hooks or development-database migration code, scoped security, English source strings with both Arabic translations, module changelogs, targeted Odoo 19 validation, and test evidence retained outside production addon packages.
