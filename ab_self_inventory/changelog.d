# ab_self_inventory changelog

## Unreleased — Branches reporting to managed departments

- Area Manager – Read Only now resolves branches only through the user's active
  employees, the active departments they manage, and those departments' active
  direct child departments (`manager_id` → child `parent_id` → `store_id`).
  Stores must be active and have type `branch`. The parent department's own
  office store is not included.
- `workplace_region` no longer grants access. Shared, different, or missing
  regions do not change branch permissions.
- All 13 Self Inventory access tests passed in an isolated database, including
  same-region manager isolation, direct read denial, inactive mappings, and
  existing read-only/report protections.
- Restart Odoo workers to load the Python change and discard cached rule domains.
  HR records and production inventory data are unchanged.

## Previous implementation — Area Manager – Read Only

- Grant read access to processes and product lines in all states for branches
  sharing an area with departments managed by the user's linked employees.
- Use active employees, departments, and branch stores; missing mappings grant
  no inventory access. No custom ir.rule extension is used. Restart all Odoo
  workers after HR area/branch reassignment to refresh cached access rules.
- Show Processes only and provide Export Saved Report without refreshing stock
  or resetting count results. Keep operational actions unavailable.
- Assign the normal XML group under the existing Self Inventory privilege/category,
  using the same group/privilege pattern as Quality Assurance. No res.groups
  extension or custom role-conflict validation is used.
- For area-only, read-only access, assign this as the user's only Self Inventory
  role. As in Quality Assurance, standard Odoo permissions are additive: other
  roles may grant broader access. Managers and system administrators retain their
  existing access. The HR mapping is unchanged; area_security.py and its import
  have been removed without introducing a replacement model.
- Deploy with a restart and targeted upgrade of ab_self_inventory only. No
  production database upgrade is performed by this source change.
- Area-access tests explicitly refresh the standard rule cache after HR changes;
  they do not assert automatic cache revocation.
- After removing the extension, all 12 tests passed on a targeted module upgrade
  in the isolated temporary database.

## Recent commits

### 684e50f

Author: Mohamed Fawzy
Date: 2026-08-26
Subject: ab_self_inventory/chore(#2312):Inventory Count Snapshot, Partial Progress, and Result Reporting Plan

User-facing changes:
- Save Balance at Count snapshots when exporting count sheets.
- Import Actual Qty and optional Balance at Count from partial Excel uploads.
- Calculate shortage, excess, matched, and implementation progress from saved count data.
- Require all requested products to be counted before final inventory submission.

Files changed:
- ab_self_inventory/i18n/ab_self_inventory.pot
- ab_self_inventory/i18n/ar.po
- ab_self_inventory/i18n/ar_001.po
- ab_self_inventory/models/self_inventory_process.py
- ab_self_inventory/models/self_inventory_request.py
- ab_self_inventory/reports/self_inventory_xlsx.py
- ab_self_inventory/static/src/js/self_inventory_form_widgets.js
- ab_self_inventory/static/src/scss/self_inventory_form.scss
- ab_self_inventory/views/self_inventory_process_views.xml
- ab_self_inventory/wizard/self_inventory_import_wizard.py

## Current changes before commit

User-facing changes:
- Show only one visible row result column, Difference, on active self inventory process lines.
- Color the Difference result box by row state: shortage yellow, excess red, and matched green.
- Keep the inventory progress donut, progress bar, and stat boxes on one horizontal line.
- Remove Counted and Pending stat boxes from the inventory progress panel.
- Remove the Actual Qty spinner controls and sort icon from the process count grid.
- Add a separate Inventory Implementation percentage column to the self inventory request list.

Files changed:
- ab_self_inventory/i18n/ab_self_inventory.pot
- ab_self_inventory/i18n/ar.po
- ab_self_inventory/i18n/ar_001.po
- ab_self_inventory/static/src/js/self_inventory_form_widgets.js
- ab_self_inventory/static/src/scss/self_inventory_form.scss
- ab_self_inventory/views/self_inventory_request_views.xml
- ab_self_inventory/views/self_inventory_process_views.xml
- ab_self_inventory/changelog.d
