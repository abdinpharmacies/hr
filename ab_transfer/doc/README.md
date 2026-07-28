# ab_transfer

`ab_transfer` handles internal stock transfer records in Odoo and pushes the transfer into the ePlus SQL Server database.

## What the module does

- `ab_transfer_header` stores the transfer header, source store, destination store, user, notes, and transfer status.
- `ab_transfer_line` stores the per-item transfer lines, quantities, expiry dates, and pricing fields used during posting.
- `ab_transfer_pos_api` powers the POS-style transfer screen under `ab_transfer/static/src/pos`.
- The send action validates the Odoo data first, then validates the SQL-side prerequisites, then writes the transfer header, lines, stock deductions, replication rows, and optional accounting documents in one transaction.

## JSON inventory flow

- Each transfer line now follows the `ab_sales` pattern with a stored `inventory_json` field.
- `_recompute_inventory_json` reads all available source batches for the selected product from `Item_Class_Store` using the header source store.
- The selected batch drives `class_id`, `expiry_date`, `sell_price`, `cost`, `tax_value`, and `purchase_price`.
- `from_store_id`, `to_store_id`, and `user_id` are header-level values and are no longer forced on each line.

## POS interface

- The module now exposes a client action `ab_transfer.pos`.
- The POS screen keeps local transfer drafts, defaults the source store from `ab_replica_db.default_sales_store_id`, and defaults the user from the current employee cost center when available.
- Product search is source-store aware, and line batch selection is driven by the `inventory_json` rows instead of manual per-line store entry.

## Connector change

- The module uses the shared `ab_eplus_connect` connector instead of opening direct `pyodbc` connections.
- The transfer action connects with `connect_eplus(..., param_str="?")`, which means the ODBC path is handled by the shared connector.
- The source SQL server is resolved from the header source store (`ip1`, fallback `ip2`) instead of a hardcoded address.

## Notes

- The transfer code keeps the existing business rules and SQL payloads unchanged.
- The shared connector adds pooled connections, reconnect handling, and server validation.
