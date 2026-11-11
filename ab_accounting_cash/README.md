# Branch cash accounting

This optional addon owns branch cash account mappings and immutable links to posted
`ab_accounting_je_header` journals. It does not depend on Sales and does not create
operational cash shifts. Install the Sales bridge to connect shift operations.

Accounting → Cash Management → Branch Cash Accounts shows the drawer, treasury and
cash-in-transit balances from posted journal lines. These are branch-filtered
ledger balances, not editable balance fields. Drawer and treasury use separate
final accounts under the same branch. Branch code is the primary local account
identifier; the optional database relation retains `ab_replica_db.db_serial`.

Configuration is Accounting Manager only. Each account must be an active final
account with branch balances, the correct account type and posting-user access.
The integration respects native account/document authorizations. Accounting users
retain the existing forbidden-store rules; cashiers gain no accounting rights.
Company rules also apply. Configuration with posted history cannot be reassigned.

Posting is private to validated adapters. Each operation has one immutable link
and a saved journal-line snapshot. Repeating an operation returns its existing
entry only when its financial values, source and branch agree. Translated
reference labels do not create duplicate journals. Cashier posting users are not
given Finance or accounting configuration access.

The live pilot uses `BR29-<ROLE>` and `BR140-<ROLE>` codes. Both branches currently
belong to database serial 102; the serial alone would not distinguish their
accounts. Setup is explicit, not an installation hook. No historical journals or
opening inventory values are automatically backfilled.
