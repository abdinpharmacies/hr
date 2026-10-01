# Verification — first-copy restoration

Verified with Odoo 19 and an isolated PostgreSQL 16 instance on 2026-10-01.
Initial functional checks used isolated databases. The existing development database
was subsequently backed up and upgraded as documented below.

- Clean `ab_accounting` install passed, without purchase modules.
- Targeted `ab_accounting` upgrade passed, without purchase modules.
- Purchase adapter and its dependencies installed successfully against the restored schema.
- Targeted upgrade of both accounting modules passed.
- All 208 explicitly declared first-copy fields were preserved; no fields were added.
- Python AST/compile, XML parsing, manifest file/load paths, diff whitespace and
  GNU `msgfmt --check-format` checks passed.
- 42 named functional checks passed, with additional confirmation, reversal,
  adapter posting and atomic-edit assertions. Scripts ran outside the addons and
  rolled back their data; no test directory was added.

Functional coverage includes balanced manual/automated posting, one-cent imbalance,
negative/non-finite/sub-cent amounts, both sides on a line, inactive/non-final or
unauthorized accounts, required dimensions, forbidden/inactive stores, inactive or
restricted cost centers, direct status bypasses, posted deletion/new-line restrictions,
creator/reviewer freeze and edit permissions, allowed-field edits, multi-line edits,
confirmation/reversal, supplier/inventory/tax mapping errors, missing tax/configuration,
inactive suppliers, purchase retry linkage, posted-only balance limits, archived
children and recursive account hierarchy.

The first-copy document-type model has no `active` field. Inactivity is validated
when supplied by an extension; the baseline uses document-type authorizations.
The first copy also has no account/company schema. Restoring it is not a migration
of populated journals created under the later replacement schema. Other populated databases using that replacement require a separately specified
mapping before upgrade; the small development dataset was audited explicitly below.

The isolated module installs show unrelated warnings in purchase dependency models
(e.g. legacy `auto_join` arguments). Those modules were not changed in this refactor.

## Startup repair on the existing development schema

The 2026-10-01 startup logs showed missing source columns during eager report-view
creation, followed by obsolete views/rules from the replacement accounting version.
The report now uses Odoo 19's `_table_query` API with explicit source dependencies.
The users view reuses `view_users_accounting` so its old unsupported fields are
replaced before inherited-view validation. No accounting fields were added.

A snapshot of `rip_bconnect` was upgraded in isolated PostgreSQL first. Its draft
journal (ID 9) and line (ID 23) retained their IDs, accounts, store, cost center and
amounts. The legacy period/report table rows remained present. Ordinary startup
without update flags passed. The account/cost-center relation's old column names
were renamed to the original names; that relation contained no rows. This is a
one-time development database correction, not a module hook or migration.

The startup command must include `ab_accounting` when applying this refactor;
upgrading only purchase and sync modules leaves the accounting schema stale.

After the snapshot checks, a fresh backup was taken with the server stopped. The
same relation-column correction and targeted `ab_accounting,ab_purchase_accounting`
upgrade passed on `rip_bconnect`. Read-only checks confirmed the existing journal
and line values and legacy period/report rows were preserved. The server restarted
without update flags; the registry loaded, the login endpoint on port 4097 returned
HTTP 200, and the restarted process logged no ERROR or CRITICAL entries. Unrelated
legacy `auto_join`, import-time translation and sales not-null warnings remain.

## Journal form table repair

Restored the prior responsive table approach for the original journal form, with
accounting-form-scoped assets, readable column widths and horizontal scrolling.
The embedded inherited list uses explicit `column_invisible` rules for internal
flags and fields. Standard Odoo 19 `<chatter/>` replaces legacy message-field
markup that caused the form sheet to collapse beside raw message tables.

XML/manifest checks and SCSS compilation passed. A backed-up targeted accounting
upgrade passed. Browser verification in the Arabic interface covered the new-record
form and adding an unsaved line in an existing journal: the sheet measured 1405px,
the scrolling container 1373px, the account column 240px, and page width stayed at
its 1600px viewport. Internal columns were absent. Unsaved checks were discarded;
read-only database verification confirmed existing journal values were unchanged.
No accounting model fields or posting behavior changed for this layout repair.
