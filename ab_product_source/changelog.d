Current changes before commit:

- Assign immutable UUID identities to new sources and copies and retain explicit expiry handling without fabricated dates.
- Separate physical lots from receipt cost layers; preserve branch/company/document/database provenance and optional legacy/parent references.
- Enforce standalone source, physical-lot and price-history isolation, administrator-only store assignments, and company isolation for branch metadata.
- Audit source and master price changes with old/new values, actor and time; prevent edits or deletion of the audit history.
- Require explicit product eligibility for stock without expiry and validate native/legacy conversions and configured fractional stock precision.
- Protect posted stock-unit and service classification settings, including direct product-card changes; preserve frozen tax calculations for later quantities.
- Add administrator configuration access without deletion rights and expose stock configuration, physical lots and price history through module-owned views.
- Touch locked branch metadata so an older concurrent snapshot cannot accept a company change after new source history.
- Serialize source binding and branch-company changes with store-before-source locks; reject company changes after stock or sales history.
- Maintain both Arabic catalogs from the installed Odoo translation template, preserving existing entries.

Files changed:

- ab_product_source/__manifest__.py
- ab_product_source/changelog.d
- ab_product_source/i18n/ar.po
- ab_product_source/i18n/ar_001.po
- ab_product_source/models/__init__.py
- ab_product_source/models/ab_product_source.py
- ab_product_source/models/physical_lot.py
- ab_product_source/models/price_history.py
- ab_product_source/models/source_foundations.py
- ab_product_source/security/ir.model.access.csv
- ab_product_source/security/record_rules.xml
- ab_product_source/security/security_groups.xml
- ab_product_source/views/source_foundations.xml
- ab_product_source/views/source_integrity.xml

Validation:

- Fresh source-only installation and targeted upgrade in isolated `ab_source_foundation_test`; initial tax seed compatibility failure was corrected in its owning module before a successful retry.
- Python/XML parse and `git diff --check`; both Arabic catalogs pass `msgfmt --check-format`.
- 45 standalone conversion, expiry, immutable identity/history, scope and Arabic runtime checks passed and are recorded in `/tmp/ab_source_foundation_validation/checks.json`; final integrated release checks are coordinated separately.
- Three concurrent source-creation/company-change checks passed, preserving source/branch consistency.
- No live/external database changes or service restarts. Existing historical sources are not backfilled.

commit c2f8ebf5d573c9712e564727a23e003b5773d7c6
Author: yahyazakaria22 <yahyazakaria.soskty@gmail.com>
Date: 2026-09-27T09:38:45+03:00

    [fix]Modifying the module to Odoo 19

- Replace the Odoo 15 tree view and action mode with the Odoo 19 list view type.
- Replace legacy `name_get` behavior with an Odoo 19 computed display name.
- Update product-source name search to the Odoo 19 signature and compose its filters with `fields.Domain`.
- Preserve existing price, cost, tax, expiry, and unit-conversion behavior.
- Preserve existing English source strings; no user-facing text required translation updates.

Files changed:

- ab_product_source/changelog.d
- ab_product_source/models/ab_product_source.py
- ab_product_source/views/ab_product_source.xml

Validation:

- All module XML files parse successfully.
- Legacy Odoo 15 view/API scans pass.
- `git diff --check` passes.
- Python compilation and an Odoo database upgrade remain pending because a working Python/Odoo runtime is unavailable in this shell.

commit 4786f546e25101fcf835b0d15e032b177343258e
Author: emadco88 <emadco88@gmail.com>
Date:   2026-09-23T16:34:25+03:00

    ab_product_source/ FIX Odoo 19 manifest metadata

- Standardize the Odoo 19 manifest metadata while preserving dependencies and data-file order.

Files changed:

- ab_product_source/__manifest__.py
- ab_product_source/changelog.d

commit 3600e7503ecc50ab89eb8b48ead075cb9d3287fc
Author: emadco88 <emadco88@gmail.com>
Date:   2026-09-23T15:56:48+03:00

    ab_product_source/ NEED FIX , STILL ODOO15

- Import the existing Odoo 15 module as a foundation; full Odoo 19 compatibility remains pending.

Files changed:

- ab_product_source/__init__.py
- ab_product_source/__manifest__.py
- ab_product_source/models/__init__.py
- ab_product_source/models/ab_product_source.py
- ab_product_source/security/ir.model.access.csv
- ab_product_source/static/description/icon.png
- ab_product_source/views/ab_product_source.xml
- ab_product_source/views/menus.xml
- ab_product_source/views/sql_source_id.txt
