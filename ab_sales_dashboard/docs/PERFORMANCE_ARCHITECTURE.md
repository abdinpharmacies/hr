# Sales Dashboard Performance Architecture

## Production Constraint

No dashboard refresh, report sync, export, cron, or worker task should approach
1.5 GB RAM. The module must avoid unbounded report ranges, unbounded Python
lists, and concurrent heavy B-Connect calculations.

## Current Phase 1 Architecture

Phase 1 kept the existing synchronous dashboard behavior:

```text
OWL dashboard
  -> ab.sales.dashboard.snapshot.refresh_dashboard_data()
  -> ab.sales.dashboard.service.fetch_dashboard_data()
  -> ab.sales.dashboard.service.fetch_daily_store_facts()
  -> Odoo daily facts + dashboard report snapshot
```

Phase 1 intentionally did not remove duplicate B-Connect scans.

## Phase 2 Dashboard Query Architecture

Before Phase 2, each dashboard section prepended `_invoice_base_cte()` to its
own SQL statement:

```text
totals query           -> invoice CTE
collection query       -> invoice CTE
contract query         -> invoice CTE
medicine query         -> invoice CTE
sales by user query    -> invoice CTE
top items query        -> invoice CTE
recent invoices query  -> invoice CTE
```

SQL Server CTEs are statement scoped, so the filtered invoice base was rebuilt
for every section.

Phase 2 changed `fetch_dashboard_data()` only:

```text
fetch_dashboard_data()
  -> one ab_eplus_connect pooled MSSQL connection/session
  -> one cursor
  -> drop stale #invoice_base if present
  -> create #invoice_base once
  -> create one temp-table join index
  -> dashboard section queries read #invoice_base
  -> previous-period KPI uses one separate bounded aggregate query
  -> drop #invoice_base
  -> close cursor
  -> return the same dashboard payload shape
```

## Phase 3 Shared Refresh Source

Phase 3 changes the heavy refresh source path so snapshot refresh no longer
calls `fetch_dashboard_data()` and `fetch_daily_store_facts()` independently.
The public RPC behavior remains unchanged.

```text
refresh_dashboard_data
        |
        v
fetch_refresh_data
        |
        v
one MSSQL session
        |
        v
#invoice_base
     /       \
dashboard   daily facts
     \       /
      aggregated data
             |
             v
      snapshot persistence
```

`fetch_refresh_data(date_from, date_to, store_eplus_ids)` is an internal
wrapper used by `_create_snapshot()`. It returns:

```python
{
    "dashboard": {...},          # existing dashboard payload shape
    "daily_store_facts": {
        "store_facts": [...],
        "collection_facts": [...],
    },
}
```

The wrapper is not exposed to the frontend. Existing standalone service methods
are preserved:

- `fetch_dashboard_data()` still returns the dashboard payload directly.
- `fetch_daily_store_facts()` still returns the daily fact payload directly.

Both standalone methods now use the same `#invoice_base` session pattern when
called explicitly.

## Phase 3 Daily Fact SQL

Daily store totals and collection facts now aggregate from the shared
`#invoice_base`:

```text
#invoice_base
  -> GROUP BY report_date, sto_id
  -> GROUP BY report_date, sto_id, collection_category
```

Daily medicine/non-medicine facts still require sales detail rows, but they are
filtered by joining `r_sales_trans_d` to the same shared `#invoice_base`:

```text
r_sales_trans_d
  JOIN #invoice_base ON sth_id + store
  GROUP BY report_date, sto_id, medicine flag
```

Only grouped daily/store/category rows are returned to Python. Raw invoices and
sales lines are never loaded into Python.

## Daily Fact Cardinality Guard

Phase 3 adds a daily fact safety limit:

- Config key: `ab_reports.max_daily_fact_rows`
- Default: `10000`
- Minimum accepted value: `1`
- Maximum accepted value: `50000`

The service rejects oversized daily fact payloads. Snapshot persistence also
checks the actual sparse aggregate row count before persistence. Oversized
scopes raise a user-facing error; the module never silently truncates daily
reporting data.

## Phase 4 Bounded SQL Optimizations

Phase 4 keeps the Phase 3 shared MSSQL session and does not change the
dashboard UI, RPC methods, payload keys, date semantics, or snapshot behavior.
It reduces expensive source work inside the same session:

```text
one MSSQL session
  -> #invoice_base
  -> #daily_item_type_fact
  -> dashboard aggregates
  -> daily aggregates
  -> #top_items
  -> bounded stock aggregation
  -> #recent_headers
  -> bounded invoice detail aggregation
```

### Shared Medicine Aggregate

Before Phase 4, medicine/non-medicine sales were calculated twice from
`r_sales_trans_d`:

- dashboard medicine split
- daily store medicine facts

Phase 4 creates one temporary aggregate:

```text
#daily_item_type_fact
  grain: report_date, sto_id, item_type
  source: r_sales_trans_d JOIN #invoice_base JOIN item_catalog
```

The dashboard medicine split is now `SUM(sales_amount) GROUP BY item_type`
from this temp table. Daily medicine facts read the same temp table directly.
No raw sales detail rows are returned to Python.

No index is created on `#daily_item_type_fact` initially. Its expected
cardinality is bounded by days x selected stores x 2 item types, so an index
would add tempdb work without clear evidence yet.

### Bounded Recent Invoices

Before Phase 4, the recent invoice query grouped all invoices in the selected
period and applied `STRING_AGG` before `TOP (20)` was useful.

Phase 4 first materializes:

```text
#recent_headers
  TOP (20) from #invoice_base
  ordered by sec_insert_date desc, sth_id desc, sto_id desc
  includes sth_id + sto_id composite identity
```

The item-count and item-summary aggregation then joins details only for those
20 headers. This preserves the current payload shape while avoiding full-period
item summary aggregation.

