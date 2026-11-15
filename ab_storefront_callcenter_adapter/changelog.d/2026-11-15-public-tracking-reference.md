# Public tracking reference in invoice cards

Current changes before commit:

- Capture native sale.order.ab_public_reference as optional public_reference separately from the internal reference.
- Keep native checkout, payment, delivery, reservation and exchange behavior unchanged.

Files changed:

- `models/adapter.py`
- `protocol.py`
- `tests/test_adapter.py`
- `README.md`
- `changelog.d/2026-11-15-public-tracking-reference.md`
