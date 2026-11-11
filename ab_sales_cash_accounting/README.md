# Sales cash accounting adapter

This addon connects operational `ab_sales_cash_shift` records to
`ab_accounting_cash` and the existing Accounting journal engine. Core sales,
purchase, cumulative inventory and tax calculations remain unchanged.

| Operation | Accounting effect |
| --- | --- |
| Prepare first funded opening | Debit cashier-wallet control; credit branch treasury |
| Close wallet sales batch | Debit payment-method accounts; credit sales; debit returns for refunds; post frozen stock cost |
| Record count discrepancy | Adjust drawer against pending cash differences |
| Send counted closing cash | Debit cash in transit; credit cashier-wallet control |
| Treasury confirms receipt | Debit treasury; credit cash in transit |
| Finance approves discrepancy | Clear pending difference to approved shortage or surplus |
| Carry forward to the next employee | No new journal; that cash remains in the cashier-wallet control account |

The physical count determines treasury transfer and carry-forward float. Card,
wallet and other payments stay in separate clearing accounts and are never added
to physical drawer cash. Payment-provider charging, provider reconciliation and
bank settlement are outside this adapter.

Sales retains the original Cashier screen. Sales → Cash Management contains the
operational wallet ledger and payment breakdown. Accounting → Cash Management contains account mappings, posted links,
treasury/drawer/payment-method setup, transfers and Finance review. Existing XML
IDs and model ownership are preserved. Finance receives operational closing
reports without moving POS code into Accounting.

A dedicated non-password-provisioned integration user is declared in security XML.
Explicit account/document authorizations and allowed branch/company configuration
must be provided before enabling accounting. The pilot authorizes only branches
29 and 140 and their new accounts. Enabling the module alone does not configure
branch accounts or post money.

The validated baseline uses tax-exempt stock, no bonus quantities and no
invoice-level discount. Automatic closing rejects nonzero sales tax, taxed stock,
bonus stock and invoice discounts pending an approved valuation allocation. These
checks prevent silent differences between the existing stock cost and purchase
journal value. They do not change the underlying calculations. Existing physical
opening inventory has not been assigned an invented financial opening value.
Finance must supply/approve that opening valuation before general use with old
stock. A failed accounting close rolls back the closing operation.

Closing data is local to `rip_bconnect`. No central destination, remote posting or
Odoo-to-Odoo synchronization is activated in this phase. A future sync adapter must
retain branch/database identity and idempotent source-operation references.
