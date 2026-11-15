# Website adapter

Current changes before commit:

- Add scoped confirmed-order snapshots, durable exchange and text chat with manual POS integration.
- Preserve native checkout, payment, reservation and pricing behavior.
- Add focused access, retry and workflow tests and both Arabic catalogs.

Files changed:

- `README.md`
- `__init__.py`
- `__manifest__.py`
- `changelog.d/2026-11-11-website-adapter.md`
- `controllers/__init__.py`
- `controllers/adapter.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `models/__init__.py`
- `models/adapter.py`
- `protocol.py`
- `security/ir.model.access.csv`
- `security/security.xml`
- `static/src/order.xml`
- `static/src/pos.js`
- `tests/__init__.py`
- `tests/test_adapter.py`
- `tests/test_http.py`
- `tests/test_pos.py`
- `tests/test_ui.py`
- `views/views.xml`
