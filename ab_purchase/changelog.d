Current changes before commit:

- Add a separate Data Entry client-action window with purchase/return tabs, supplier and product search, an editable line grid, live reconciliation totals, draft queue, and Save and new. Restore the standard Odoo form views.
- Search suppliers by name or code with native autocomplete and keyboard selection; move focus to the document number after selection.
- Add a product entry strip with Enter navigation through quantity and prices, Ctrl+Enter addition, automatic focus back to search, and keyboard navigation in the existing line grid.
- Display many2many taxes as tags with checkbox selection in the entry strip and line grid; preserve all selected taxes when saving and reopening drafts.
- Verify all purchase view tags and action view modes use list; preserve existing external IDs.
- Enable branch-scoped draft creation and editing for the data entry team; keep posting manager-only and guard product-source changes after submission.
- Enable vertical dashboard scrolling inside the action viewport.
- Link each return to its original purchase invoice and line; inherit its store, supplier, product source, and unit.
- Track paid and bonus quantities separately; prevent cumulative over-returns and changes to posted documents.
- Allocate invoice discounts proportionally to partial returns; post returns through the existing inventory API under the store lock.
- Extend the existing overview dashboard with received, returned, and retained values and receipt/return movement counts. Drilldowns open standard Odoo views.
- Restrict purchase and return records to assigned stores for ordinary users; preserve manager and administrator access.
- Validate invoice and tax totals before submission and receipt; correct compound-tax line-cost inversion and zero-quantity handling.
- Keep purchase details visible, replace legacy chatter fields with Odoo 19 chatter, and use master prices for first purchases.
- Preserve the working-tree change allowing draft-only store editing.
- Append translations from the Odoo-exported POT to both Arabic catalogs while preserving existing entries.

Files changed:

- ab_purchase/__manifest__.py
- ab_purchase/changelog.d
- ab_purchase/i18n/ar.po
- ab_purchase/i18n/ar_001.po
- ab_purchase/models/__init__.py
- ab_purchase/models/ab_purchase_dashboard.py
- ab_purchase/models/ab_purchase_header.py
- ab_purchase/models/ab_purchase_line.py
- ab_purchase/models/ab_purchase_links.py
- ab_purchase/models/ab_purchase_source_guard.py
- ab_purchase/models/ab_purchase_entry.py
- ab_purchase/security/ir.model.access.csv
- ab_purchase/security/record_rules_purchase_header.xml
- ab_purchase/security/record_rules_purchase_notice_header.xml
- ab_purchase/security/record_rules_data_entry.xml
- ab_purchase/static/src/dashboard/purchase_dashboard.js
- ab_purchase/static/src/dashboard/purchase_dashboard.xml
- ab_purchase/static/src/dashboard/purchase_dashboard.scss
- ab_purchase/static/src/entry/purchase_entry.js
- ab_purchase/static/src/entry/purchase_entry.xml
- ab_purchase/static/src/entry/purchase_entry.scss
- ab_purchase/views/ab_purchase_header.xml
- ab_purchase/views/ab_purchase_links_views.xml
- ab_purchase/views/ab_purchase_entry_views.xml

Validation:

- Targeted ab_purchase upgrade passed on abdin_replica19.
- Rollback-only ORM checks passed for receipt posting, partial/full returns, discount allocation, cumulative quantity limits, repeated submission, stock balances, and dashboard access.
- Branch-scoped purchase/return reads and rejection of another store's dashboard passed.
- Compound-tax inversion passed within the purchase-price field's rounding precision.
- Python syntax, XML parsing, JavaScript syntax, SCSS compilation, and git diff --check passed.
- Both PO catalogs passed Babel format checks; Arabic action translation differed from English during rollback-only language activation. GNU msgfmt is unavailable locally.
- Data entry role tests passed: create/edit drafts, reject posting and pending-source changes, and manager receipt/return posting.
- The standalone OWL window mounted in headless Chrome; product search, quantity edits, live totals, draft saving/reloading, and return calculations passed with mocked RPC.
- Headless keyboard checks passed using the native supplier autocomplete: selection with Enter, quantity/price focus navigation, Ctrl+Enter, validation, and multiple-tax save/reload; RPC and layout/service hooks were mocked.
- Rollback-only window API checks passed for draft saving/reloading, stale-save rejection, excess-return rejection, store isolation, restored native forms, and Arabic action translation. Earlier dashboard scrolling check passed in Chrome.
- Supplier code lookup and many2many tax save/load/clear passed in rollback-only ORM checks.
- Full interaction in the authenticated Odoo browser remains manual. Restart the running Odoo process to load Python changes.

commit bd69753cc9e683a44834ffa142d25840a241d400
Author: Alhassan Hossny <alhassan.hossny@gmail.com>
Date:   2026-09-27T16:01:18+03:00

    ab_purchase/fix: Odoo 19 activation for delegated source lines

- Use Odoo 19 privileges for purchase security groups.
- Declare the delegated product-source inheritance mapping for purchase lines.
- Add module comments to both Arabic translation files and translate the Abdin Purchase security label.

Files changed:

- ab_purchase/changelog.d
- ab_purchase/i18n/ar.po
- ab_purchase/i18n/ar_001.po
- ab_purchase/models/ab_purchase_line.py
- ab_purchase/security/security_groups.xml
