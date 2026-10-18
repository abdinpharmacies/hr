# Inventory integration

Declare `ab_inventory` as a manifest dependency. Business methods must validate
the actor and document before invoking stock posting; do not expose a public
method that accepts arbitrary elevated records or posting fields.

| Service | Contract |
|---|---|
| `inventory_write(line, qty, store_id, status, sign)` | Private purchase, purchase-notice and opening-line adapter. Positive document-unit quantity, sign ±1; converts with frozen source factors. One stable key per business line. |
| `get_balance(store_id, product_id=None, source_id=None, before=None)` | Total on-hand quantity across locations, including deficits. Optional exclusive historical UTC cutoff. |
| `get_source_balances(store_id, product_id=None, before=None, include_zero=False)` | Physical-source quantities across locations. Deficits have no physical source; use total balance or stock-layer reports for the net position. |
| `source_stock(store_id, product_ids)` | Saleable, unexpired available layers with identity, quantity, cost, price and expiry. Amounts and quantities are per smallest stock unit. |
| `available_stock(store_id, product_ids)` | Product-level saleable availability, including the shortage balance once. |
| `reserve_stock(store_id, product_id, qty, operation_key, preferred_price=None, allow_shortage=False, reason=None)` | Positive smallest-unit quantity; returns a caller-scoped reservation with frozen allocation rows. |
| `release_reservation(operation_key, store_id)` | Idempotent release by owner or manager; posted reservations cannot be released. |
| `post_reserved(operation_key, store_id, document_model, document_id)` | Private native sale posting. Requires a matching accessible sale document. Repeating the same posting is idempotent. |
| `return_allocations(store_id, operation_key, original_key, qty, document_model, document_id)` | Private native return posting. Restores original allocations and prevents over-returns. |
| `transfer_location(store_id, source_id, qty, from_location, to_location, operation_key, reason)` | Manager-only paired movement within one store. Stock released to saleable can settle shortages. |
| `check_integrity(store_id)` | Independent comparison of ledger, current balances, sequences and reservations. |
| `rebuild_projection(store_id, reason)` | Manager-only audited repair from valid history. Never rewrites the ledger. |

All stock-changing calls belong to the surrounding Odoo transaction. Do not
commit between invoice lines. A failed line must roll back the complete business
operation. Callers should retry lock/serialization conflicts in a fresh
transaction with the same operation identity.

Manual movements require a real source. New source origins bind to the created
movement; existing bound sources retain their original provenance. Posted source
commercial inputs, unit definitions, expiry and raw audit snapshots are immutable.

Validation scripts live under the repository `scripts/` directory rather than
inside runtime addon packages. Phases 7–8 will integrate journal posting against
these frozen quantities, values, operation identities and correction events.
