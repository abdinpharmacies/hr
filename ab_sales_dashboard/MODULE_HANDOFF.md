# ab_sales_dashboard Module Handoff

## Purpose

`ab_sales_dashboard` is an Odoo 19 management reporting module for sales data
read from E-Plus / B-Connect. It lets management review sales performance inside
Odoo while treating E-Plus as the external read-only source of legacy sales,
collection, invoice, employee, product, and branch facts.

The module is reporting-focused. It must not write to E-Plus, change stock, or
replace Odoo business logic.

## Main User Experience

- A backend OWL client action registered with tag
  `ab_sales_dashboard.dashboard`.
- A top filter bar for store/branch and date range selection.
- A `Refresh from E-Plus` button for bounded source refreshes.
- KPI cards for sales, invoice count, units sold, unique products, product
  sales, average product metrics, stores with sales, and bearing percentage.
- Report sections for medicine vs non-medicine, collection methods, sales by
  users, top sold items, and customer/invoice sales.
- Stored-summary behavior for longer ranges when full E-Plus refresh is not
  allowed.

Frontend files:

- `static/src/js/sales_dashboard_action.js`
- `static/src/scss/sales_dashboard.scss`

## Current Data Flow

```text
Dashboard open
  -> ab.sales.dashboard.snapshot.get_dashboard_data(filters)
  -> latest matching Odoo snapshot or synchronized daily facts
  -> OWL dashboard payload

Refresh from E-Plus
  -> ab.sales.dashboard.snapshot.refresh_dashboard_data(filters)
  -> ab.sales.dashboard.service.fetch_refresh_data(...)
  -> read-only aggregated SQL Server queries
  -> Odoo snapshot, daily facts, coverage rows, telemetry
  -> OWL dashboard payload
```

## Main Models

- `ab.sales.dashboard.snapshot`: saved dashboard report header and serialized
  dashboard payload source.
- `ab.sales.dashboard.collection.line`: collection-method rows attached to a
  snapshot.
- `ab.sales.dashboard.user.line`: employee/user sales rows attached to a
  snapshot.
- `ab.sales.dashboard.item.line`: top item rows attached to a snapshot.
- `ab.sales.dashboard.invoice.line`: recent/customer invoice rows attached to a
  snapshot.
- `ab.sales.dashboard.daily.store.fact`: daily store-level aggregate facts used
  for longer summary ranges.
- `ab.sales.dashboard.daily.collection.fact`: daily collection-category facts.
- `ab.sales.dashboard.daily.item.fact`: daily item/product facts.
- `ab.sales.dashboard.sync.coverage`: daily synchronization coverage by store
  and fact type.
- `ab.sales.dashboard.fact.coverage`: coverage state used by reporting and
  reconciliation.
- `ab.sales.dashboard.product.sales.report`: SQL-backed/reporting model for
  product sales analysis.
- `ab.sales.dashboard.report.archive`: archived dashboard report history.
- `ab.sales.dashboard.reconciliation.job`: manager-triggered coverage analysis
  and reconciliation job.
- `ab.sales.dashboard.reconciliation.chunk`: bounded reconciliation work chunks.
- `ab.sales.dashboard.report.telemetry`: performance and usage telemetry.
- `ab.sales.dashboard.fact.decision`: transient helper for fact-grain decisions.
- `ab.sales.dashboard.service`: abstract E-Plus/B-Connect query service.
- `ab.sales.dashboard.config.mixin`: shared configuration limits.

## Menus

Root menu: `Sales Dashboard`

User-visible:

- `Dashboard`

Manager-visible:

- `Reports`
- `Archived Sales Reports`
- `Reconciliation Jobs`
- `Product Sales Report`
- `Reporting Analytics`
- `Fact-Grain Decision`
- `Report Data`
- `Daily Store Facts`
- `Daily Collection Facts`
- `Daily Item Facts`

## Security

Groups are defined in `security/security_groups.xml`:

- `ab_sales_dashboard.group_ab_sales_dashboard_user`
- `ab_sales_dashboard.group_ab_sales_dashboard_manager`

The manager group implies the user group. `base.group_system` implies the
manager group, so system administrators inherit dashboard manager access.

ACL behavior:

- Dashboard users can read normal dashboard reports, child report lines, daily
  facts, and coverage rows.
- Dashboard managers can create/update/delete snapshots and child lines, manage
  daily facts and coverage rows, run reconciliation, access archives, telemetry,
  product reports, and the fact decision wizard.
- Some manager operational/fact models intentionally do not grant unlink access
  to preserve reporting history.

Record rules currently use broad domains like `[(1, '=', 1)]`; there is no
branch-level row restriction in this module yet. Store/branch filtering is
handled by report filters and server-side query scope, not by record rules.

## E-Plus / B-Connect Rules

- E-Plus is read-only for this module.
- Refreshes must be date-bounded.
- Long source refreshes are blocked; long-range dashboard reads use stored daily
  facts when available.
- Queries should aggregate in SQL Server and return small result sets.
- Do not load raw sales lines into Python for dashboard rendering.
- Store filters must be applied server-side before querying E-Plus.
- Confirm source columns against metadata before adding new query fields.

Known column corrections already handled:

- Employee name uses `e_Name`; do not use `e_name_ar`.
- Product medicine flag is `itm_ismedicine`.
- Product plain name columns are not assumed reliable.

## Configuration Direction

The module uses config parameters through `ab.sales.dashboard.config.mixin` for
limits such as dashboard maximum refresh days, summary range, reconciliation
branch-days, chunk size, and top-row limits.

## Tests

Tests live in `tests/test_sales_dashboard.py`. They cover filter normalization,
dashboard data flow, report limits, refresh behavior, daily facts, coverage, and
reconciliation-related behavior.

Run targeted tests with:

```bash
/opt/odoo19/venv19/bin/python /opt/odoo19/server/odoo-bin \
  -c /opt/odoo19/odoo19.conf \
  -d abdin_replica19 \
  -u ab_sales_dashboard \
  --test-enable \
  --test-tags /ab_sales_dashboard \
  --stop-after-init
```

## Current Frontend Note

The store/branch filter is a custom OWL search dropdown, not a native HTML
select. Selecting `All Stores` or pressing the clear button resets
`filters.store_id` to `0` and reloads the dashboard.

## Recommended Next Work

- Add explicit branch/security row restrictions if branch-level report privacy is
  required.
- Add frontend tests or tours for the custom store/date filter controls.
- Keep expanding daily fact coverage instead of making long E-Plus refreshes.
- Keep `README.md` and `docs/PERFORMANCE_ARCHITECTURE.md` as the deeper
  architecture references.
