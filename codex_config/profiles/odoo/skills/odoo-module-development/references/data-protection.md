# Archival and Price History

The core instructions list protected pharmacy records and inventory quantities.
Implement supported archival or business-state transitions instead of physical
deletion. When the model supports normal Odoo archival, the source pattern is:

```python
active = fields.Boolean(default=True)
```

Do not blindly add an active flag to transactional models with their own state
workflows. Normal users must not edit product code, barcode or external reference
after creation; only Inventory Managers/System Administrators may do so.

Every price modification retains `old_price`, `new_price`, `changed_by` and
`change_date`. The source recommends a dedicated history model such as
`ab_product_price_history`; reuse existing ownership before creating another.

Never assign system-managed stock quantities (for example,
`product.qty_available = 100`). Use approved stock moves, inventory adjustments,
transfers, receipts, internal transfers or stock recycling business operations.
Preserve data and reject destructive changes when the safe operation is uncertain.

Before authorized mass price/product/barcode changes, adjustment imports,
stock recycling batches or supplier synchronization, follow
[backup requirements](../../odoo-testing-validation/references/backups.md).
