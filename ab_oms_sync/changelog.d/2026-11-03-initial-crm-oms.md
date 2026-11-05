# ab_oms_sync

No prior commits exist for this new module.

Current changes before commit:

- Fix view loading with `--dev=xml` by retaining whitespace before architecture elements; preserve all view IDs, fields and UI strings.

- Add OMS Website Synchronization with module-owned access control and branch/company safeguards where applicable.
- Provide English UI and Arabic catalogs for ar and ar_001.
- Preserve existing addon files and business-operation ownership.

Author: Alhassan Hossny

Date: 2026-11-03

Files changed:

- `__init__.py`
- `__manifest__.py`
- `i18n/ar.po`
- `i18n/ar_001.po`
- `models/__init__.py`
- `models/sync.py`
- `security/ir.model.access.csv`
- `security/record_rules.xml`
- `security/security_groups.xml`
- `static/description/icon.png`
- `views/menus.xml`
- `views/views.xml`
- `changelog.d/2026-11-03-initial-crm-oms.md`