Recent invoice customer display uses confirmed B-Connect customer sources in
this order: `sales_deliv_info.contact`, `Customer_Delivery.cd_contact_person`,
non-placeholder `Customer.cust_name_ar`, `Customer_Delivery.cd_tel`, then a
controlled cash-customer fallback for `cust_id = 0`. This avoids displaying raw
`0` customer IDs or `spare...` placeholder customer names when the invoice has
a better captured customer snapshot.

Recent invoice item summaries return bounded item identity pairs from
B-Connect and resolve display names from Odoo `ab_product` by `eplus_serial`.
This avoids relying on plain E-Plus item name columns, which may be empty or
encrypted. If an item is not mapped in Odoo, the summary falls back to the
E-Plus item code.

`STRING_AGG(CONVERT(NVARCHAR(MAX), ...))` is retained to avoid silent
truncation of invoice item summaries. The aggregation is now bounded to at
most the selected recent invoice headers.

### Bounded Top Items and Stock

Before Phase 4, top items used a correlated `OUTER APPLY` to calculate
`Item_Class_Store` balance while broadly grouping sales details.

Phase 4 splits this into:

```text
Stage A:
  #top_items
    TOP (20) sold item aggregate
    source: r_sales_trans_d JOIN #invoice_base JOIN item_catalog

Stage B:
  stock_balance
    source: Item_Class_Store JOIN #top_items
    grouped by itm_id
```

The final result joins stock balance to `#top_items` and preserves the current
ordering and payload shape. Store filtering remains parameterized:

- selected stores: `ics.sto_id IN (?, ...)`
- all-store dashboard: no stock store filter, matching the previous behavior

### Temp Table Cleanup

Phase 4 cleanup covers all temp objects:

- `#top_items`
- `#recent_headers`
- `#daily_item_type_fact`
- `#invoice_base`

Cleanup is attempted before creation and in `finally`. Cleanup failure is
logged separately and does not replace the original query/source exception.

### Timing Instrumentation

Phase 4 adds structured timing for:

- item type fact creation
- top-items source and final fetch
- recent-header source and final fetch
- dashboard normalization
- daily fact merge
- MSSQL cleanup
- sync coverage build
- bounded scope delete
- daily fact batch persistence
- sync coverage persistence
- snapshot parent persistence
- snapshot child command/persistence work
- dashboard serialization
- daily-fact fallback dashboard reads

The logs intentionally avoid full SQL text, credentials, connection strings,
customer detail payloads, and dashboard payload dumps.

## Phase 5 Sparse Daily Fact Persistence

Phase 5 keeps the Phase 3/4 MSSQL query architecture intact. It optimizes only
Odoo/PostgreSQL persistence for daily reporting facts.

Before Phase 5, snapshot refresh generated synthetic rows for every date,
store, and collection category. For a 31-day period and 200 stores this meant
approximately:

```text
daily store facts:          31 x 200      =  6,200
daily collection facts:     31 x 200 x 4  = 24,800
total generated fact rows:                    31,000
```

Most of those rows could be artificial zero values. They also required Python
maps, ORM recordsets for existing rows, and per-record writes.

After Phase 5:

```text
daily store facts:       actual source aggregate rows only
daily collection facts:  actual source aggregate rows only
sync coverage:           31 x 200 = about 6,200 rows
```

Coverage rows record that a date/store was successfully synchronized even when
no source facts were returned. Coverage grain is deliberately only:

```text
report_date + store_eplus_id
```

It is not category-specific.

### Sparse Fact Semantics

The persistence layer now stores only grouped rows returned by B-Connect:

- `ab.sales.dashboard.daily.store.fact`: `report_date + store_eplus_id`
- `ab.sales.dashboard.daily.collection.fact`:
  `report_date + store_eplus_id + category`
- `ab.sales.dashboard.sync.coverage`: `report_date + store_eplus_id`

Missing collection categories are interpreted as zero only when every
requested date/store has a `synced` coverage row. If coverage is incomplete,
the daily-fact fallback does not present the range as confirmed zero and falls
back to the existing safe snapshot behavior.

### Stale Fact Replacement

Sparse facts require stale-row handling. A successful refresh for a bounded
date/store scope now:

```text
DELETE existing daily store facts in scope
DELETE existing daily collection facts in scope
INSERT/UPSERT actual sparse source rows in bounded batches
UPSERT date/store sync coverage rows
```

Facts outside the requested date/store scope are preserved. The delete, insert,
coverage upsert, and snapshot persistence run inside the current Odoo
transaction. The code does not call `env.cr.commit()`. A failure rolls the whole
refresh back through normal Odoo transaction handling.

### PostgreSQL Batch Persistence

Daily reporting facts are persisted with parameterized `INSERT ... ON CONFLICT
... DO UPDATE` statements. Table and column identifiers come only from
hardcoded internal mappings. Fact values are passed as SQL parameters.

The code no longer loads existing daily fact rows into ORM recordsets for key
comparison and no longer performs a per-record `write()` loop for daily facts.
Direct SQL is acceptable here because the daily fact models are pure reporting
storage: they have no `create()`/`write()` overrides, no tracking, and no
business side effects.

### Coverage Limits

Coverage cardinality is separately bounded:

- Config key: `ab_reports.max_daily_coverage_rows`
- Default: `10000`
- Minimum accepted value: `1`
- Maximum accepted value: `50000`

This protects all-store ranges where coverage is `days x stores`.

## Phase 6 Snapshot Persistence Optimization

Phase 6 keeps the dashboard UI, payload contract, row key behavior, and
snapshot reuse semantics unchanged. It optimizes only PostgreSQL/Odoo
persistence for the bounded dashboard snapshot child rows.

### Snapshot Model Diagnostic

The snapshot parent model is:

```text
model: ab.sales.dashboard.snapshot
table: ab_sales_dashboard_snapshot
semantics: one parent reused per date_from + date_to + store_filter_key
```

The child models are bounded reporting rows:

