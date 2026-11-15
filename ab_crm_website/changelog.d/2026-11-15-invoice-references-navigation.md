# Invoice references and CRM / OMS navigation

Current changes before commit:

- Receive optional readable unit names without mapping or product lookups; preserve them in snapshots while showing only Product, Quantity, Price, Discount and Total on Sales Chatter invoice cards.
- Keep older snapshots unchanged and retain the invoice toggle and general manual POS workflow.
- Move read-only Website Orders under CRM / OMS and deactivate mapping navigation without deleting records.

Files changed:

- `models/adapter.py`
- `protocol.py`
- `views/views.xml`
- `static/src/order.xml`
- `tests/test_adapter.py`
- `tests/test_ui.py`
- `README.md`
- `changelog.d/2026-11-15-invoice-references-navigation.md`
