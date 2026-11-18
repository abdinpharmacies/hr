# Form access repair — 2026-11-18

## Recent relevant commit

- Commit: `4ebaf1eedb45d83aa3d309d0631b405b942545a5`
- Author: Hossam Elsheikh
- Date: 2026-11-17 15:16:09 +0200
- Original commit subject: `ab_fixed_asset/FIX: correct valuation and protect asset movements`
- Corrected asset valuation and movement protections, refreshed forms and translations, and documented the access rollback.

Files changed:

- `ab_fixed_asset/changelog.d/2026-11-15-checklist-repair.md`
- `ab_fixed_asset/changelog.d/2026-11-15-workflow-safety.md`
- `ab_fixed_asset/changelog.d/2026-11-17-access-rollback.md`
- `ab_fixed_asset/i18n/ar.po`
- `ab_fixed_asset/i18n/ar_001.po`
- `ab_fixed_asset/models/ab_accounting_je.py`
- `ab_fixed_asset/models/ab_fixed_asset_assets_inventory.py`
- `ab_fixed_asset/models/ab_fixed_asset_inventory_line.py`
- `ab_fixed_asset/models/ab_fixed_asset_move_wizard.py`
- `ab_fixed_asset/views/ab_fixed_asset_assets_inventory.xml`
- `ab_fixed_asset/views/ab_fixed_asset_move_wizard.xml`

## Current changes before commit:

- Omit journal details, transfer-line details and cost-center controls when their existing model read ACL is absent. Keep Manager submission and Accountant confirmation intact; cost-center edits require an already-authorized user.
- Also omit unreadable journal lines from asset forms, fixing Asset User/Manager creation refresh, reopening and draft editing discovered by the synthetic replacement cases.
- Filter each returned form architecture after the shared cache; preserve ACLs, groups, memberships, record rules and business operations.
- Verification: Eight Manager-to-Accountant browser workflows, authorized cost-center editing, 42 backend regressions, valuation/role assertions and mixed-role view-cache checks. Synthetic replacement coverage adds 34 ORM assertions and browser create/edit/search/protection checks; direct journal read denial remains intact.
- No new or changed user-facing strings; both Arabic translation files remain unchanged. Existing English/Arabic form differences verified.

Files changed:

- `ab_fixed_asset/models/ab_fixed_asset_assets_inventory.py`
- `ab_fixed_asset/models/ab_fixed_asset_move_wizard.py`
- `ab_fixed_asset/changelog.d/2026-11-18-view-access.md`