```text
ab.sales.dashboard.collection.line -> ab_sales_dashboard_collection_line
  parent: snapshot_id
  ordering: total_sales desc, id
  logical row: collection category

ab.sales.dashboard.user.line -> ab_sales_dashboard_user_line
  parent: snapshot_id
  ordering: total_sales desc, id
  logical row: employee_eplus_id

ab.sales.dashboard.item.line -> ab_sales_dashboard_item_line
  parent: snapshot_id
  ordering: sale_times desc, sold_qty desc, id
  logical row: eplus_item_id

ab.sales.dashboard.invoice.line -> ab_sales_dashboard_invoice_line
  parent: snapshot_id
  ordering: invoice_date desc, id desc
  logical row: invoice_no payload row
```

These child models have no `create()`, `write()`, or `unlink()` overrides, no
`mail.thread`, no tracking, no computed/inverse fields, and no Python
constraints. They are pure readonly reporting storage, so direct SQL
replacement is safe when cache invalidation is handled explicitly.

The parent remains ORM-managed because it is one bounded record and owns the
`store_ids` many-to-many relation.

### Archive Semantics

The module currently reuses a snapshot parent for the same:

```text
date_from + date_to + store_filter_key
```

Refresh updates that parent and replaces its bounded child rows. Phase 6
preserves this behavior; it does not convert snapshots into immutable
append-only archives.

### Child Replacement Strategy

Before Phase 6, child persistence used one2many command lists:

```text
[(5, 0, 0)] + [(0, 0, values), ...]
```

After Phase 6:

```text
parent lookup/create/write through ORM
DELETE FROM child_table WHERE snapshot_id = %s
INSERT child rows in bounded parameterized batches
invalidate child models and parent one2many fields
serialize the same payload shape
```

The child table and column identifiers come only from hardcoded internal
mappings. Payload values are always SQL parameters. No manual commit is used;
parent persistence, child replacement, daily facts, and coverage all remain in
the current Odoo transaction.

### Snapshot Child Row Guard

Each child collection is protected by:

- Config key: `ab_reports.max_snapshot_child_rows`
- Default: `100`
- Minimum accepted value: `1`
- Maximum accepted value: `1000`

The guard fails safely with a user-facing error if a bounded child section
unexpectedly exceeds the configured limit. It does not truncate rows.

### Cache Invalidation and Serialization

Direct SQL bypasses ORM cache updates. After child replacement, Phase 6
invalidates:

- every affected child model cache
- the parent snapshot one2many fields:
  `collection_line_ids`, `user_line_ids`, `item_line_ids`, `invoice_line_ids`

Immediate `_serialize_dashboard()` in the same transaction sees the newly
inserted rows and not the deleted rows.

### Ordering Guarantees

Ordering remains model-defined:

- collection: `total_sales desc, id`
- users: `total_sales desc, id`
- items: `sale_times desc, sold_qty desc, id`
- invoices: `invoice_date desc, id desc`

No schema field was added because existing `_order` definitions already match
the dashboard behavior.

### Expected PostgreSQL Query Reduction

For the typical bounded snapshot payload:

```text
collection <= 4
users      <= 20
items      <= 20
invoices   <= 20
```

Phase 6 replaces ORM child unlink/create bookkeeping with:

```text
4 scoped DELETE statements
up to 4 bounded INSERT batches at the default batch size
1 cache invalidation pass
```

This reduces ORM object allocation, per-row create overhead, and one2many
command processing while keeping the data volume bounded.

## Phase 7 Current Cache vs Management Archive

Phase 7 separates two concepts that were previously easy to confuse:

```text
current dashboard snapshot
  mutable cache for one date/store filter scope

management report archive
  immutable reviewed report captured explicitly by a manager
```

### Current Snapshot Diagnostic

The existing snapshot model remains:

```text
model: ab.sales.dashboard.snapshot
table: ab_sales_dashboard_snapshot
lookup key: date_from + date_to + store_filter_key
behavior: reused and updated by refresh
purpose: current dashboard/report cache
```

Refresh still follows the same cache path:

```text
refresh_dashboard_data()
  -> advisory lock
  -> _create_snapshot()
  -> fetch_refresh_data()
  -> one MSSQL session and temp tables
  -> sparse daily facts and coverage
  -> _create_snapshot_from_payload()
  -> reusable parent snapshot
  -> bounded direct-SQL child replacement
  -> _serialize_dashboard()
```

Dashboard reads still use this fallback order:

```text
latest full current snapshot
  -> PostgreSQL daily-fact fallback when coverage is complete
  -> latest partial current snapshot
  -> empty safe payload
```

Archives are not part of dashboard fallback, refresh, daily fact fallback, or
snapshot child replacement.

### Immutable Management Archive

Phase 7 adds:

```text
model: ab.sales.dashboard.report.archive
table: ab_sales_dashboard_report_archive
purpose: explicit reviewed management report archive
```

An archive is created only by an explicit backend action from a current
snapshot. It is never created automatically by dashboard refresh and is never
silently replaced by a later refresh.

Creation flow:

```text
current snapshot
  -> _serialize_dashboard(snapshot, filters)
  -> deterministic JSON bytes
  -> payload size guard
  -> SHA-256 payload hash
  -> ir.sequence archive number
  -> immutable archive record
```

The archive stores the exact dashboard payload visible at archive time:

- payload keys are unchanged
- row key values are preserved
- child ordering is preserved
- payload values are stored in `fields.Json`

Opening an archive reads only `payload_json`. It does not query B-Connect, does
not call `fetch_refresh_data()`, does not use daily fact fallback, and does not
re-serialize the current snapshot.

### Immutability and Cancellation

Archive creation is controlled by server-side context from the archive action.
Direct `create()` calls are rejected. Once created, report data is immutable:

- payload cannot be changed
- dates cannot be changed
- store scope cannot be changed
- archive records cannot be deleted

The only allowed write is changing `state` to `cancelled`. Cancellation keeps
the archived payload intact and provides an audit-safe way to mark a report as
superseded or invalid.

