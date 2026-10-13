# Odoo 19 Custom Development

Target Odoo 19.0 and the project's existing `ab_*` conventions. Read applicable
repository guidance and inspect the affected module first. Use English for
technical communication unless requested otherwise. Make the smallest valid
diff; preserve XML IDs, module ownership, and unrelated work. Do not introduce
deprecated APIs, monkey patches, full JS overrides, or changes to shared frontend
components that affect other modules.
Use XML IDs for stable configured-record references, never hardcoded database
row IDs. Preserve existing XML IDs unless explicitly instructed otherwise.

Inventory integrity, pricing integrity, and branch/company isolation are
mandatory. Never physically delete products, categories, suppliers, purchase or
sales orders, inventory adjustments/transfers, stock recycling records,
contracts, price lists, branches, or warehouses; use supported archival/state
workflows. Never directly edit `qty_available`, `virtual_available`, `free_qty`,
`incoming_qty`, or `outgoing_qty`. Use Odoo stock business operations. External
B-Connect/E-Plus databases are read-only by default; external writes require
explicit authorization and must never bypass Odoo business logic.

Enforce permissions server-side, including direct ORM/RPC calls. UI visibility
is not security. Validate caller, role, target records, branch and company before
scoped `sudo()`; do not expose elevated recordsets. Check intended manager/admin
access before inherited lower-role restrictions. Restrict product code, barcode
and external-reference edits after creation to Inventory Managers/System
Administrators. Price changes must retain old/new values, actor and timestamp.

Use `ab_template` as the starting scaffold, only adding necessary files. New
module and custom-model technical names use underscores; preserve existing
model names and Odoo's native dotted names. Declare real dependencies in the
manifest, including `ab_hr` when used; do not install modules from Python. Keep
groups, memberships, privileges, ACLs and record rules in module-owned XML/CSV
under `security/`. Do not create/configure groups from Python or use `env.ref()`
to create another module's records. New modules are clean installations: no demo
files, unnecessary database edits, cron jobs, triggers or SQL, or hooks/migrations
for development database state.
Hooks require an explicitly requested bounded deployed-production migration.

Keep English source UI strings and Arabic translations in both `i18n/ar.po` and
`i18n/ar_001.po`; preserve existing `msgid` values and translations. Never hardcode
Arabic UI text in Python/XML/JS/Owl. Mark JS literals with `_t(...)`. Validate
every changed user-facing string in both languages before finishing.

Use focused skills for module development, Odoo 19 compatibility, security
reviews, validation, translation, B-Connect, optional Ready enrichment and
`ab_product_seo`. Their references contain detailed workflows, SQL and measured
baselines; load only relevant material. Run targeted installs/upgrades, never
`-u base` for routine work. Do not stop the user's Odoo process for validation.
Generated medical claims require human review and approval before publication.
For Trello boards, cards and checklist tasks, use the shared `trello-workflow` skill.
