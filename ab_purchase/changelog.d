Current changes before commit:

- Show purchase product search matches as selectable cards with product codes and purchase/sale prices, following the sales POS search pattern.
- Debounce product searches, ignore stale replies, show loading, result-count, and empty-result states, and keep keyboard selection visible while scrolling.
- Keep the product search and keyboard entry within the purchase-only OWL component and styles.
- Add a reverse line-cost calculator for purchase quick entry and existing lines, supporting sequential percentage discounts, selected taxes, paid quantity, and bonus quantity.
- Show the resulting unit purchase price, tax-inclusive unit cost, combined effective discount, and total difference after rounding before applying the price.
- Add manager-only Submit invoice and Post return actions to the OWL footer; return posting asks for confirmation and both actions use the existing server methods.
- Keep the reverse-cost dialog sizing compatible with Odoo's SCSS compiler by removing mixed-unit `min()` expressions.
- Put a calculator button beside purchase price and sale price in quick entry and invoice lines; calculate unit sale price from line sale total and paid quantity.
- Show Add line as a compact plus button in quick entry while retaining its accessible label.
- Remove Save and new from the data-entry footer and drop its unused save-and-reset branch.
- Place Unit beside Product and Sale price beside Quantity in quick entry and invoice lines; align Enter-key navigation with the new order.
- Rename purchase screen and form labels from selling price to sale price, including the validation message.
- Translate the new calculator, search, and submission messages in both Arabic catalogs.
- Block direct ORM changes to submitted purchase headers, lines, and source economics.
- Bind purchase sources to their originating invoice and branch when stock integration is installed.
- Verify receipt, supplier-return, accounting rollback, idempotency, and branch isolation through the backend QA runner.

Files changed:

- ab_purchase/static/src/entry/purchase_entry.js
- ab_purchase/static/src/entry/reverse_cost.js
- ab_purchase/static/src/entry/purchase_entry.xml
- ab_purchase/static/src/entry/purchase_entry.scss
- ab_purchase/models/ab_purchase_entry.py
- ab_purchase/models/ab_purchase_header.py
- ab_purchase/models/ab_purchase_line.py
- ab_purchase/models/ab_purchase_source_guard.py
- ab_purchase/views/ab_purchase_header.xml
- ab_purchase/__manifest__.py
- ab_purchase/i18n/ar.po
- ab_purchase/i18n/ar_001.po
- ab_purchase/changelog.d

commit cec171b8a552d6f25eedbd3f7a6244c4412bbb69
Author: yahyazakaria22 <yahyazakaria.soskty@gmail.com>
Date:   2026-10-19T02:59:57+03:00

    ab_purchase: protect posted purchase documents from deletion

- Prevent submitted and saved purchase invoices from being deleted, preserving their inventory source documents.
- Prevent saved purchase returns from being deleted, preserving their posted movement source documents.
- Translate the deletion messages in both Arabic catalogs.

Files changed:

- ab_purchase/changelog.d
- ab_purchase/i18n/ar.po
- ab_purchase/i18n/ar_001.po
- ab_purchase/models/ab_purchase_header.py
- ab_purchase/models/ab_purchase_notice_header.py

commit b68b8b34aba74df72104cd1a3117c32f83589251
Author: yahyazakaria22 <yahyazakaria.soskty@gmail.com>
Date:   2026-10-19T00:36:34+03:00

    Preserve inventory, purchase, product source and tax addons after sync

- Preserve the purchase addon while syncing the branch.

Files changed:

- ab_purchase/__manifest__.py
- ab_purchase/changelog.d
- ab_purchase/i18n/ar.po
- ab_purchase/i18n/ar_001.po
- ab_purchase/models/ab_purchase_entry.py
- ab_purchase/models/ab_purchase_header.py
- ab_purchase/models/ab_purchase_line.py
- ab_purchase/models/ab_purchase_links.py
- ab_purchase/models/ab_purchase_notice_header.py
- ab_purchase/models/ab_purchase_notice_line.py
- ab_purchase/models/ab_purchase_source_guard.py
- ab_purchase/security/company_rules.xml
- ab_purchase/security/ir.model.access.csv
- ab_purchase/security/security_groups.xml
- ab_purchase/static/src/dashboard/purchase_dashboard.js
- ab_purchase/static/src/entry/purchase_entry.js
- ab_purchase/static/src/entry/purchase_entry.scss
- ab_purchase/static/src/entry/purchase_entry.xml
- ab_purchase/views/ab_purchase_header.xml
- ab_purchase/views/ab_purchase_links_views.xml
- ab_purchase/views/source_integrity.xml

commit bd69753cc9e683a44834ffa142d25840a241d400
Author: Alhassan Hossny <alhassan.hossny@gmail.com>
Date:   2026-09-27T16:01:18+03:00

    ab_purchase/fix: Odoo 19 activation for delegated source lines

- Use Odoo 19 privileges for purchase security groups.
- Declare delegated product-source inheritance for purchase lines.
- Add the purchase security label to both Arabic catalogs.

Files changed:

- ab_purchase/changelog.d
- ab_purchase/i18n/ar.po
- ab_purchase/i18n/ar_001.po
- ab_purchase/models/ab_purchase_line.py
- ab_purchase/security/security_groups.xml
