Recent relevant commit:

- Commit: `0eda2686d9f8d83279ec64db46cb05fc378b6d88`
- Author: Alhassan Hossny
- Date: 2026-09-07
- Original subject: ab_sales: scope passive mixin to high-value mirrors
- User-facing changes:
  - Scoped shared passive metadata to high-value sales mirrors.
  - Included archived invoices in the sales reporting action.
- Files changed:
  - ab_sales/changelog.d/2026-09-03-report-server-passive-cleanup.md
  - ab_sales/models/ab_sales_mirror_models.py
  - ab_sales/views/sales_mirror_views.xml

Current changes before commit:

- User-facing changes:
  - Adapted supported POS sales, return, inventory, metadata and printer layouts to existing passive reporting fields; retained source metadata and payload inspection.
  - Restored customer anchors required by doctor prescription list/search extensions.
  - Matched POS Sales, Bills, Returns, Configurations and Reports menu ordering while retaining reporting-only entries and existing XML IDs.
  - Kept mirror forms and lists read-only, with no operational buttons, business logic, assets or security changes.
  - Added Arabic translations in both catalogs and removed conflicting duplicate entries and stale action/menu references while preserving existing message IDs.
- Files changed:
  - ab_sales/views/sales_mirror_views.xml
  - ab_sales/views/sales_mirror_extra_views.xml
  - ab_sales/i18n/ar.po
  - ab_sales/i18n/ar_001.po
  - ab_sales/changelog.d/2026-09-30-pos-reporting-views.md
- Validation:
  - Installed ab_sales_doctor successfully on report19; checked all four inherited sales views.
  - Validated 32 sales views, menu hierarchy, read-only mirror ACLs, and en_US/ar_001 action labels.
  - Exported the Odoo POT and checked both catalogs with msgfmt --check-format.
  - Targeted ab_sales upgrade applied its views, then failed in existing dependent ab_sales_sync profile updates: read-only create_uid cannot be enabled for synchronization. Refreshed the final ab_sales XML through Odoo's XML loader and translations through the module translation loader; left ab_sales_sync unchanged.
