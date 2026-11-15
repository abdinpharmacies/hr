# Invoice delivery address and reference

Current changes before commit:

- Show the governorate before the detailed delivery address on one line in incoming Sales Chatter invoice cards.
- Resolve recognized Egyptian snapshot address codes without changing stored evidence; retain unknown formats as received text on one line.
- Add the order reference directly below Delivery Address, translated in both Arabic catalogs.
- Verify backend formatting, immutable snapshots and English/Arabic browser layouts.

Files changed:

- `models/adapter.py`
- `static/src/order.xml`
- `static/src/order.scss`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `tests/test_adapter.py`
- `tests/test_ui.py`
- `README.md`
- `changelog.d/2026-11-15-invoice-delivery-address.md`
