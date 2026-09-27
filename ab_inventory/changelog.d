Current changes before commit:

- Replace the legacy pending inventory workflow with a branch-scoped movement ledger that stores a signed quantity change and per-movement closing balance while blocking negative batch stock.
- Keep saved movements immutable; add source-record duplicate prevention and a read-only balance API for later integrations.
- Add a period report with opening, incoming, outgoing, and closing balances plus item movement detail.
- Add a movement schedule with incoming, outgoing, and closing columns and a current stock balance report by store and batch.
- Rebuild `inventory_write()` as the trusted business-line interface, replacing `_post_movements()`; convert units exactly, upsert pending observations, and save one immutable movement per source record.
- Separate stock posting, quantity conversion, store authorization, and balance queries into `models/ab_inventory_process.py`; keep the movement model focused on fields and guarded CRUD.
- Make `ab_inventory_process` the single abstract operations service instead of a forwarding mixin; migrate purchase and opening-balance callers to explicit service calls.
- Read source, product, and store balances from the latest saved closing balance per source, including zero, with indexed source lookups rather than aggregating the full movement ledger; preserve exclusive historical cutoffs.
- Use latest per-source closing balances for current-stock reports and period-opening snapshots; keep period movement totals limited to the selected period.
- Calculate posting opening balances from indexed latest saved rows under the store lock, instead of summing each batch's full history.
- Make signed `qty` the only stored quantity input; derive read-only incoming/outgoing display amounts and freeze each movement's closing balance at posting.
- Remove the manually entered movement reference; identify records by movement ID and linked source metadata.
- Remove the redundant movement-direction selection; infer direction from the sign of `qty` and retain only an extendable source type.
- Align movement statuses with purchase as Pending and Saved; only Saved affects balances and is immutable.
- Remove the redundant operation key; serialize and reject duplicate source-record pairs during creation.
- Rename the movement timestamp to `saved_at` across balance cutoffs, reports, and movement screens.
- Remove reversal linkage, automatic reversal action, and free-text notes from the movement ledger.
- Rename the movement workflow field from `state` to `status` while retaining Pending/Saved behavior.
- Add inventory roles, branch record rules, and administrator-managed store assignments.
- Add Arabic translations for new screens and messages; remove legacy pending-source views and models.
- Replace the old truck app icon with an inventory warehouse-and-balance icon.
- Expose `ab_inventory_process.inventory_write()` directly to purchase and opening-balance consumers.
- Document signed-quantity posting, exact unit conversion, pending versus saved stock, balance reads, corrections, and transfer pairs.
- Add a module README covering architecture, stock semantics, direct service integration, security, screens, performance limits, and production verification.
- Clarify in both integration documents that `bonus` is purchase-specific; the inventory API accepts an explicit quantity and does not require a bonus field on other modules.
- Explain `get_balance()` step by step and document a separate, proposed screen-availability/reservation module with atomic holds, branch security, and clear on-hand/reserved/available quantities.
- Add `get_source_balances()` for batch lists that omit zero-balance sources by default, with `include_zero=True` for reports and audits; keep scalar `get_balance()` semantics unchanged.
- Simplify the integration examples to the two balance-read methods, documenting source-specific and zero-balance options separately.
- Move report models and views into a dedicated `report/` package without changing their model names or actions.

Files changed:

- ab_inventory/__manifest__.py
- ab_inventory/__init__.py
- ab_inventory/INTEGRATION.md
- ab_inventory/README.md
- ab_inventory/changelog.d
- ab_inventory/i18n/ar.po
- ab_inventory/i18n/ar_001.po
- ab_inventory/models/__init__.py
- ab_inventory/models/ab_inventory.py
- ab_inventory/models/ab_inventory_header.py (removed)
- ab_inventory/models/ab_inventory_process.py
- ab_inventory/models/ab_product.py
- ab_inventory/models/ab_product_inherit.py (removed)
- ab_inventory/models/ab_product_source.py
- ab_inventory/models/ab_product_source_inherit.py (removed)
- ab_inventory/models/ab_product_source_pending.py (removed)
- ab_inventory/models/res_users.py
- ab_inventory/report/__init__.py
- ab_inventory/report/ab_inventory_balance_report.py
- ab_inventory/report/ab_inventory_balance_report.xml
- ab_inventory/report/ab_inventory_period_report.py
- ab_inventory/report/ab_inventory_period_report.xml
- ab_inventory/security/ir.model.access.csv
- ab_inventory/security/record_rules.xml
- ab_inventory/security/security_groups.xml
- ab_inventory/static/description/icon.png
- ab_inventory/views/ab_inventory_header.xml (removed)
- ab_inventory/views/ab_inventory_movements.xml
- ab_inventory/views/ab_product_source_inherit.xml (removed)
- ab_inventory/views/ab_product_source_pending.xml (removed)
- ab_inventory/views/menus.xml
- ab_inventory/views/res_users_inventory.xml

Validation:

- All remaining module XML files parse successfully.
- Translation entry pairs have no duplicate message identifiers.
- `git diff --check` passes.
- A targeted Odoo 19 install/upgrade, POT export, `msgfmt`, and runtime language check are pending because the Odoo/Python/gettext tools are unavailable locally.

commit da3754e09c65e74b83715008e7033c51cefa948d
Author: emadco88 <emadco88@gmail.com>
Date:   2026-09-23T16:34:09+03:00

    ab_inventory/ FIX Odoo 19 manifest metadata

- Standardize the Odoo 19 manifest metadata while preserving dependencies and data-file order.

Files changed:

- ab_inventory/__manifest__.py
- ab_inventory/changelog.d

commit 65e0c40e3b7ed38f689cc908fa689beee3eecb63
Author: emadco88 <emadco88@gmail.com>
Date:   2026-09-23T15:56:26+03:00

    ab_inventory/ NEED FIX , STILL ODOO15

- Import the existing Odoo 15 module as a foundation; full Odoo 19 compatibility remains pending.

Files changed:

- ab_inventory/__init__.py
- ab_inventory/__manifest__.py
- ab_inventory/models/__init__.py
- ab_inventory/models/ab_inventory.py
- ab_inventory/models/ab_inventory_header.py
- ab_inventory/models/ab_inventory_process.py
- ab_inventory/models/ab_product_inherit.py
- ab_inventory/models/ab_product_source_inherit.py
- ab_inventory/models/ab_product_source_pending.py
- ab_inventory/security/ir.model.access.csv
- ab_inventory/static/description/icon.png
- ab_inventory/views/ab_inventory_header.xml
- ab_inventory/views/ab_product_source_inherit.xml
- ab_inventory/views/ab_product_source_pending.xml
- ab_inventory/views/menus.xml
