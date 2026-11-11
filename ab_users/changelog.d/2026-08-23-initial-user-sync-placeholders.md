# User Sync Placeholders

## Current changes before commit:

- Restored the existing report-branch module to satisfy the `ab_odoo_sync`
  dependency that prevented branch upload upgrades on `pos19`.
- Retained blank identity placeholders, deletion protection, administrator-only
  access, existing translations, and company/developer ownership.
- Passed isolated clean install and targeted `ab_odoo_sync_upload` upgrade.
- Passed runtime blank-default, deletion-protection, administrator/public access,
  and upload registry checks; test records were rolled back.
- Installed the dependency and completed the targeted sync upgrade on
  `abdin_pos`. Logs: `/tmp/codex_sync_upgrade_install.log`,
  `/tmp/codex_sync_upgrade_check.log`, `/tmp/codex_sync_pos_upgrade.log`.
- Both restored Arabic catalogs passed `msgfmt --check-format`.

Files changed:

- `ab_users/__init__.py`
- `ab_users/__manifest__.py`
- `ab_users/models/__init__.py`
- `ab_users/models/ab_users.py`
- `ab_users/security/ir.model.access.csv`
- `ab_users/i18n/ar.po`
- `ab_users/i18n/ar_001.po`
- `ab_users/changelog.d/2026-08-23-initial-user-sync-placeholders.md`

## e35c5b6138f80320171caabba8fc44626130e0e2

Author: Hossam Elsheikh
Date: 2026-08-23 13:53:22 +0300
Original commit subject:

    ab_users/removed the default placeholder name from ab_users, so force-ID
      creation reserves only the ID plus normal Odoo technical defaults. It will not
      copy name, login, email, groups, partner, or any real res.users data.

- Left placeholder name/login empty until authoritative user data is supplied.

Files changed:

- `ab_users/models/ab_users.py`
- `ab_users/i18n/ar.po`
- `ab_users/i18n/ar_001.po`
- `ab_users/changelog.d/2026-08-23-initial-user-sync-placeholders.md`
