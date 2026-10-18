# Using `ab_inventory` from another module

`ab_inventory` is the stock movement ledger. It depends only on `base`,
`ab_product`, `ab_product_source`, and `ab_store`. Other modules should depend
on `ab_inventory` in their manifest and use the methods below; they should not
write stock quantities or saved movement fields directly.

The ledger fields and guarded create/write/delete methods live in
`models/ab_inventory.py`. The `ab_inventory_process` abstract service in
`models/ab_inventory_process.py` owns stock posting, unit conversion, store
checks, and balance reads. Integrating modules call that service directly;
they do not inherit it.

## What a movement means

Each `ab_inventory` record belongs to one store and one product source (batch).
The stored `qty` is a **non-zero signed integer in the product's
smallest unit**. Positive means incoming stock; negative means outgoing stock.
`incoming_qty` and `outgoing_qty` are read-only display values:

| Movement | `model_ref` example | `qty` |
| --- | --- | ---: |
| Initial stock | `opening` | Positive |
| Receipt or return | Extended by its module | Positive |
| Sale or issue | Extended by its module | Negative |

Only records with `status='saved'` affect physical stock. Pending outgoing
movements reduce availability, while pending incoming movements are excluded.
Saving checks physical stock and remaining pending holds under a store lock.
`closing_balance` is a read-only computed historical sum through that saved
movement. The period report uses `closing = opening + incoming - outgoing`.
Saved movements are immutable.
There is no manually entered `name` or reference column: the movement ID,
store, product, and linked `model_ref`/`res_id` identify the entry. Manual
movements have no external `res_id`.

## Prepare an integrating module

Add `ab_inventory` to the integrating module's `depends`. Add a source type by
extending `model_ref`; do not change the base module's selection for every new
integration:

```python
from odoo import fields, models


class InventoryMovement(models.Model):
    _inherit = 'ab_inventory'

    model_ref = fields.Selection(
        selection_add=[('my_sale_line', 'Sale Line')],
        ondelete={'my_sale_line': 'set default'},
    )
```

The source model name above is an example. Use a stable value specific to your
module. There is no separate movement-direction selection: the sign of
`qty` determines direction, while `model_ref` identifies the business
source. The base selection provides `manual` and `opening`; other modules add
their own source values.

An administrator assigns users to their allowed stores through **Inventory
Stores** on the user form. Inventory managers and Settings administrators can
access all stores. For balance reads, give the integrating users the Inventory
User group through the integrating module's security XML; do not create or
modify group membership in Python.

## Write a business-line movement

Use `inventory_write()` on `ab_inventory_process` from trusted addon Python
code. The business line must be saved and have `source_id` (linked to a
product) and `uom_id`. The caller supplies its workflow's stock quantity;
the inventory service does not read or require a `bonus` field. Inventory
converts the positive input quantity to the item's smallest unit **exactly**;
it rejects a fractional smallest-unit result instead of rounding it.
`sign=1` is incoming
and `sign=-1` is outgoing. The default status is `saved`; pass
`status='pending'` explicitly for observed inbound stock:

```python
movement = self.env['ab_inventory_process'].inventory_write(
    line, line.qty, document.store_id.id,
    status='pending', sign=1,
)
# After receipt approval, with the same line and quantity:
movement = self.env['ab_inventory_process'].inventory_write(
    line, line.qty, document.store_id.id,
    status='saved', sign=1,
)
```

The pair (`model_ref`, `res_id`) is derived from the business line model and
ID. One line has at most one movement in each store. Calling again for the
same store while pending updates that
pending movement; calling again after saving with identical values returns the
same movement without a second stock effect. Saved values cannot be changed.
The database unique index enforces `(store_id, model_ref, res_id)` for positive
`res_id` values. The same linked ID may be used in another store; manual
movements without a linked record may coexist.
If a sale needs two batches, use two distinct business lines.

The API checks the calling user's store access and serializes retries for the
same business line. Saving locks the store, sums saved movement quantities,
and rejects negative batch stock. It uses elevated ORM access internally only
after store checks. Do not wrap the call in `sudo()` or bypass it with direct
SQL. For multi-line documents, call it inside one business transaction and
let any failure roll back the entire document; do not commit partial results.
Inventory locks the source, product, and referenced units before converting a
line quantity. Their item and unit definitions cannot change while pending or
saved movements reference them.
Purchase and opening-balance models call the same service directly. It is a
trusted server-side method, not a general end-user RPC endpoint.

## Check a proposed operation

`check_operation()` lets a business module check a proposed stock effect from
its `create()`, `write()`, or `unlink()` override. Each module must call it
explicitly; it does not intercept unrelated Odoo models. Pass `old` only for
an inventory movement that already exists. Pass `new` for the proposed effect:

```python
effect = {
    'store_id': store.id,
    'source_id': source.id,
    'qty': -3,              # signed quantity in the smallest unit
    'status': 'pending',    # or 'saved'
}
process = self.env['ab_inventory_process']
process.check_operation('create', new=effect)
```

