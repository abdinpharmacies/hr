# Delivery lines in website handoffs

Current changes before commit:

- Preserve native delivery-line evidence in website quotations.
- Skip zero-value delivery lines when preparing POS product lines; require explicit review for charged delivery.
- Validate delivery flags and cover native COD capture and mixed product/delivery handoffs.

Files changed:

- `models/adapter.py`
- `protocol.py`
- `tests/test_adapter.py`
- `tests/test_pos.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `changelog.d/2026-11-12-delivery-line-handoff.md`
