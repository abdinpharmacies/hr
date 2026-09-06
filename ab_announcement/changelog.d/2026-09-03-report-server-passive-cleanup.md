Recent relevant commit:

- Commit: `3db5d596c9429ff082c3fe9b0466692b945f788f`
- Author: emadco88
- Date: 2026-07-28
- Original subject: INIT commit pos19
- User-facing changes:
  - Established the previous baseline for this module before the report-server passive cleanup.
- Files changed:
  - ab_announcement/__init__.py
  - ab_announcement/__manifest__.py
  - ab_announcement/i18n/ar_001.po
  - ab_announcement/models/__init__.py
  - ab_announcement/models/ab_announcement.py
  - ab_announcement/security/ir.model.access.csv
  - ab_announcement/security/record_rules.xml
  - ab_announcement/security/security_groups.xml
  - ab_announcement/static/description/icon.png
  - ab_announcement/static/src/img/announcement_bg.png
  - ab_announcement/static/src/scss/announcement.scss
  - ab_announcement/views/ab_announcement.xml
  - ab_announcement/views/menus.xml
  - ab_announcement/views/template_announcement.xml

Current changes before commit:

- User-facing changes:
  - Removed `required=True` from model field declarations so report sync loads can accept incomplete branch payloads.
- Files changed:
  - ab_announcement/changelog.d/2026-09-03-report-server-passive-cleanup.md
  - ab_announcement/models/ab_announcement.py
