## Current changes before commit

User-facing changes:

- Add the new `ab_sales_sync` module for MAIN-side branch sales operation mirrors.
- Add sales and sales-return header/line sync models with branch-scoped uniqueness by `db_serial` and `rec_id`.
- Add upload sources and auto-apply profiles for branch sales headers, lines, return headers, and return lines.
- Resolve shared product and store references through stable `eplus_serial` mappings instead of creating per-branch product or store mirrors.
- Add read-only manager security, record rules, MAIN inspection menus, views, and Arabic translations.
- Fix sales sync search views to use Odoo 19-compatible root-level group-by filters.
- Add Odoo module comments to Arabic PO entries so the Odoo 19 translation loader can import them safely.
- Validate the module with a targeted `-u ab_sales_sync --stop-after-init` run on `abdin_pos`.

Files changed:

- `ab_sales_sync/__init__.py`
- `ab_sales_sync/__manifest__.py`
- `ab_sales_sync/changelog.d/2026-08-17-initial-sales-sync.md`
- `ab_sales_sync/data/sync_profiles.xml`
- `ab_sales_sync/i18n/ar.po`
- `ab_sales_sync/i18n/ar_001.po`
- `ab_sales_sync/models/__init__.py`
- `ab_sales_sync/models/ab_sales_sync_models.py`
- `ab_sales_sync/security/ir.model.access.csv`
- `ab_sales_sync/security/record_rules.xml`
- `ab_sales_sync/security/security_groups.xml`
- `ab_sales_sync/views/ab_sales_sync_views.xml`