For `write`, pass the existing movement's store, source, quantity, and status
as `old`, and the complete proposed effect as `new`. When changing a pending
outgoing quantity, the check releases that movement's old hold in its
calculation before applying the new quantity. A saved effect cannot be edited:

```python
old = {
    'store_id': movement.store_id.id,
    'source_id': movement.source_id.id,
    'qty': movement.qty,
    'status': movement.status,
}
new = {**old, 'qty': -5}
process.check_operation('write', old=old, new=new)
```

For `unlink`, pass the existing effect as `old`; the check rejects physical
deletion of a pending or saved inventory effect. Passing `old=None` permits
deleting a draft business line with no movement. Pending document cancellation
needs a separate workflow that retains its inventory history; a saved effect
requires a new return or correction operation.

The check validates store access and locks all affected stores. Call it and
perform the business write in the **same database transaction**, without an
intermediate commit. It does not create, update, or delete a movement;
`inventory_write()` still applies the stock effect and runs the ledger's final
checks. `inventory_write()` itself calls `check_operation()` before creating
or changing a movement. Integrating modules must supply truthful `old` and
`new` values from their trusted server-side code; do not expose arbitrary
effect dictionaries as an end-user RPC API.

## Read a balance

```python
process = self.env['ab_inventory_process']
product_qty = process.get_balance(store.id, product_id=product.id)
batch_quantities = process.get_source_balances(store.id, product_id=product.id)
```

These are the two read methods, not four separate APIs. `get_balance()`
returns one integer in the smallest unit; pass `source_id=source.id` instead
of `product_id` when only one batch's balance is needed. It returns `0` for
a depleted or absent source. `get_source_balances()` returns
`{source_id: quantity}` and omits zero-balance sources by default. For an audit
that needs used-up batches, pass `include_zero=True`; sources without a saved
or pending outgoing movement are still omitted. Current reads sum saved `qty`
and pending negative `qty`, excluding pending positive `qty`. Saved `+10`,
pending `+2`, and pending `-3` therefore return `7`.
Unexpected negative closes remain visible for investigation; a
saleable-batch picker must require a quantity greater than zero. Product and
whole-store queries aggregate the same quantities across matching sources.
Partial covering indexes on store/source, store/product, and store/date include
aggregate inputs to support these sums. Query cost still grows with movement
history;
benchmark large ledgers before relying on current-stock reads at POS scale.
`before=<UTC datetime>` uses only saved movements whose `saved_at` is strictly
before that time. Computed `closing_balance` uses posting time and movement ID
to order movements with the same timestamp.
The method enforces store access and aggregates all movements in that store,
including other users' pending outgoing movements. A balance read is a
snapshot. Creating or changing a pending outgoing movement reserves its
quantity under the store lock; posting also checks under that lock.

For a step-by-step explanation and an example with a zero-balance batch, see
[README.md](README.md#read-current-availability-and-historical-stock). A
separate addon can add expiring holds for screens that have no saved business
line yet; see the [proposed workflow](README.md#recommended-future-module-expiring-screen-holds).

## Corrections, returns, and transfers

- Never edit or delete a saved movement. This base module has no automatic
  reversal action. An authorized correction is a new movement created by an
  approved business workflow; do not silently alter the original movement.
- An automated return or cancellation should post a new compensating business
  event using a new source-effect record ID. Do not reuse the original
  (`model_ref`, `res_id`) pair.
- For a store-to-store transfer, use one source-store business line with
  `sign=-1` and one destination-store line with `sign=1`, each with its own
  ID. Call both inside one business transaction; the user must be authorized
  for both stores, and a failure must roll back both effects.
- For a batch change inside one store, likewise submit a negative and a
  positive line together, with separate source-record IDs. Both quantities
  must use the smallest unit.

## Reports and UI

- **Inventory / Movement Schedule:** saved/pending movement list with date,
  store, item, batch, type, incoming, and outgoing filters/columns.
- **Inventory / Reports / Current Stock Balance:** current available quantity by source
  and store; optionally include
  zero-balance sources that have movements.
- **Inventory / Reports / Period Report:** opening, incoming, outgoing, and
  closing quantities for the selected dates. Selecting an item adds a running
  movement detail. Date boundaries follow the report user's timezone.

## Purchase behavior

`ab_purchase` submits invoice lines as `pending` observed inbound. The
manager-only **Save & Receive** action saves those same lines into on-hand
stock. Purchase lines specifically post `line.qty + line.bonus` because their
business model has a bonus field; other modules pass their own explicit
stock quantity, commonly `line.qty`. A notice requires a saved purchase
receipt first: a credit notice
saves a negative movement, while a debit notice saves a positive movement.
`ab_purchase_ob` calls the default saved path for opening
balances. None of these flows has been validated in a running Odoo 19 database
in this workspace; use a test database before deployment.

## Verification before production use

Install or upgrade the targeted `ab_inventory` and consuming purchase modules
in Odoo 19, then verify: branch
isolation, user versus manager permissions, duplicate-source rejection,
concurrent posting, negative-stock rejection, correction behavior, a two-store
transfer, current balances, and period boundaries. The current development
environment has not run an Odoo install/upgrade or runtime test, so these
checks are required before deployment.
