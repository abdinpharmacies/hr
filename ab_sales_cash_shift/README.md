# Cashier wallet handover

This optional Odoo 19 adapter keeps the original `ab_sales.cashier` screen as the
only operational cashier interface and adds an immutable employee wallet ledger
for native-inventory branches. Installing the module does not enable a branch or
change legacy E-Plus behavior.

## Operating flow

1. A cash manager configures the branch treasury, accepted payment methods and
   wallet control record. Each enabled branch can have only one active employee
   wallet.
2. Pending invoices remain visible without a wallet, opening acceptance or time
   period. The first successful collection opens a zero-balance wallet for the
   employee identified by the active PIN session inside the same transaction.
3. Only the active wallet owner can collect or refund. Another employee must wait
   for a formal handover. The original Cashier save flow records the full due
   amount as cash, while refunds reuse the original payment-method allocation.
4. **Hand Over and Close Wallet** records the physical count and splits it between
   the branch treasury and the next employee's opening balance. The split must
   equal the count. A shortage or surplus is retained for Finance review and does
   not prevent closure.
5. A positive carry-forward requires an authorized next cashier and opens that
   employee's wallet immediately. Receipt confirmation is audit-only and does not
   block invoice viewing or collection. A full treasury deposit needs no next
   cashier; the next collection opens a new zero-balance wallet.
6. Treasury receipt confirmation moves the closing transfer from pending to
   received without blocking POS operations. Closed wallets, events, tenders and
   transfers reject direct changes and deletion.

## Inventory and external systems

`ab_sales_inventory` owns stock. Native sale approval deducts stock once, sending
an approved native return to the cashier restores stock once, and payment/refund
collection creates no inventory movement. Native branches do not call E-Plus.
Legacy branches continue through the original cashier and E-Plus routes.

## Reporting and accounting

Closed wallets provide an attachment-backed QWeb PDF showing branch, employee,
opening/closing times, payment-method collections and refunds, expected and
counted cash, difference, treasury amount, carry-forward, next cashier and audit
references. Reprinting reuses the stored attachment and never repeats a financial
operation.

When `ab_sales_cash_accounting` is installed, all employee wallets use the shared
cashier-wallet control account. Closing moves only physical cash sent to treasury
into cash in transit; treasury receipt moves it into the branch treasury account.
Card, wallet and other noncash tenders remain in their clearing accounts. Employee
subledgers stay separated by immutable wallet and event records.

The legacy `shift_cashier_action` XML ID remains as an alias of
`ab_sales.cashier`, while its duplicate menu is inactive. Historical scheduled
fields and records remain available for audit and migration compatibility.