### Hashing and Duplicate Policy

Archive payload hashes use deterministic JSON serialization:

```text
json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
SHA-256 over UTF-8 bytes
```

The hash is integrity metadata only. Duplicate hashes are allowed because a
manager may intentionally archive the same reviewed report more than once at
different review times. When a duplicate payload hash already exists, the
module logs only a safe hash prefix and count; it never logs the payload.

Archive numbers come from an `ir.sequence` with code:

```text
ab.sales.dashboard.report.archive
```

The configured prefix is:

```text
MGT-SALES/%(year)s/
```

The code never uses `MAX(id) + 1`.

### Payload Size Limit

Although dashboard payloads are bounded by TOP sections and child row guards,
archives have an additional hard size guard:

- Config key: `ab_reports.max_archive_payload_bytes`
- Default: `1048576` bytes
- Minimum accepted value: `1`
- Maximum accepted value: `10485760` bytes

The size is measured from the deterministic UTF-8 JSON bytes used for hashing.
Oversized payloads raise a user-facing error and are not truncated.

### Access Control

The archive model reuses the existing sales dashboard manager group:

```text
ab_sales_dashboard.group_ab_sales_dashboard_manager
```

Dashboard users keep the existing current dashboard permissions but do not get
archive creation rights. Managers can read archives and create them only
through the controlled archive action. Record rules do not weaken the current
dashboard access model.

### Transaction and Memory Safety

Archive creation runs in the existing Odoo transaction and does not call
`env.cr.commit()`. It stores one bounded JSON payload and metadata; it does not
copy raw invoices, raw sales lines, or B-Connect detail tables into Odoo.

Structured logs were added for:

- archive start
- serialization
- hashing
- duplicate payload detection
- creation
- failure
- stored-payload reads

The logs intentionally exclude full payloads, customer names, item names,
invoice summaries, SQL text, and credentials.

## Phase 8 Full vs Summary Reports

Phase 8 adds safe long-range reporting without increasing the B-Connect refresh
limit. The module now has two explicit report modes:

```text
full
summary
```

Mode and completeness are reported through the additive `report_meta` payload
key. Existing dashboard payload keys and row keys remain unchanged.

### Full Report Mode

A full report comes from the current B-Connect refresh path:

```text
refresh_dashboard_data
  -> advisory lock
  -> fetch_refresh_data
  -> one MSSQL session
  -> #invoice_base + bounded temp aggregates
  -> sparse daily facts + coverage
  -> reusable snapshot cache
```

Full refresh remains capped by:

```text
ab_reports.max_dashboard_days = 31
```

The limit is hard-capped at 31 days. Selecting a 90-day range cannot trigger a
90-day B-Connect scan.

### Summary Report Mode

A summary report is reconstructed only from PostgreSQL daily facts:

```text
get_dashboard_data
  -> validate against ab_reports.max_summary_days
  -> read sync coverage
  -> PostgreSQL SUM/GROUP BY over sparse daily facts
  -> payload + report_meta
```

Summary mode never calls `connect_eplus()` and never calls
`fetch_refresh_data()`. It does not require a saved snapshot with the same
date/store filter key; daily facts are reusable by branch and date range.

The summary range limit is separate from the refresh limit:

```text
ab_reports.max_summary_days = 90
minimum: 31
maximum: 365
```

### Summary Coverage

Coverage remains authoritative and uses the Phase 5 grain:

```text
report_date + store_eplus_id
```

For a requested scope:

```text
expected_store_days = requested_days * selected_store_count
covered_store_days = synced coverage rows in scope
```

Coverage states:

- `complete`: all requested branch-days are covered
- `partial`: some requested branch-days are covered
- `unavailable`: no requested branch-days are covered

Sparse fact absence means zero only when coverage exists. Missing coverage is
never fabricated as zero. Partial reports aggregate available covered facts and
expose the missing branch-days in `report_meta`.

Previous-period comparison also uses PostgreSQL facts only. If the previous
scope is not fully covered, the comparison is listed in
`report_meta.unavailable_comparisons` and no B-Connect query is made.

### Supported Summary Sections

Summary mode supports these sections from existing daily fact grains:

- total sales
- average daily sales
- invoice count
- previous-period average when previous coverage is complete
- sales by collection method
- medicine/non-medicine split
- contract/customer bearing using the corrected customer/company denominator

Unsupported summary sections remain payload-compatible empty lists and are
listed in `report_meta.unsupported_sections`:

- sales by user
- top sold items
- customer sales / recent invoices

The frontend displays a small status/banner for fully refreshed, stored
summary, partial summary, and unavailable states. Unsupported detail sections
show a neutral "not available for summary range" note instead of implying zero
sales.

### Last 90 Days Flow

The `Last 90 Days` filter calls `get_dashboard_data()`. The Refresh from
E-Plus button is disabled for ranges over 31 days and displays that long-range
reports use synchronized daily facts. Phase 8 does not automatically split a
90-day request into multiple B-Connect refreshes.

### Snapshot and Archive Separation

Reusable snapshots remain the current full-dashboard cache. Daily facts are the
long-range summary reporting source. Phase 7 archives remain immutable reviewed
captures and are not used by summary reporting or refresh fallback.

### Production Fix Compatibility

Phase 8 preserves the targeted production fixes applied after Phase 7:

- runtime-safe `#invoice_base` creation before parameterized inserts
- corrected Customer Sales customer display and cash-customer fallback
- corrected Bearing Percentage denominator using customer and company shares
- Customer Sales item-name resolution from Odoo products by E-Plus serial
- medicine/non-medicine color markers
- offer classification from header-level and detail-line discounts

## Phase 9 Coverage Reconciliation

Phase 9 adds an explicit manager-controlled maintenance workflow for filling
missing daily fact coverage. It is not part of the dashboard read path.

