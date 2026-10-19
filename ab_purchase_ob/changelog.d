Current changes before commit:

- Fix opening-run and receipt views failing in XML development mode by preserving leading architecture whitespace.
- Depend on the shared stock integration to restore missing store/company and source helper contracts.
- Scope delegated opening lines by their header company and serialize opening stock posting.
- Grant inventory managers the source and tax-read permissions required for opening entry without purchase roles.

Validation: 59 workflow/security checks and 4 concurrency checks passed; fresh installation, targeted upgrades and Arabic runtime labels verified. Live startup repair passed without changing stock or document states. View rendering passes 48 English/Arabic checks with --dev=xml; no UI strings or business logic changed by this XML repair.

Files changed:

- ab_purchase_ob/__manifest__.py
- ab_purchase_ob/changelog.d
- ab_purchase_ob/models/opening_balance_header.py
- ab_purchase_ob/models/opening_balance_line.py
- ab_purchase_ob/security/ir.model.access.csv
- ab_purchase_ob/views/opening_run.xml

9ffb7f85 | Alhassan Hossny | 2026-10-18 | feat(ab_purchase_ob): add independent opening runs and receipt corrections

- Install opening-stock operations independently of purchasing and accounting modules.
- Add one authorized opening run per branch with cutoff, explicit receipt reasons and irreversible closure after documents are received.
- Post other receipts and bounded corrections through the inventory engine; retain the original source and prevent cumulative over-correction.
- Create reviewable correction drafts with populated source lines and fail closed when accounting configurations would process unsupported corrections.
- Enforce branch/company permissions and maintain both Arabic catalogs.

Files changed:

- ab_purchase_ob/__manifest__.py
- ab_purchase_ob/changelog.d
- ab_purchase_ob/i18n/ar.po
- ab_purchase_ob/i18n/ar_001.po
- ab_purchase_ob/models/__init__.py
- ab_purchase_ob/models/opening_balance_header.py
- ab_purchase_ob/models/opening_balance_line.py
- ab_purchase_ob/models/opening_run.py
- ab_purchase_ob/security/company_rules.xml
- ab_purchase_ob/security/ir.model.access.csv
- ab_purchase_ob/security/record_rules.xml
- ab_purchase_ob/views/opening_run.xml
- ab_purchase_ob/views/source_integrity.xml

Validation:

- Fresh isolated installation, targeted upgrades, behavior/security checks, translation validation and operational evidence are recorded in `ab_independence_dev_plans/13_phase_1_6_execution.md`.

commit 5965f3db8b97be15add956c660db8f21b8da9556
Author: Alhassan Hossny <alhassan.hossny@gmail.com>
Date: 2026-09-30T09:55:53+03:00

    ab_purchase_ob/Update: mark opening receipt line grid as full-width

- Expand the opening receipt line grid to the full form width.

Files changed:

- ab_purchase_ob/views/opening_balance_header.xml

Earlier committed work (historical summary):

Historical implementation summary:

- Standardize Odoo 19 manifest version, company author, developer, and explicit application/install/auto-install flags; preserve active data-file order and remaining dependencies.
- Declare delegated product-source inheritance on opening balance lines and add the direct tax dependency used by the line defaults.
- Add explicit receipt purposes for opening inventory and non-purchase receipts, with document date/code and receipt type setup.
- Post receipt lines through `ab_inventory_process` under a savepoint, require manager access and positive quantities, and protect saved headers/lines from edits.
- Add separate menu flows for Opening Balance, Non-purchase Receipts, and Receipt Types.
- Generalize the inventory movement source label from opening-only to receipt-line based use.
- Add both Arabic translation catalogs for the ported receipt/opening module.

Files changed:

- ab_purchase_ob/__manifest__.py
- ab_purchase_ob/i18n/ar.po
- ab_purchase_ob/i18n/ar_001.po
- ab_purchase_ob/models/__init__.py
- ab_purchase_ob/models/ab_inventory_inherit.py
- ab_purchase_ob/models/opening_balance_header.py
- ab_purchase_ob/models/opening_balance_line.py
- ab_purchase_ob/models/receipt_type.py
- ab_purchase_ob/security/ir.model.access.csv
- ab_purchase_ob/views/opening_balance_header.xml
- ab_purchase_ob/changelog.d

Validation:

- Python syntax compile passed for ab_purchase_ob.
- XML parsing passed for ab_purchase_ob security and view files.
- Manifest parsing passed for ab_purchase_ob.
- Live rip_bconnect upgrade passed; ab_purchase_ob is installed at version 19.0.1.0.0.
- Rollback-only Plan 3 diagnostic passed for non-purchase receipt inventory posting and opening-balance accounting exclusion.

commit fc48a952be1fe29f411c546b3014aeef4b276e5b
Author: emadco88 <emadco88@gmail.com>
Date:   2026-09-23T15:55:52+03:00

    ab_purchase_ob/ NEED FIX , STILL ODOO15

- Import the existing Odoo 15 module as a foundation; full Odoo 19 compatibility remains pending.

Files changed:

- ab_purchase_ob/__init__.py
- ab_purchase_ob/__manifest__.py
- ab_purchase_ob/models/__init__.py
- ab_purchase_ob/models/ab_inventory_inherit.py
- ab_purchase_ob/models/opening_balance_header.py
- ab_purchase_ob/models/opening_balance_line.py
- ab_purchase_ob/security/ir.model.access.csv
- ab_purchase_ob/security/record_rules.xml
- ab_purchase_ob/security/security_groups.xml
- ab_purchase_ob/views/opening_balance_header.xml
