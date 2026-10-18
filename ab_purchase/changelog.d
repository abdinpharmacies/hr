Current changes before commit:

- Prevent submitted and saved purchase invoices from being deleted, preserving their inventory source documents.
- Prevent saved purchase returns from being deleted, preserving their posted movement source documents.
- Translate the new deletion messages in both Arabic catalogs.
- Confirm the existing purchase store and saved return identity guards already prevent reassignment after posting.

Files changed:

- ab_purchase/models/ab_purchase_header.py
- ab_purchase/models/ab_purchase_notice_header.py
- ab_purchase/i18n/ar.po
- ab_purchase/i18n/ar_001.po
- ab_purchase/changelog.d

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
