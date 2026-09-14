Reference commit: 3db5d596c9429ff082c3fe9b0466692b945f788f
Author: emadco88
Date: 2026-07-28T15:21:42+03:00
Original commit subject: INIT commit pos19

User-facing changes in the reference commit:
- Introduce the existing cashier workflow extended by this bridge.

Current changes before commit:
- Add the ab_sales_routing bridge, owned by Abdin Pharmacies and developed by hossam elsheikh. Install explicitly with its sales and cashier dependencies.
- Route sale/return connections, POS stock/customer helpers, default-store inventory, local SQL status, and cashier invoice operations to the selected store's configured ip1, including the replica default store.
- Keep ab_branch_api untouched; its existing calls resolve through inherited bridge methods. Preserve callcenter API health checks without a direct SQL probe.
- Preserve parent workflow and access checks through super calls. Use a request-scoped port target for the legacy local status method and reset it after failures as well as success.
- Reject blank addresses before external work. Preserve meaningful connection/access errors and sanitize unexpected driver errors.
- Include Arabic catalogs from an Odoo 19 POT export, installation/behavior documentation and the standard module icon. No new model, fields, ACL grants, menu, cron, hook or migration is introduced.

Files changed:
- ab_sales_routing/__init__.py
- ab_sales_routing/__manifest__.py
- ab_sales_routing/models/__init__.py
- ab_sales_routing/models/sales_routing.py
- ab_sales_routing/i18n/ar.po
- ab_sales_routing/i18n/ar_001.po
- ab_sales_routing/README.md
- ab_sales_routing/static/description/icon.png
- ab_sales_routing/changelog.d/2026-09-14-sales-routing.md

Validation:
- Fresh installs passed on isolated codex_sales_routing_branch and codex_sales_routing_callcenter. The callcenter registry used a temporary addons-path overlay pointing at this module; its root directory does not allow creation of a new addon folder by the current OS account.
- Five bridge check groups passed on each registry: configured-IP routing, local status target reset and RPC context isolation, missing-IP rejection, safe connector errors, and the real cashier pending-invoice query with a mocked SQL connection and store predicate assertions. Public-user cashier access was denied.
- Existing branch API and callcenter regression checks passed with E-Plus mocked: native credentials, all eight methods, business access, DB serial identity, costs, sale/return requests, token ownership/replay, and API-only health checks.
- Targeted bridge upgrades passed on both isolated registries. Both new Arabic catalogs and the retained callcenter Arabic catalogs passed msgfmt --check-format; all final exported terms are covered. Missing-IP errors for sales/returns/POS/cashier and an existing action label differ from English at runtime. Native POT and runtime evidence are retained outside the addon.
- ab_branch_api content hashes remained unchanged. The branch ab_sales models/UI/catalogs match their pre-connectivity state, retaining only the earlier return-security changes.
- Scripts and logs are retained in /tmp/ab_sales_routing_validation. No development tests or fixtures are shipped with this addon.

Scope: source work only. No live application install/upgrade, restart, configured-IP edit, or external database write. Legacy cashier behavior on an unavailable SQL server is unchanged; the bridge corrects its target address.