```text
Reconciliation Job
  -> analyze PostgreSQL sync coverage only
  -> plan bounded missing branch-day chunks
  -> run chunks explicitly
  -> fetch daily facts only from B-Connect
  -> sparse fact replacement + coverage upsert
```

Opening a 90-day dashboard still uses only PostgreSQL daily facts. It never
starts reconciliation and never scans B-Connect implicitly.

### Coverage Analysis

Coverage analysis compares the requested branch/date scope against
`ab_sales_dashboard_sync_coverage` using PostgreSQL only. The authoritative
grain remains:

```text
report_date + store_eplus_id
```

Only rows with `sync_state = 'synced'` count as covered. Fact row existence is
not used as proof of coverage because a covered branch-day may legitimately
have zero sales and therefore no sparse fact rows.

Missing branch-days are calculated with a bounded SQL set:

```text
generate_series(date_from, date_to)
  CROSS JOIN selected E-Plus stores
  LEFT JOIN sync coverage
```

The result is guarded by:

```text
ab_reports.max_reconciliation_branch_days
default: 10000
maximum: 50000
```

The module fails safely instead of truncating a requested reconciliation scope.

### Chunk Planning

The planner groups missing branch-days by date and identical missing store
sets. Contiguous dates with the same store set are merged until the chunk
reaches the normal B-Connect source limit:

```text
max chunk date span = ab_reports.max_dashboard_days = 31
```

This avoids one query per branch-day while still preventing a 90-day source
scan. The algorithm is deterministic and intentionally conservative; it is not
an expensive global optimizer.

Chunk count is guarded by:

```text
ab_reports.max_reconciliation_chunks
default: 500
maximum: 5000
```

### Fact-Only MSSQL Path

Reconciliation chunks call a fact-only source method:

```text
fetch_daily_fact_data(date_from, date_to_exclusive, store_eplus_ids)
```

It reuses the optimized Phase 3/4 temp-table lifecycle and one MSSQL
connection/cursor per chunk, but it fetches only daily store and collection
facts. It does not execute dashboard-only sections such as sales by user, top
items, or recent invoices, and it does not create dashboard snapshots or
archives.

### Persistence and Transaction Semantics

Each successful chunk reuses the Phase 5 sparse persistence path:

```text
DELETE facts inside chunk scope
INSERT/UPSERT actual sparse facts in bounded batches
UPSERT sync coverage for each date/store in scope
```

Facts outside the chunk scope are preserved. Coverage is persisted only as
part of the same PostgreSQL transaction path as facts. There is no manual
`env.cr.commit()`.

Chunk execution uses PostgreSQL savepoints so one failed chunk can be marked
failed without discarding successful independent chunks in the same explicit
job action.

### Retry and Source Concurrency

Retry processes only `failed` or `pending` chunks. Before using B-Connect, a
chunk re-checks sync coverage; if another operation already covered the scope,
the chunk is marked done without source work.

The workflow reuses the existing sales dashboard heavy-source advisory lock.
This keeps default heavy B-Connect reporting concurrency at one operation
across dashboard refreshes and reconciliation chunks.

### Management UI and Access

Phase 9 adds standard backend list/form/search views for:

```text
ab.sales.dashboard.reconciliation.job
ab.sales.dashboard.reconciliation.chunk
```

Only `ab_sales_dashboard.group_ab_sales_dashboard_manager` can create and run
reconciliation jobs. Normal dashboard users can still read the dashboard but
cannot start maintenance backfills.

### Memory Safety

Reconciliation stores no raw B-Connect rows, invoice lines, dashboard payload
JSON, or XLSX/export data. Python receives only bounded grouped daily fact
rows, and all source chunks remain capped at 31 days.

## SQL Server Temp Table Scope

`#invoice_base` is SQL Server session scoped. It must be created and consumed on
the same MSSQL session. The shared `ab_eplus_connect.connect_eplus()` helper
returns a pooled `ConnectionProxy` and intentionally does not close the
underlying connection in its `finally` block. The dashboard service therefore
owns only:

- the cursor created for this dashboard operation
- the `#invoice_base` lifecycle

It does not close the pooled connection directly.

The connector can reconnect a `ReconnectingCursor` after disconnect-like
errors. If that happens after `#invoice_base` is created, the SQL Server temp
table would be lost. Phase 2 logs and propagates the failure; it does not add a
custom reconnect strategy inside the dashboard session.

## `#invoice_base` Schema

The primary temporary table stores only fields needed by dashboard section
queries:

- `sth_id`
- `sto_id`
- `cust_id`
- `emp_id`
- `sec_insert_date`
- `report_date`
- `net_amount`
- `company_part`
- `is_delivery`
- `is_contract`
- `is_offer`
- `collection_category`

The table is created with explicit `CREATE TABLE #invoice_base` and then
populated with a parameterized `INSERT INTO #invoice_base ... SELECT ...`.
This avoids a SQL Server/pyodbc prepared-statement scope problem where a local
temp table created by a parameterized `SELECT ... INTO #invoice_base` may not
exist for the next statement in the same dashboard workflow. Values remain
parameterized; only the temp-table DDL is non-parameterized and contains no
user input.

Filtering remains parameterized and preserves the current semantics:

```text
h.sec_insert_date >= date_from
h.sec_insert_date < date_to
h.sth_flag = 'C'
optional h.sto_id IN (?, ?, ...)
```

## Temporary Index

Phase 2 creates one temporary clustered index:

```sql
CREATE CLUSTERED INDEX IX_invoice_base_sth_store
ON #invoice_base(sth_id, sto_id)
```

This index supports repeated joins from `r_sales_trans_d` to `#invoice_base`:

```text
d.sth_id = h.sth_id
d.std_stock_id = h.sto_id
```

No employee, collection, item-type, recent-header, or top-items index is added
yet. Those temp sets are either already bounded or grouped directly, and extra
indexes would add tempdb/CPU cost without measured evidence.

## Contract Bearing Semantics

