Current changes before commit:

- Make the cashier addon depend on native sales inventory and settle approved pending invoices without another stock deduction.
- Own native cash-count models, security and views in the optional cashier addon.
- Replace hardcoded Arabic cashier labels with translatable English source strings and add both Arabic catalogs.
- Route legacy operations through the optional sales connector abstraction so the cashier addon installs without E-Plus.
- Keep ordinary cash-count access branch-scoped across active-company switches while retaining company scope for managers.
- Pass the authenticated PIN session into the original Close Cashier dialog and avoid asking for the same PIN again inside that dialog.

Validation:

- Fresh optional installation passed after native inventory was already installed without E-Plus.
- A rollback-only suite passed 27 collection, refund, atomicity, idempotency, branch, wallet and raw-ORM guard checks.
- Independent transactions proved settlement and cancellation produce one valid terminal state.
- English/Arabic views, actions, JavaScript and OWL templates compiled server-side without browser automation.
- The restored legacy close form compiled and rendered with the active session context during the targeted cashier and cash-shift upgrade.

Files changed:

- ab_sales_cashier/__manifest__.py
- ab_sales_cashier/changelog.d/2026-10-21-native-collection.md
- ab_sales_cashier/i18n/ar.po
- ab_sales_cashier/i18n/ar_001.po
- ab_sales_cashier/models/__init__.py
- ab_sales_cashier/models/ab_sales_cashier_api.py
- ab_sales_cashier/models/native_inventory.py
- ab_sales_cashier/security/ir.model.access.csv
- ab_sales_cashier/security/record_rules.xml
- ab_sales_cashier/static/src/cashier/cashier_action.js
- ab_sales_cashier/static/src/cashier/cashier_action.xml
- ab_sales_cashier/views/native_inventory.xml

1f4a2040 | emadco88 | 2026-10-08 | ab_sales_cashier/ UPD remove lookup on bconnect

- Removed the cashier's direct B-Connect lookup path.

Files changed:

- ab_sales_cashier cashier models and frontend assets.
