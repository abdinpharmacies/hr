Recent relevant commit:

- Commit: `6dd4b5a638c4b1d4d8b82fe3b4e09021dfda4639`
- Author: Alhassan Hossny
- Date: 2026-09-02
- Original subject: ab_project_sync: add passive sync metadata to project roles
- User-facing changes:
  - Established the previous baseline for this module before the report-server passive cleanup.
- Files changed:
  - ab_project_sync/__init__.py
  - ab_project_sync/__manifest__.py
  - ab_project_sync/changelog.d/2026-09-02-project-role-passive-sync.md
  - ab_project_sync/i18n/ar.po
  - ab_project_sync/i18n/ar_001.po
  - ab_project_sync/models/__init__.py
  - ab_project_sync/models/project_role.py

Current changes before commit:

- User-facing changes:
  - Added passive sync metadata inheritance for classified high-value report facts where applicable.
  - Declared the inherited project role model explicitly so registry verification is clean after adding passive sync inheritance.
  - Removed `required=True` from model field declarations so report sync loads can accept incomplete branch payloads.
  - Declared new module dependencies required by the cleaned report-server model schema.
- Files changed:
  - ab_project_sync/changelog.d/2026-09-03-report-server-passive-cleanup.md
  - ab_project_sync/__manifest__.py
  - ab_project_sync/models/project_role.py