For Odoo-originated contract invoices, `total_bill_net` is the customer-paid
share and `fh_company_part` is the company/insurance share. The dashboard
therefore calculates:

```text
customer_bearing_amount = SUM(net_amount)
company_part_amount = SUM(company_part)
bearing_pct = customer_bearing_amount / (customer_bearing_amount + company_part_amount)
```

The older `net_amount - company_part` formula is not valid for this module's
contract push flow and can produce false negative percentages when the company
share exceeds the customer share.

## Collection Category Semantics

The dashboard has four bounded collection categories: `cash`, `delivery`,
`contract`, and `offer`. `offer` has priority over the other categories when an
invoice has either header-level discount fields or detail-line discounts:

```text
total_des_mon != 0
OR total_dis_per != 0
OR sth_pnt_dis != 0
OR any r_sales_trans_d.itm_dis_mon / itm_dis_per != 0
```

This captures product-level sales, coupons, and line-level discounts that do
not populate header discount fields. Collection payloads are normalized to
return all four categories; categories with no sales are returned as zero-value
cards.

## Remaining `fetchall()` Calls

`fetch_dashboard_data()` still uses `fetchall()` for dashboard section result
sets, but only for bounded aggregate outputs:

- totals: one row
- previous totals: one row
- contract bearing: one row
- collection categories: four expected categories
- medicine split: two expected categories from `#daily_item_type_fact`
- sales by user: `TOP (20)`
- top items: `TOP (20)`
- recent invoices: `TOP (20)`

The raw invoice base remains inside SQL Server and is never loaded into Python.

## Dashboard Date Range Limit

The server validates dashboard ranges before starting B-Connect work.

- Config key: `ab_reports.max_dashboard_days`
- Default: `31`
- Minimum accepted value: `1`
- Maximum accepted value: `31`

Dashboard UI dates are inclusive: `date_from <= report date <= date_to`.
Service methods that receive an exclusive upper boundary validate:
`date_from <= report date < date_to`.

## B-Connect Refresh Lock

Heavy dashboard refreshes use a transaction-scoped PostgreSQL advisory lock:

```text
pg_try_advisory_xact_lock(1907350131)
```

The lock protects only `refresh_dashboard_data()` and does not block normal
`get_dashboard_data()` reads. If another worker already holds the lock, the
refresh raises a user-facing error and does not start B-Connect queries.

## Query Timeout Behavior

- Config key: `ab_reports.query_timeout_seconds`
- Default: `120`
- Minimum accepted value: `1`
- Maximum accepted value: `300`

The service applies the timeout only when the active MSSQL cursor exposes a
native `timeout` attribute. Drivers/cursors without that attribute remain
backward compatible and are logged as timeout-unsupported.

The module does not implement a Python thread timeout.

## Batch Size Configuration

- Config key: `ab_reports.query_batch_size`
- Default: `1000`
- Minimum accepted value: `1`
- Maximum accepted value: `2000`

Phase 5 uses this value as the PostgreSQL daily-fact and sync-coverage
persistence batch size.

## Structured Logs

Phase 1 and Phase 2 add key/value style logs for:

- `sales_dashboard_refresh_started`
- `sales_dashboard_refresh_completed`
- `sales_dashboard_refresh_failed`
- `sales_dashboard_refresh_lock_busy`
- `sales_dashboard_service_started`
- `sales_dashboard_service_completed`
- `sales_dashboard_service_failed`
- `sales_dashboard_query_completed`
- `sales_dashboard_query_failed`
- `sales_dashboard_query_timeout_unsupported`
- `sales_dashboard_session_opened`
- `sales_dashboard_invoice_base_created`
- `sales_dashboard_invoice_base_dropped`
- `sales_dashboard_session_closed`
- `sales_dashboard_source_started`
- `sales_dashboard_temp_source_created`
- `sales_dashboard_sections_completed`
- `sales_dashboard_daily_facts_completed`
- `sales_dashboard_source_completed`
- `sales_dashboard_source_failed`
- `sales_dashboard_coverage_build_completed`
- `sales_dashboard_scope_delete_completed`
- `sales_dashboard_fact_batch_completed`
- `sales_dashboard_fact_persistence_completed`
- `sales_dashboard_coverage_persistence_completed`
- `sales_dashboard_snapshot_parent_persistence_started`
- `sales_dashboard_snapshot_parent_persistence_completed`
- `sales_dashboard_snapshot_child_delete_completed`
- `sales_dashboard_snapshot_child_batch_completed`
- `sales_dashboard_snapshot_child_persistence_completed`
- `sales_dashboard_snapshot_cache_invalidation_completed`
- `sales_dashboard_serialization_started`
- `sales_dashboard_report_mode_selected`
- `sales_dashboard_summary_started`
- `sales_dashboard_summary_coverage_completed`
- `sales_dashboard_summary_query_completed`
- `sales_dashboard_summary_normalization_completed`
- `sales_dashboard_summary_completed`
- `sales_dashboard_summary_partial`
- `sales_dashboard_summary_unavailable`
- `sales_dashboard_long_refresh_rejected`
- `sales_dashboard_daily_item_fact_completed`
- `sales_dashboard_summary_product_aggregation_completed`
- `sales_dashboard_summary_top_items_completed`
- `sales_dashboard_item_coverage_analysis_completed`
- `sales_dashboard_item_coverage_persistence_completed`
- `sales_dashboard_reconciliation_analysis_started`
- `sales_dashboard_reconciliation_analysis_completed`
- `sales_dashboard_reconciliation_plan_completed`
- `sales_dashboard_reconciliation_chunk_started`
- `sales_dashboard_reconciliation_chunk_source_completed`
- `sales_dashboard_reconciliation_chunk_persistence_completed`
- `sales_dashboard_reconciliation_chunk_completed`
- `sales_dashboard_reconciliation_chunk_failed`

Logs include date range, store count, operation name, duration, and row count
where safe. Logs do not include SQL credentials or full SQL payloads.

