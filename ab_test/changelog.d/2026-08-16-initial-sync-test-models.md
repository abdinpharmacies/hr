<<<<<<< Updated upstream
## Commit 6c024bf

Author: Alhassan Hossny
Date: 2026-08-16
Subject: ab_test/ test module for sync testing
=======
## 6c024bf0e6d109ed969d10ff415d3b11273e63d0

- Author: Alhassan Hossny <alhassan.hossny@gmail.com>
- Date: Sun Aug 16 17:07:34 2026 +0300
- Subject: ab_test/ test module for sync testing
>>>>>>> Stashed changes

User-facing changes:

- Added relational source models for categories, tags, headers, and child lines.
- Added stored totals, JSON fields, relational test coverage, security, views, and Arabic translations.

Files changed:

- `ab_test/__init__.py`
- `ab_test/__manifest__.py`
- `ab_test/changelog.d/2026-08-16-initial-sync-test-models.md`
- `ab_test/i18n/ar.po`
- `ab_test/i18n/ar_001.po`
- `ab_test/models/__init__.py`
- `ab_test/models/ab_test_models.py`
- `ab_test/security/ir.model.access.csv`
- `ab_test/security/record_rules.xml`
- `ab_test/security/security_groups.xml`
- `ab_test/views/ab_test_views.xml`

<<<<<<< Updated upstream
## Current changes before commit

User-facing changes:

- Added dedicated source models for cascade, set-null, and restrict delete policy testing.
- Added parent/child relationships that exercise `ondelete="cascade"`, `ondelete="set null"`, and `ondelete="restrict"` directly.
- Added full CRUD access rules so test users can create child records and trigger each delete behavior from the UI.
- Added Delete Policy Tests menus and views for the new parent and child records.
- Added Arabic translations for the new delete-policy test screens and model labels.

Files changed:

- `ab_test/changelog.d/2026-08-16-initial-sync-test-models.md`
- `ab_test/i18n/ar.po`
- `ab_test/i18n/ar_001.po`
- `ab_test/models/ab_test_models.py`
- `ab_test/security/ir.model.access.csv`
- `ab_test/security/record_rules.xml`
=======
## Current changes before commit:

User-facing changes:

- Use the shared Odoo Sync JSON widget for editable header settings.
- Add a complete test-line form with a formatted and validated attributes JSON editor.
- Add the explicit `ab_odoo_sync` dependency and bump the module version to `19.0.1.1.0`.

Files changed:

- `ab_test/__manifest__.py`
- `ab_test/changelog.d/2026-08-16-initial-sync-test-models.md`
>>>>>>> Stashed changes
- `ab_test/views/ab_test_views.xml`
