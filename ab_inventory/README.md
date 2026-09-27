# Abdin Inventory (`ab_inventory`)

`ab_inventory` is the stock ledger and operations service for Abdin's Odoo 19
addons. It records signed movements by store and product source (batch),
answers on-hand balance queries, and provides movement and stock reports. It
depends only on `base`, `ab_product`, `ab_product_source`, and `ab_store`; it
does not read E-Plus or perform accounting entries.

> Status: This is the current implementation, not the full future stock plan.
> It has not been installed or business-tested in an Odoo 19 database from this
> workspace. Do not deploy it without the verification checklist below.

## Architecture

| Component | Responsibility |
| --- | --- |
| `models/ab_inventory.py` | Movement fields, source identity, immutable saved records, and guarded create/write/delete. |
| `models/ab_inventory_process.py` | The `ab_inventory_process` service: convert quantity, create/update a movement, save it under a store lock, and read balances. |
| `models/ab_product.py`, `models/ab_product_source.py` | Prevent changes to product unit definitions or a source's item/unit after saved stock exists. |
| `models/res_users.py` | Current administrator-managed store assignments (`inventory_store_ids`). |
| `report/` | Current stock balance and dated period reports. |
| `security/` | Inventory roles, ACLs, and store-scoped record rules. |
| `views/` | Movement schedule, menus, and the current user-store assignment form. |

The movement is the audit record. Other addons call the process service; they
must not set a product's computed stock fields or write a saved movement's
quantity or `closing_balance` directly.

## Stock rules

| Field or concept | Meaning |
| --- | --- |
| `store_id` | Physical store whose stock changes. Every write and balance read requires a valid store. |
| `source_id` | Product source/batch. `product_id` is derived from this source. |
| `qty` | Non-zero signed integer in the product's smallest unit: positive is incoming, negative is outgoing. |
| `incoming_qty`, `outgoing_qty` | Read-only positive display amounts derived from `qty`; they are not separate stock inputs. |
| `status='pending'` | Observed movement only; it does not affect on-hand stock. |
| `status='saved'` | Final stock effect. The movement and its closing balance cannot be edited or deleted. |
| `closing_balance` | Saved balance for the same **store and source** immediately after this movement. It is not the product total across batches. |
| `model_ref`, `res_id` | Type and ID of the originating business line. One business line has at most one movement. |
| `saved_at` | UTC posting timestamp used by historical balance queries and period reports. |

For a saved movement, `closing_balance = previous saved close + qty`. Saving
rejects a negative batch balance. The process serializes retries for the same
business line and locks the store during posting, including a first receipt.
Calling `inventory_write()` again with the same saved effect returns that
movement without posting it twice; changing a saved effect is rejected.

## Use from another addon

1. Put `ab_inventory` in the addon's manifest `depends`.
2. Extend `ab_inventory.model_ref` with the business-line model name.
3. Call `self.env['ab_inventory_process']` from trusted server-side business
   methods. Do not inherit `ab_inventory_process` into the business model.
4. Give relevant users the Inventory User or Inventory Manager role through
   security XML. Ensure the store authorization is correct before posting.

```python
from odoo import fields, models


class InventoryMovement(models.Model):
    _inherit = 'ab_inventory'

    model_ref = fields.Selection(
        selection_add=[('my_sale_line', 'Sale Line')],
        ondelete={'my_sale_line': 'set default'},
    )
```

The business line must already exist and have a `source_id` and `uom_id`.
Pass a **positive** quantity in the line's unit; use `sign=1` for a receipt
or `sign=-1` for an issue. The service converts exactly to the smallest unit
and rejects an invalid factor or fractional smallest-unit result. It does
not round stock quantities. It never reads a `bonus` field: each business
module decides the quantity to post. For example, a normal line may pass
`line.qty`, while `ab_purchase` intentionally passes
`purchase_line.qty + purchase_line.bonus`.

```python
process = self.env['ab_inventory_process']

# Observe an expected receipt without increasing on-hand stock.
process.inventory_write(line, line.qty, header.store_id.id, status='pending')

# Save the same line when the receipt is approved.
process.inventory_write(line, line.qty, header.store_id.id, status='saved')

# Issue stock from a sale line. The batch cannot go below zero.
process.inventory_write(sale_line, sale_line.qty, sale.store_id.id,
                        status='saved', sign=-1)
```

The line's model name and database ID become `(model_ref, res_id)`. Reusing one
line for two sources is not supported: create two business lines if a sale or
transfer must be split across batches. For a multi-line document, run every
call in the same Odoo transaction and let an error roll back the whole
document. Do not commit between lines or call the process through `sudo()`.

## Read on-hand stock

```python
process = self.env['ab_inventory_process']
product_qty = process.get_balance(store.id, product_id=product.id)
batch_quantities = process.get_source_balances(store.id, product_id=product.id)
```

These are two methods. `get_balance()` returns one smallest-unit integer;
pass `source_id=source.id` instead of `product_id` to read one batch. A
depleted or absent source returns `0`. `get_source_balances()` returns
`{source_id: qty_small}` and hides zero-balance sources by default. Pass
`include_zero=True` for a report or audit that needs used-up batches. A
source with no saved movement is never listed.
An unexpected negative close remains visible for investigation; a sales
screen must select only entries with quantity greater than zero.
Both APIs exclude pending movements.
A batch lookup returns its latest saved `closing_balance`, **including zero**.
A product lookup adds one latest saved close for each matching source in that
store; it does not sum the entire transaction history. The optional
`before=<UTC datetime>` cutoff is exclusive and returns an as-of balance.

The current lookup works as follows:

