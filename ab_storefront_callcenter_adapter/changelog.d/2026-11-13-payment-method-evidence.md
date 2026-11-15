# Payment method evidence

Current changes before commit:

- Include the actual payment method or native custom payment mode in new immutable order snapshots.
- Allow callcenter invoice cards to distinguish cash on delivery from bank transfer without guessing from payment status.

Files changed:

- `models/adapter.py`
- `tests/test_adapter.py`
- `changelog.d/2026-11-13-payment-method-evidence.md`
