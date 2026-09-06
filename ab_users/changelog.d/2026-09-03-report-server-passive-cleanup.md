Recent relevant commit:

- Commit: `e35c5b6138f80320171caabba8fc44626130e0e2`
- Author: Hossam Elsheikh
- Date: 2026-08-23
- Original subject: ab_users/removed the default placeholder name from ab_users, so force-ID   creation reserves only the ID plus normal Odoo technical defaults. It will not   copy name, login, email, groups, partner, or any real res.users data.
- User-facing changes:
  - Established the previous baseline for this module before the report-server passive cleanup.
- Files changed:
  - ab_users/changelog.d/2026-08-23-initial-user-sync-placeholders.md
  - ab_users/i18n/ar.po
  - ab_users/i18n/ar_001.po
  - ab_users/models/ab_users.py

Current changes before commit:

- User-facing changes:
  - Replaced explicit report-side user relations with `ab_users` placeholders where this module declares user fields.
  - Removed `required=True` from model field declarations so report sync loads can accept incomplete branch payloads.
- Files changed:
  - ab_users/changelog.d/2026-09-03-report-server-passive-cleanup.md
  - ab_users/models/ab_users.py
