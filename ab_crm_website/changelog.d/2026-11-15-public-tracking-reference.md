# Public tracking reference in invoice cards

Current changes before commit:

- Show the storefront public tracking reference in Order Reference instead of the internal number.
- Retain optional public reference metadata for older invoice cards without rewriting snapshots.
- Preserve invoice headings, scoped access, immutable evidence and duplicate handling.

Files changed:

- `models/adapter.py`
- `protocol.py`
- `static/src/order.xml`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `tests/test_adapter.py`
- `tests/test_ui.py`
- `README.md`
- `changelog.d/2026-11-15-public-tracking-reference.md`
