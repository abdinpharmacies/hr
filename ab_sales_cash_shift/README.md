# Shared cash drawer and shift handover

This optional adapter implements one shared physical cash drawer per native Odoo
branch. It preserves the existing sales submission, cashier stock posting,
returns, cumulative inventory, pricing and tax calculations. Installing it does
not configure or enable any branch. No remote synchronization is enabled.

The Cairo schedule is 00:00–08:00, 08:00–16:00 and 16:00–00:00. Periods use the
Africa/Cairo timezone, including its daylight-saving transitions; stored timestamps
are UTC and Odoo displays them in the user's timezone. These are fixed local-clock
periods, which need not span exactly eight elapsed hours on a clock-change date.

## Operating flow

1. A cash configuration manager configures the branch treasury and its receiving
   employee, company payment methods and the branch drawer. Configuration must
   be reviewed before enabling a drawer; accepted methods may include cash, cards,
   electronic wallets and other methods, including multiple providers.
2. The manager prepares the first opening float for an authorized cashier. A
   treasury-to-drawer transfer records the initial funding when the amount is
   nonzero. The incoming cashier must physically count and accept that exact
   opening before the drawer can process sales.
3. Use **Sales → Cash Management → Shift Cashier**. **Drawer Handover** opens acceptance or closing.
   Saving an invoice opens a payment breakdown; the sum must equal the amount due
   at company currency precision. Non-cash references are required when configured.
   Only cash payments change physical drawer cash. These records acknowledge
   payments; they do not charge cards or call wallet/payment-provider APIs.
4. Only the designated employee can settle payments/refunds for the current
   scheduled period. Sales staff may prepare drafts; submission requires an
   accepted current drawer, and cashier settlement still controls stock posting.
   Payment, stock, tender rows and drawer totals share one rollback boundary.
5. Closing records expected cash, physical count, discrepancy explanation, next
   cashier, manually retained float and the destination treasury. A discrepancy
   does not block closure. The treasury transfer equals count minus retained float.
   The transfer remains awaiting receipt until its designated employee confirms it.
6. The next opening must be physically accepted by the designated incoming cashier.
   Posting remains blocked outside the scheduled period, even if accepted early.
   A manager may reassign an unaccepted opening or roll it forward after a missed
   period, retaining its amount and recording old/new assignment details and reason.
7. Finance reviews differences after closure, recording reviewer, timestamp and
   decision note. This does not rewrite the original counted amount or variance.

The responsible cashier needs the existing native sales/cashier permissions,
assigned inventory branch and a valid employee PIN session authorized for that
branch. The receiving treasury employee uses an authorized active cashier session
for the branch to acknowledge receipt. Finance review itself needs only the Finance
review role and allowed company; it does not require cashier or inventory access.
Cash configuration managers also need authorized inventory branch access for
opening preparation and reassignment. No permanent employee/user permissions are
provisioned by this addon.

## Reports and integrity

**Sales → Cash Management** contains **Cash Shifts**, **Treasury Transfers**,
**Shift Payment Breakdown** and **Pending Finance Review**. The same section
contains **Branch Treasuries**, **Cashier Payment Methods** and **Shared Cash Drawers**
for authorized configuration managers. Create the treasury and methods first, then
the drawer; enable it and use **Prepare First Opening** to assign the first cashier
and cash amount. These values can be entered through the setup screens. Every tender retains its settlement,
branch, employee and employee-session link. Refunds belong to the shift paying them,
retain their original sale and cannot exceed the unrefunded amount for each original
payment method. Insufficient physical drawer cash blocks a cash refund.

The older per-user cash projection is hidden for enabled shared drawers; it is not
the shared drawer's cash balance. The original payment report shows accumulated
collections, which can include non-cash receipts. Closed cash records reject direct
ORM changes/deletion. Technical store locks and unique payment/period constraints
protect retries and concurrent posting. Configuration cannot disable a drawer once
it has cash history. Records stay local to the branch database; no central posting
or synchronization queue is installed by this module.

Treasury transfers are operational cash custody records, not general-ledger journal
entries or bank settlement records. Mid-shift treasury top-ups, payment-provider
reconciliation, journal posting and reporting-server synchronization are separate
integration work. Historical invoices settled before cash-shift activation require
historical refund review because they have no captured tender breakdown.

## Validation and activation

Validation scripts live under `scripts/stock_integration_validation/`, outside the
runtime addon. On 2026-10-19 the module was installed and tested on `rip_bconnect`
using only branches 29 and 140. Initial workflow fixtures were rolled back.
After explicit user approval, the marked full cycle was committed for both
branches and independently verified. Both drawers are enabled; their next
openings retain 10 each and await the incoming employee's receipt confirmation
for 20 October 2026 at 00:00 Cairo time. See
`scripts/stock_integration_validation/CASH_ACCOUNTING_REPORT.md` for retained
record IDs, accounting balances and valuation limits.

When `ab_sales_cash_accounting` is installed, financial setup, transfers and Finance
review move to Accounting → Cash Management. The adapter posts journals without
changing the operational models described above. The native cashier remains a
separate action; enabled shared drawers must use **Shift Cashier**.
