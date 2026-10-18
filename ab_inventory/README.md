# Abdin Inventory

`ab_inventory` owns the native stock ledger, current balances, reservations,
source allocation, locations and shortage reconciliation. It has no external
SQL Server connection and does not post accounting entries.

The isolated phases 1–6 validation is recorded in
`ab_independence_dev_plans/13_phase_1_6_execution.md`. Business tax approval,
production-scale performance and rollout remain separate release decisions.

## Stock contract

- Quantities use the product's configured smallest stock unit and increment.
  Unsupported fractions, non-finite values and zero movements are rejected.
- Pending receipts do not contribute to stock. Posting atomically freezes the
  source inputs, appends an immutable movement and updates its current balance.
- Balances are scoped by company, store, product, source and location. A physical
  lot can have several receipt cost layers; identical price or expiry does not
  merge layers. `source_id=False` is reserved for the shortage balance.
- Each saved movement has a store posting sequence and immutable `ending_balance`.
  `closing_balance` remains a compatibility alias for that layer/location close.
- Current stock reads use `ab_inventory_balance`. Historical reports aggregate
  saved movements by their UTC posting timestamp, with user-local date boundaries.
- Cost uses the frozen purchase calculation, including configured capitalized
  taxes, bonus allocation and allocated invoice discount. It is converted to
  the smallest unit and retained on each movement.

## Operations

Inventory users can read their assigned stores. Operators can reserve/release
stock. Managers can post manual adjustments, transfer locations and rebuild a
corrupted current-balance projection. Administrators assign stores; manager
access remains restricted to allowed companies. Raw balance, reservation and
audit writes are forbidden through public ORM/RPC methods.

Locations are saleable, quarantine, damaged and transit. Allocation excludes
expired stock and locations other than saleable. Preferred-price layers are
selected first, then ascending price and expiry. Reservations retain the exact
source allocations and are owned by their creator. Repeating a key requires
identical inputs. A released key cannot be reused.

Shortage sales require explicit authorization and a reason. The deficit is
separate from physical lots, with provisional cost at 85% of the requested
selling price. Later receipts reconcile oldest shortages, recording the actual
cost adjustment and paired movements without increasing total stock twice.
Returns restore the original physical allocation, reverse an unresolved deficit,
or restore the receipt layer that settled that deficit.

The native sales adapter reserves and posts in one transaction. Public reservation
clients must release abandoned holds explicitly; there is no expiry cron.
Branch and economic-input locks also touch their ORM metadata so an older repeatable-read snapshot cannot miss a committed posting. Concurrent requests may receive Odoo's lock/serialization retry error. Retrying a completed
operation with the same key cannot duplicate its stock effect.

## Screens and reconciliation

Inventory includes movement history, stock layers, reservations, shortages,
cost corrections, repair audits, current stock and period reports. Reports
include deficit rows so shortages are not hidden from totals.

Inventory Integrity Review compares movement running balances and sequences,
current quantities/revisions and held reservations. Rebuild Projection requires
a reason and records before/after values. It never edits movement history and
refuses an inconsistent ledger or sequence counter. Correct business errors
through a return, adjustment or location transfer with a new operation identity.

See `INTEGRATION.md` for the server-side API contract.
