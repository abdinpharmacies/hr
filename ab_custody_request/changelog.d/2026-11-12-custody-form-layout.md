# ab_custody_request

## 43af8349 — emadco88 — 2026-11-09

Original commit subject: migrate19 INIT

- Imported the custody request module and its existing request, account, employee account, and configuration screens.

Files changed:

- `ab_custody_request/__init__.py`
- `ab_custody_request/__manifest__.py`
- `ab_custody_request/data/template_custody_request_email.xml`
- `ab_custody_request/i18n/ar_001.po`
- `ab_custody_request/models/__init__.py`
- `ab_custody_request/models/ab_custody_employee_data.py`
- `ab_custody_request/models/ab_custody_request_account.py`
- `ab_custody_request/models/ab_custody_request_config.py`
- `ab_custody_request/models/ab_custody_request_header.py`
- `ab_custody_request/models/ab_custody_request_line.py`
- `ab_custody_request/security/ir.model.access.csv`
- `ab_custody_request/security/record_rules_ab_custody_request_header.xml`
- `ab_custody_request/security/record_rules_ab_custody_request_line.xml`
- `ab_custody_request/security/security_groups.xml`
- `ab_custody_request/static/description/icon.png`
- `ab_custody_request/views/ab_custody_employee_data.xml`
- `ab_custody_request/views/ab_custody_request_account.xml`
- `ab_custody_request/views/ab_custody_request_config.xml`
- `ab_custody_request/views/ab_custody_request_header.xml`
- `ab_custody_request/views/menus.xml`

## ba2649988 — hager yasser — 2026-11-12

Original commit subject: `ab_custody_request/FIX: repair form layouts and contain detail table scrolling`

- Align request entry and accounting sections, remove empty separator rows, and give custody detail tables their full page width.
- Contain custody detail table horizontal overflow in its native list renderer, with a named wrapper scoping the presentation rules and preserving the original sheet, notebook, and field classes.
- Keep the custody detail table header in normal flow inside the scroll wrapper so it cannot overlap the first row or the Add a line control; other list views retain their sticky headers.
- Restore the native renderer's automatic height and horizontal scrolling locally despite the shared overflow override; give header labels normal line height and vertical padding to avoid top clipping.
- Repair request total stat buttons with translation-safe structural anchors and use the native Odoo 19 chatter.
- Arrange employee accounts, custody accounts, and configuration forms into balanced columns using existing fields and labels.
- Preserve business attributes, button methods, workflow conditions, domains, and contexts through inherited XML views.

Files changed:

- `ab_custody_request/views/ab_custody_employee_data.xml`
- `ab_custody_request/views/ab_custody_request_account.xml`
- `ab_custody_request/views/ab_custody_request_config.xml`
- `ab_custody_request/views/ab_custody_request_header.xml`
- `ab_custody_request/changelog.d/2026-11-12-custody-form-layout.md`

Validation:

- The latest targeted upgrade and en_US/ar_001 runtime checks pass for native-renderer scrolling, automatic height, header label padding/line height, and unchanged editing controls; browser visual verification remains unavailable.
- The targeted request-module upgrade and en_US/ar_001 runtime checks pass for the custody-only non-sticky header rule, retained horizontal scrolling, and unchanged editable-list options.
- The containment rules are scoped to the custody detail table's native renderer; the extra outer scroll boundary and sheet, notebook, and detail-field sizing overrides were removed.
- The targeted request-module upgrade and en_US/ar_001 runtime checks pass with the original field classes, automatic renderer height, and unchanged editable-list options.
- Targeted custody-module upgrades completed successfully; no Python, model, manifest, security, or business-logic files were edited.
- Static inheritance and business-attribute comparisons cover all eight forms and the optional HR employee-account extension.
- Odoo runtime checks resolve all eight forms in en_US and ar_001; the request and reconciliation forms retain language-specific translated content. The custody journal-entry extension resolves successfully.
- During the earlier form-layout verification, the restored database had no custody records or authorized reconciliation users for record-level checks; reconciliation view checks used the existing superuser context. No business records or user permissions were changed for verification.
- Existing labels and translation files are unchanged; the added inherited views introduce no new user-facing strings.
- Browser visual verification is unavailable in this session.