## Phase 9 Reconciliation

Reconciliation is explicit administrative maintenance. It is not part of the
dashboard read path and is never started by selecting Last 90 Days.

The reconciliation job model analyzes coverage using PostgreSQL only. Missing
coverage is calculated from requested dates and selected E-Plus stores with
`generate_series(...)`, joined against the coverage table. No B-Connect
connection is opened during analysis.

Chunk planning groups contiguous missing branch-days with the same store set.
Every source chunk is capped by `ab_reports.max_dashboard_days`, currently
hard-limited to 31 days. The workflow uses the same PostgreSQL advisory lock as
dashboard refreshes, preserving the default one-heavy-source-task-at-a-time
behavior.

Each chunk uses the fact-only service path:

```text
one MSSQL session
  -> #invoice_base
  -> #daily_item_fact
  -> #daily_item_type_fact
  -> grouped daily facts only
  -> sparse PostgreSQL replacement
  -> coverage persistence
```

Chunks do not create dashboard snapshots, do not create archives, and do not
run dashboard-only queries such as sales by user, recent invoices, or customer
sales. Retry re-checks coverage first; already covered chunks are marked done
without opening B-Connect.

## Phase 10 Sparse Daily Item Facts

Phase 10 adds sparse item-level facts for product KPIs, long-range Top 20
products, and a paginated backend product sales report.

Daily item fact grain:

```text
report_date
+ store_eplus_id
+ item_eplus_id
```

The fact table stores only actual sales activity:

- `report_date`
- `store_id`
- `store_eplus_id`
- `item_eplus_id`
- `item_code`
- `product_id`
- `item_name`
- `item_type`
- `sold_qty`
- `sales_amount`
- `invoice_count`
- `sale_times`
- `synced_at`

No `date x store x product` zero rows are generated.

## Item Coverage

Legacy `ab.sales.dashboard.sync.coverage` continues to prove store/collection
daily summary coverage. It does not prove item fact completeness.

Phase 10 adds `ab.sales.dashboard.fact.coverage` with grain:

```text
report_date
+ store_eplus_id
+ fact_type
```

Supported fact types are `store`, `collection`, and `item`. Current item
summary behavior accepts item data only when:

```text
fact_type = 'item'
AND sync_state = 'synced'
```

Existing sync coverage alone is intentionally insufficient for product KPIs and
long-range Top 20 products. This prevents old covered days from being treated
as item-complete before item facts are backfilled.

## MSSQL Item Aggregate

The shared MSSQL source session creates `#daily_item_fact` once:

```text
r_sales_trans_d
  JOIN #invoice_base
  JOIN item_catalog
  GROUP BY report_date, sto_id, itm_id
```

This aggregate is then reused for:

- product KPI calculations
- dashboard Top Sold Items ranking
- daily item fact persistence
- medicine/non-medicine daily item-type aggregation

Top Sold Items remains a bounded Top 20 dashboard section. Current balance is
queried only for those Top 20 item IDs through `Item_Class_Store`, not for all
sold products.

## Product KPI Formulas

Product KPI fields are additive dashboard payload fields:

- `total_units_sold`: `SUM(sold_qty)`
- `unique_products_sold`: `COUNT(DISTINCT item_eplus_id)`
- `total_product_sales`: `SUM(sales_amount)`
- `avg_products_per_invoice`: item/invoice occurrences divided by invoice count
- `stores_with_sales`: `COUNT(DISTINCT store_eplus_id)` with item sales
- `avg_products_sold_per_store`: average distinct sold products per selling store

These are never calculated from the Top 20 presentation ranking.

## Long-Range Product Summary

For ranges over 31 days, product KPIs and Top 20 products are calculated only
from PostgreSQL daily item facts. B-Connect is not queried. If item coverage is
complete, summary mode removes `top_items` from unsupported sections and
returns a PostgreSQL-derived Top 20. If item coverage is partial or unavailable,
product rankings are not fabricated from incomplete data and `top_items`
remains unsupported.

## Product Sales Report

The backend Product Sales Report is a SQL-backed Odoo model over daily item
facts. It supports standard Odoo server-side filtering, grouping, pagination,
pivot, and graph views without sending thousands of products to the OWL
dashboard. It intentionally omits live current balance because a live B-Connect
lookup per report row would be unbounded; current balance remains limited to
the dashboard Top 20.

## Phase 10 Guards

- Config key: `ab_reports.max_daily_item_fact_rows`
- Default: `750000`
- Minimum accepted value: `1`
- Maximum accepted value: `1000000`

Oversized item fact payloads are rejected before persistence. Item coverage is
recorded only after item fact persistence succeeds in the same PostgreSQL
transaction.

## Known Remaining Limitations

Phase 10 still does not solve:

- employee and customer detail fact grains for long-range summaries
- fully incremental source synchronization or scheduled reconciliation
- automatic remediation when previous-period comparison coverage is incomplete
- live current balance for paginated product report rows

## Next Phases

Phase 11 should focus on scheduled or operator-assisted reconciliation policy:
when to backfill item coverage, how to reconcile late-arriving E-Plus rows, and
how to expose safe progress without tying it to normal dashboard reads.

## Security Finding Outside This Module

`ab_eplus_connect/models/ab_eplus_connect.py` currently appears to log encrypted
password and decryption key information in `decrypt_password()`. This task does
not modify `ab_eplus_connect`; the issue requires separate approval because the
connector is shared by other modules.

## Phase 12 Reporting Demand Telemetry

Phase 12 intentionally does not add employee or customer daily facts. It first
measures whether long-range users actually need those grains often enough to
justify their storage, synchronization, coverage, and reconciliation cost.

The `ab.sales.dashboard.report.telemetry` model stores one row per dedicated
top-level operation. It never stores report payloads, request/filter JSON, SQL,
search text, credentials, store-ID arrays, or customer, employee, product, and
invoice identifiers or names. The stored shape is limited to event and report
mode, deterministic range and store-scope buckets, coverage state, bounded
integer timing/size/count metadata, source-use flags, and section
available/unsupported booleans.

