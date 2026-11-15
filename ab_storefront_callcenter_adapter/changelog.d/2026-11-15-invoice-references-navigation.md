# Invoice references and CRM / OMS navigation

Current changes before commit:

- Capture the readable source unit name as optional unit_name alongside the original unit code.
- Validate optional unit names without changing checkout, payments, reservations, delivery, acknowledgements or deduplication.

Files changed:

- `models/adapter.py`
- `protocol.py`
- `tests/test_adapter.py`
- `README.md`
- `changelog.d/2026-11-15-invoice-references-navigation.md`
