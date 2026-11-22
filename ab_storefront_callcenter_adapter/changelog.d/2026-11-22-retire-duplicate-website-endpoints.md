# Retire duplicate website endpoints

Reference commit: `b0095b6521105f026f3de12e4283d402255f28c3`
Author: Alhassan Hossny
Date: 2026-11-17
Original subject: ab_storefront_callcenter_adapter/fix: allow website selection on new endpoints

- Allow administrators to select an existing company website when creating a call center endpoint.
- Keep the endpoint website fixed after creation and prevent creating websites from its selector.

Files changed:

- `__manifest__.py`
- `views/views.xml`
- `tests/test_adapter.py`
- `README.md`
- `changelog.d/2026-11-17-endpoint-website-selector.md`

Current changes before commit:

- Let administrators detach a disabled endpoint from a retired duplicate website while preserving its company, source, orders, and outgoing events.
- Require a website when creating or enabling an endpoint, and keep source and company changes blocked.
- Translate the new validation messages in both Arabic catalogs.
- Cover endpoint detachment, denied access, website removal, and an existing endpoint in the test database.
- Release version `19.0.1.0.2` for the targeted module upgrade.

Files changed:

- `__manifest__.py`
- `models/adapter.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `tests/test_adapter.py`
- `changelog.d/2026-11-22-retire-duplicate-website-endpoints.md`