Dedicated operations currently measured are:

- dashboard reads
- dashboard refreshes
- summary reads
- archived report reads
- bounded reconciliation runs

The Product Sales Report remains a standard Odoo SQL-view action. Generic
`search_read`, `read_group`, or web model calls are not overridden merely to
measure this view because doing so would be fragile, could affect unrelated
models, and would not reliably represent one user operation. Its exact demand
is therefore a known telemetry limitation. Dashboard and long-range summary
demand are the decision gate's primary evidence.

Telemetry writes use the surrounding Odoo transaction and never commit
manually. A telemetry persistence failure is caught and logged as
`sales_dashboard_telemetry_write_failed`; it cannot replace the report result
or original report/source error. If the surrounding transaction rolls back,
its telemetry row may roll back as well. No separate connection is introduced
to evade that transaction behavior.

### Buckets and Section Demand

Range buckets are deterministic:

- `1_7_days`
- `8_31_days`
- `32_60_days`
- `61_90_days`

Store scope buckets are `single_store`, `2_10_stores`, `11_50_stores`,
`51_100_stores`, `over_100_stores`, and `all_stores`. `all_stores` is derived
from the dashboard's existing zero/empty store filter semantics; selected IDs
are not persisted.

Summary unsupported flags are derived from the returned `report_meta` rather
than assumptions. `top_items` is available when item coverage is complete and
unsupported when item coverage is partial or unavailable. Employee and
customer gaps map from `sales_by_user` and `customer_sales` respectively.

Result size is measured from deterministic compact JSON bytes and discarded;
only `result_size_bytes` is stored. Wall-clock duration is recorded only for
the top-level operation. Existing detailed timing logs remain the source for
internal stage diagnosis.

### Retention

Telemetry retention uses:

- `ab_reports.telemetry_retention_days`: default 90, bounds 1..365
- `ab_reports.telemetry_cleanup_batch_size`: default 5000, bounds 1..20000

The daily cleanup cron performs one bounded PostgreSQL `DELETE` batch ordered
by event date and ID. It does not ORM-load old telemetry and leaves further
rows for the next cron execution. The same maintenance pass checks PostgreSQL's
bounded `pg_class.reltuples` estimate for the daily item fact warning; the
manager fact-volume analysis uses an exact aggregate count.

### Analytics and Fact Volume

Managers receive standard list, pivot, graph, and search views under
Sales Dashboard > Reporting Analytics. Dimensions include event date/type,
report mode, range bucket, store-scope bucket, and coverage state. Measures
include operation count, average and maximum duration, average result size, and
requested days.

`get_fact_volume_analysis()` uses aggregate PostgreSQL SQL only. It returns
counts and date boundaries for daily store, collection, and item facts;
distinct item/store counts for item facts; coverage counts by fact type;
snapshot child counts; archive payload size aggregates; and telemetry count
and date boundaries. It never loads fact rows into Python.

### Warning Thresholds

Warnings are observational and never reject an otherwise valid report:

- `ab_reports.warn_dashboard_duration_ms`: default 5000
- `ab_reports.warn_summary_duration_ms`: default 5000
- `ab_reports.warn_refresh_duration_ms`: default 120000
- `ab_reports.warn_payload_size_bytes`: default 524288
- `ab_reports.warn_daily_item_fact_rows`: default 250000

Threshold crossings emit bounded structured events:
`sales_dashboard_slow_operation`, `sales_dashboard_large_payload`, and
`sales_dashboard_fact_volume_warning`. Existing hard range/cardinality guards
remain separate and unchanged.

### Fact-Grain Decision Gate

`get_fact_grain_recommendation()` aggregates long-range summary telemetry in
PostgreSQL. Its demand threshold is configured by
`ab_reports.fact_demand_threshold_percentage` (default 30, bounds 1..100).
The deterministic result is:

- employee gap at/above threshold only: `employee`
- customer gap at/above threshold only: `customer`
- both at/above threshold, employee equal/higher: `both_employee_first`
- both at/above threshold, customer higher: `both_customer_first`
- neither at/above threshold: `neither`

Item gap and item coverage completeness are reported separately. The decision
never recommends another item fact table because daily item facts already
exist. The manager-only Fact-Grain Decision form presents the measurement
period, operation and gap counts, percentages, performance averages, and the
recommendation without creating any new fact model or starting another phase.

### PostgreSQL Index Decisions

Existing daily fact uniqueness constraints provide leading date keys for the
bounded date-range aggregates and prevent duplicate grains:

- daily store: `(report_date, store_eplus_id)`
- daily collection: `(report_date, store_eplus_id, category)`
- daily item: `(report_date, store_eplus_id, item_eplus_id)`
- sync coverage: `(report_date, store_eplus_id)`
- fact coverage: `(report_date, store_eplus_id, fact_type)`

Existing field indexes on date, store, item, category, fact type, and product
support the 90-day summary, Top 20, Product Sales Report, and coverage filters.
No extra daily-item index was added because the current unique index plus
single-column indexes cover the measured patterns, while another wide index
would amplify high-volume fact writes. Telemetry adds indexes on its bounded
analysis dimensions and unsupported flags; retention is led by `event_date`,
and the recommendation query is led by indexed `report_mode`. Index usage must
be revisited with production `EXPLAIN (ANALYZE, BUFFERS)` evidence after the
90-day measurement window.

## Recommended Phase 13 Gate

Run Phase 12 for a complete 90-day retention window, review the manager
decision report and PostgreSQL plans, then implement only the recommended
employee/customer grain. Phase 13 should define that grain's sparse schema,
coverage proof, bounded B-Connect aggregate, reconciliation extension,
retention impact, and migration/backfill plan. If the result is `neither`,
Phase 13 should remain a performance tuning and telemetry-quality phase rather
than adding another fact table.
