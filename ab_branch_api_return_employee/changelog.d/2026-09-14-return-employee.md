# Return employee validation — 2026-09-14

Commit: none (new module, not committed)
Author: hossam elsheikh
Date: 2026-09-14
Original commit subject: not applicable (new module)

Current changes before commit:

- Validate an explicit active employee and active cost center with a positive
  branch E-Plus serial before return reservation or external invoice processing.
- Preserve native authentication, business permissions, token ownership,
  successful-result replay and uncertain-operation reconciliation.
- Keep the provider and routing sources unchanged; no hooks, provisioning,
  permission assignments or automatic reservation recovery.
- Document the companion callcenter employee selector and deployment locations.
- Add both Arabic catalogs from the native Odoo POT export.
- Verify fresh installation and targeted upgrade on an isolated branch clone,
  mocked return posting, token isolation and Arabic runtime errors.

Files changed:
- `__init__.py`
- `__manifest__.py`
- `models/__init__.py`
- `models/branch_api.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `static/description/icon.png`
- `README.md`
- `changelog.d/2026-09-14-return-employee.md`
