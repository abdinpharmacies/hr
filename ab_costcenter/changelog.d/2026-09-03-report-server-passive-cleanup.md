Recent relevant commit:

- Commit: `293b3f87af9d08fe7566a4c0260a56166fc45929`
- Author: Alhassan Hossny
- Date: 2026-08-25
- Original subject: ab_costcenter: relax master fields for report sync
- User-facing changes:
  - Established the previous baseline for this module before the report-server passive cleanup.
- Files changed:
  - ab_costcenter/changelog.d/2026-08-25-report-server-master-placeholders.md
  - ab_costcenter/models/costcenter.py

Current changes before commit:

- User-facing changes:
  - Replaced explicit report-side user relations with `ab_users` placeholders where this module declares user fields.
  - Removed `required=True` from model field declarations so report sync loads can accept incomplete branch payloads.
  - Declared new module dependencies required by the cleaned report-server model schema.
- Files changed:
  - ab_costcenter/changelog.d/2026-09-03-report-server-passive-cleanup.md
  - ab_costcenter/__manifest__.py
  - ab_costcenter/models/costcenter.py
