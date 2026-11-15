# abdin_eplus

## Current changes before commit:

- Document the committed timestamp index, its targeted-upgrade deployment, and disposable validation results.

Files changed:

- `abdin_eplus/changelog.d/2026-11-14-sales-timestamp-index.md`

## 515c2bd07 — emadco88 — 2026-11-14

Original commit subject: `abdin_eplus/ UPD add index to sec_insert_date field`

- Add the Odoo-managed B-tree index to the sales-header `sec_insert_date_h` timestamp used by the default descending list order.
- Preserve the field label, list ordering, replication, and access behavior. Existing databases receive the index during a targeted `abdin_eplus` upgrade; schedule the large-table build in a maintenance window.
- User-facing strings are unchanged, so translation updates are not needed. No hooks or migrations are added.

Files changed:

- `abdin_eplus/models/eplus_tables.py`

Validation:

- Python compilation and `git diff --check` passed. The field label and existing user-facing strings are unchanged.
- A fresh installation of the actual `abdin_eplus` module in disposable Odoo 19 validation created `abdin_eplus_r_sales_trans_h__sec_insert_date_h_index` as a B-tree index.
- With 25,000 synthetic sales headers, `ORDER BY sec_insert_date_h DESC LIMIT 100` used a backward scan on that index without a sort. Its measured 0.045 ms fixture execution is not a production performance guarantee.
- The disposable database was removed. No live index, module upgrade, backup, or data change was performed against `main19` or the external E-Plus database.

## 43af83499 — emadco88 — 2026-11-09

Original commit subject: `migrate19 INIT`

- Introduced the module's E-Plus models, including the sales-header timestamp and its default descending sort, which previously had no timestamp index.

Files changed (relevant model):

- `abdin_eplus/models/eplus_tables.py`
