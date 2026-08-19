## Commit 6c024bf

Author: Alhassan Hossny
Date: 2026-08-16
Subject: ab_test/ test module for sync testing

User-facing changes:

- Added four relational source models for branch-to-MAIN synchronization testing.
- Added test categories with self-parent relations, tags, headers, and child lines.
- Added stored computed totals, JSON fields, selections, dates, Many2one, One2many, and Many2many relationships.
- Added module-owned access groups, record rules, menus, and administration views.
- Added complete Arabic translations for both supported Arabic locales.

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
- `ab_test/views/ab_test_views.xml`