1. Validate that the store exists and the caller may access it.
2. For a `source_id`, search only saved movements in that store/source,
   ordered by `saved_at DESC, id DESC`. Return the first row's
   `closing_balance`, or zero if there is no saved row. Do **not** filter for
   positive balances: the latest row may correctly be zero.
3. For a `product_id`, find that product's accessible sources, read only the
   latest saved movement for each source in the store, and add their closing
   balances. With neither product nor source, do the same for all accessible
   sources in the store. The lookup uses a partial composite index; it does
   not sum every historical movement. `get_source_balances()` uses those same
   latest rows but omits zero-close sources unless `include_zero=True`.
4. If `before` is supplied, ignore movements saved at or after that UTC
   timestamp. Odoo read rules are checked before returning the result.

For example, if a store has two sources for an item, with latest closes of
`4` and `0`, its item balance is `4` smallest units. The zero source must not
fall back to an earlier positive closing balance.

`get_balance()` is an informational read, not a reservation. Two users can
both see the last unit; the final negative-stock check occurs when posting
under the store lock. This release does not provide reserved or available
quantities.

## Recommended future module: screen availability

Create a separate addon, provisionally `ab_inventory_reservation`, for sales,
transfer, and similar screens. It should depend on `ab_inventory` rather than
adding screen-specific state to the movement ledger. This is a **design
recommendation, not an API or table implemented by this module**.

When a user adds or changes a product line, the screen should show:

| Quantity | Meaning |
| --- | --- |
| On hand | Saved stock from `get_balance()` for the selected store and source, or all sources for the item. |
| Reserved | Active holds belonging to draft lines, including other users' screens. |
| Available | `max(on hand - reserved, 0)` for ordinary sales or transfer selection. |

An observation-only first version can call `get_balance()` and refresh the
display when the source, unit, or quantity changes. It must label the number
as a snapshot: **observing does not claim stock**. Posting must still perform
the authoritative negative-stock check. Do not include pending inbound in
on-hand or available stock.

To prevent two devices from taking the last unit, add a separate reservation
table and service. A reservation should identify its store, product, selected
source, owner draft line or client token, quantity in the smallest unit,
expiry, and state. A single atomic operation must lock the relevant stock
key, expire stale holds, check `on hand - other active holds`, and create or
resize the caller's hold. Repeating the same draft-line request must update
one hold, not create another. Editing or removing a line releases or changes
its hold; when resizing, exclude that line's own hold from the competing
reserved quantity. Checkout consumes the hold and posts the movement in one
transaction. A failed checkout must roll back both actions.

For a selected batch, try that `source_id` first. If it cannot cover the
quantity, an alternative may be suggested only when the item and selling
price match the screen's line. Do not silently mix two sources in one
business line; prompt the user to add a second line for a split. A different
price or insufficient available stock must produce a clear message.

The reservation service must enforce branch access and be tested with two
devices competing for the final unit, abandoned screens, expiry, retries,
and checkout failures. Its detailed schema and integration contract should
be agreed with the planned `ab_inventory_balance` projection and upstream
quantity/source contracts before implementation.

## Existing integrations and screens

- `ab_purchase` submits invoice lines as pending observed inbound and uses a
  manager-only **Save & Receive** action to save them into on-hand stock.
- A purchase credit notice posts a negative effect; a debit notice posts a
  positive effect. The linked purchase receipt must already be saved.
- `ab_purchase_ob` posts opening-balance lines through the same service.
- **Inventory / Movement Schedule** shows pending and saved movements, with
  separate incoming, outgoing, and closing columns.
- **Inventory / Reports / Current Stock Balance** shows the latest close by
  source in a selected store, optionally including zero-balance sources.
- **Inventory / Reports / Period Report** shows opening, incoming, outgoing,
  and closing quantities over a selected date range. Date boundaries use the
  report user's timezone; item filtering adds movement detail.

## Security and corrections

Inventory users currently see only stores in `inventory_store_ids`; Inventory
Managers and Settings administrators can access all stores. Only managers
can use the manual movement Post action. Purchase integration methods apply
their own workflow authorization before calling the stock service. These
rules are defined in `security/`, not in Python group-creation code.

Never edit or delete a saved movement. An authorized return, correction, or
transfer must create new business-line effects with new `(model_ref, res_id)`
identities. A transfer needs a negative source-store line and a positive
destination-store line in one transaction. Both stores must be authorized.

## Scope and performance

Current balance reads and posting use the latest saved close per source with
a partial composite index on `(store_id, source_id, saved_at, id)`. They do not
aggregate a batch's full movement history. Product/store reads still scale
with the number of product sources, and period reports total movements inside
the chosen period. Benchmark these paths with realistic data volumes.

This module does **not yet** include a current-balance projection table,
reservations, automatic batch allocation, shortage authorization, location
types, valuation, or reversal workflow. Those are separate design and release
decisions; do not assume the current API provides them.

## Verification before production

- Install or upgrade only the targeted modules on a test database; do not
  run a broad `-u base` upgrade for this change.
- Test branch isolation, role permissions, pending versus saved stock,
  duplicate retries, invalid unit factors, exact conversion, and zero balance.
- Test simultaneous first receipts and competing last-unit issues; confirm
  that one failure rolls back an entire multi-line document.
- Compare current and historical balances with an independent ledger
  calculation, and test current-stock and period-report date boundaries.
- Benchmark the latest-row index and period report on a realistic database.
  Index creation on a populated million-row table needs a planned upgrade
  window.
- Verify both Arabic catalogs and an `ar_001` runtime view after the target
  module upgrade.

For API edge cases and integration examples, see [INTEGRATION.md](INTEGRATION.md).
