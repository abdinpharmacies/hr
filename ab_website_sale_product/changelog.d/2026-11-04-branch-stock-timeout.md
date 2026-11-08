# Branch stock query timeout

## Current changes before commit:

- Use the existing connector's ODBC backend for branch-stock reads. The installed SQL Server ODBC driver avoids pymssql's process-wide timeout changes from connection-health probes; no shared connector implementation was changed.
- Discover branch identifiers from Eplus `Store`, then parameterize each stock query by `sto_id` rather than aggregating the entire network in one statement. Preserve existing quantity units and committed-read policy, and fetch at most 1,000 result rows per batch.
- Retry without branch-name columns only for ODBC missing-column SQLSTATE `42S22` before any result for that branch has been consumed. Do not retry a metadata query after a timeout or disconnection.
- Convert source failures to a translated user error. Retain the existing savepoint that rolls back partial snapshot updates on failure.
- Add the exported error term to both Arabic catalogs without replacing concurrent translation work.

Files changed:

- `ab_website_sale_product/models/eplus_stock_snapshot.py`
- `ab_website_sale_product/i18n/ab_website_sale_product.pot` (append only the new exported term; preserve concurrent work)
- `ab_website_sale_product/i18n/ar.po`
- `ab_website_sale_product/i18n/ar_001.po`
- `ab_website_sale_product/changelog.d/2026-11-04-branch-stock-timeout.md`
- `ab_website_sale_product/changelog.d/2026-11-04-authoritative-eplus-stock.md`

Validation:

- Final targeted upgrade and inventory/reservation integration run on isolated `codex_eplus_sync_20261104`: 51 tests, 0 failures, 0 errors. Includes bound branch parameters, ODBC selection, bounded fetches, missing-column fallback, no timeout fallback, and preservation after partial read failure.
- Exported the Odoo 19 POT to `/tmp/eplus-branch-timeout.pot`; both Arabic catalogs passed `msgfmt --check-format`. Python syntax and whitespace checks passed.
- Read-only live Eplus probe returned the first 1,000 rows for one branch in 1.54 seconds, with all returned rows belonging to that branch. No source data or operational Odoo inventory was modified. A complete all-branch production refresh remains unverified.
- Runtime failure simulation verified distinct English and Arabic (`ar_001`) messages. The local module POT also contains the new term so Odoo does not discard it when merging catalog references.
- Full test log: `/tmp/eplus-sync-validation.log`. The test clone retains pre-existing missing-filestore attachment warnings.

Technical reference: https://pymssql.readthedocs.io/en/latest/ref/pymssql.html documents the process-wide effect of pymssql timeout settings.

## Relevant prior commit

Commit: `a66d053feb106a3f41b08d22bc44ec785fde7686`
Author: Mohamed Fawzy
Date: 2026-10-29
Original commit subject: `ab_website_sale_product/FIX: restore E-Plus stock refresh on store`

- Switched both stock queries to the default pymssql backend. This correction scopes the ODBC change to branch stock; aggregate stock keeps its existing backend.

Files changed:

- `ab_website_sale_product/models/eplus_stock_snapshot.py`
- `ab_website_sale_product/changelog.d/current.md`
