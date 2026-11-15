# XML developer mode view loading

Current changes before commit:

- Format view architecture fields with leading whitespace so Odoo 19 can read them from disk in XML developer mode.
- Preserve view IDs, fields and behavior.

Files changed:

- `views/views.xml`
- `tests/test_adapter.py`
- `changelog.d/2026-11-11-xml-developer-mode.md`
