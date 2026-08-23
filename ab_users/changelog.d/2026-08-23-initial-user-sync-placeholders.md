## Current changes before commit:

User-facing changes:

- Add a standalone MAIN-owned `ab_users` module for branch user identity placeholders.
- Provide the `ab_users` model used by branch upload apply flows to resolve source `res.users` IDs without mirroring real Odoo users.
- Add manager/system ACL coverage and Arabic translations for the placeholder messages.

Files changed:

- `ab_users/__init__.py`
- `ab_users/__manifest__.py`
- `ab_users/changelog.d/2026-08-23-initial-user-sync-placeholders.md`
- `ab_users/i18n/ar.po`
- `ab_users/i18n/ar_001.po`
- `ab_users/models/__init__.py`
- `ab_users/models/ab_users.py`
- `ab_users/security/ir.model.access.csv`

