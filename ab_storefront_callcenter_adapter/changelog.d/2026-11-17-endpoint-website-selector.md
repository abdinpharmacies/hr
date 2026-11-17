# Endpoint website selection

Reference commit: `6e253eacb61978ae42160d4c00716cf3131d212e`
Author: Alhassan Hossny
Date: 2026-11-15
Original subject: ab_storefront_callcenter_adapter/feat: add callcenter order snapshots and secure customer chat

Current changes before commit:

- Show websites from active companies when creating an endpoint, before its related company is populated.
- Disable website creation from the endpoint selector to prevent accidental duplicate websites.
- Preserve server-side company/service-user validation and immutable endpoint identities.
- Cover new endpoint form creation, allowed-company selection, rejected cross-company service assignment and saved identity protection.
- Release version `19.0.1.0.1` for a targeted module upgrade.
- No user-facing strings changed; both existing Arabic catalogs remain applicable.

Files changed:

- `__manifest__.py`
- `views/views.xml`
- `tests/test_adapter.py`
- `README.md`
- `changelog.d/2026-11-17-endpoint-website-selector.md`
