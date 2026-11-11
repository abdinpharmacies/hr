# Sales Dashboard

`ab_sales_dashboard` is the management reporting dashboard for sales data read from
E-Plus / BConnect. The module is designed to show management reviewed reports in
Odoo while keeping E-Plus / BConnect as the source of truth for legacy sales and
stock facts.

The module currently uses `ab_eplus_connect` to read BConnect through Microsoft
SQL Server, stores aggregated dashboard snapshots in Odoo, and renders an Arabic
RTL OWL client action.

## Primary Goals

- Fast management dashboard refreshes from BConnect.
- Accurate sales, invoice, collection, employee, customer, medicine, and stock
  report values.
- Bounded memory usage on the production Odoo server.
- Read-only access to E-Plus / BConnect.
- No replication of raw reporting rows into Odoo unless needed for bounded
  snapshots, cache, or reviewed report history.

## Production Constraints

- No report refresh, HTTP request, cron, export, or worker task should approach
  1.5 GB RAM.
- Large BConnect tables may contain millions of sales and inventory rows.
- Dashboard queries must aggregate inside SQL Server and return small result
  sets.
- Raw invoice-line or stock-detail exports must be asynchronous and streamed.
- Date ranges must be bounded before opening a BConnect query.
- Store access must be enforced on the server, not only in the frontend.
- External BConnect data is read-only unless explicitly approved otherwise.

## BConnect Reference

Reference repository:

```text
https://github.com/Hossam-elsheikh/e-plus-structure.git
```

Primary reference file:

```text
e-plus-db.md
```

The reference was generated from the configured BConnect / E-Plus SQL Server
database named `genius`. It documents the discovered schema and confirms that the
key product and stock path is:

```text
Item_Catalog -> Item_Class_Store -> Store
```

Important schema facts from the reference:

- The SQL Server database contains 238 user tables and 3460 columns.
- Current custom addons reference 29 E-Plus tables in SQL contexts.
- Broad production `COUNT(*)` scans were intentionally avoided.
- Product names may be stored in encrypted fields such as
  `itm_name_ar_encrypt` and `itm_name_en_encrypt`; do not assume plain product
  name columns are populated.
- Stable identifiers such as `itm_id`, `itm_code`, `sto_id`, `sto_code`, and
  transaction IDs must be preserved for traceability.

## Relevant BConnect Tables

| Table | Purpose |
| --- | --- |
| `r_sales_trans_h` | Replicated or historical sales invoice headers. Preferred source for management dashboard sales reporting. |
| `r_sales_trans_d` | Replicated or historical sales invoice details. Used with `r_sales_trans_h` for item, medicine, and invoice-detail metrics. |
| `sales_trans_h` | Live invoice header table. Used for bill status, returns, and live invoice operations. |
| `sales_trans_d` | Live invoice detail table. Used for invoice lines and returnable quantities. |
| `Item_Class_Store` / `item_class_store` | Store-scoped stock batches by product, class/batch, quantity, expiry, and price. |
| `Item_Catalog` / `item_catalog` | Product master, active flag, default price, UoM conversion, medicine flag, product groups, and scientific data. |
| `Store` | Store metadata including store IDs, codes, names, and server IP fields. |
| `Customer` | Customer lookup and reporting dimensions. |
| `Customer_Delivery` | Customer delivery/reporting dimensions. |
| `sales_return` | Posted return facts. |
| `sales_return_payment` | Posted return payment facts. |
| `F_Transaction_Header` | Finance/cash impact of sales and returns. |
| `F_Cash_Store` | Store cash/finance impact. |
| `sales_deliv_info` | Delivery/customer contact snapshot. |
| `employee` | E-Plus employee lookup. |
| `Replication_Trans` | Replication queue/transaction table for stock and transaction propagation. |

## Metadata Validation Notes

A metadata-only BConnect check was run through the existing Odoo connector. It
read `INFORMATION_SCHEMA` and `sys.indexes`; it did not scan sales rows.

Confirmed columns used by this module:

- `r_sales_trans_h`: `sth_id`, `sto_id`, `cust_id`, `emp_id`,
  `sec_insert_date`, `total_bill_net`, `fh_company_part`, `fh_contract_id`,
  `fh_medins_rec_name`, `bill_typ`, `sth_flag`, `total_des_mon`,
  `total_dis_per`, `sth_pnt_dis`
- `r_sales_trans_d`: `sth_id`, `std_stock_id`, `itm_id`, `itm_unit`, `qnty`,
  `itm_back`, `itm_sell`, `itm_dis_mon`, `itm_dis_per`, `sec_insert_date`
- `Item_Catalog`: `itm_id`, `itm_code`, `itm_ismedicine`,
  `itm_unit1_unit2`, `itm_unit1_unit3`
- `Item_Class_Store`: `itm_id`, `sto_id`, `itm_qty`
- `Employee`: `e_id`, `e_Name`
- `Customer`: `cust_id`, `cust_name_ar`

Important corrections:

- The medicine flag is `itm_ismedicine`, not `itm_is_medicine`.
- The confirmed employee name column is `e_Name`; `e_name_ar` was not confirmed
  in the metadata probe.
- Plain item name columns are not reliable from the reference. Use `itm_code`
  or Odoo `ab_product.display_name` unless the decryption/name path is
  explicitly confirmed.

Observed useful index coverage:

- `r_sales_trans_h` has date/store/header indexes such as
  `IX_r_sales_trans_h_date_sto`, `IX_r_sales_trans_h_Join_Date`,
  `IX_r_sales_trans_h_sto_sth`, and `indx_r_s__insert_date`.
- `r_sales_trans_d` has header/store and sales-search indexes such as
  `ix_r_sales_trans_d`, `IX_r_sales_trans_d_Sales_Search`,
  `indx_r_s__insert_date`, and item indexes.
- `Item_Catalog` has primary/item-code indexes and `indx_itm_medicine`.
- `Item_Class_Store` has several item/store/quantity indexes.

This index shape supports bounded dashboard refreshes using date/store filters
and joins on `(sth_id, sto_id/std_stock_id)`.

## Current Module Flow

```text
OWL dashboard action
  -> ab.sales.dashboard.snapshot.get_dashboard_data()
  -> latest Odoo snapshot for the selected filters

Refresh from E-Plus
  -> ab.sales.dashboard.snapshot.refresh_dashboard_data()
  -> ab.sales.dashboard.service.fetch_dashboard_data()
  -> aggregated BConnect SQL queries
  -> Odoo snapshot + child lines
  -> OWL dashboard renders snapshot payload
```

Current Odoo snapshot models:

- `ab.sales.dashboard.snapshot`
- `ab.sales.dashboard.collection.line`
- `ab.sales.dashboard.user.line`
- `ab.sales.dashboard.item.line`
- `ab.sales.dashboard.invoice.line`

## Accuracy Rules

- Use completed invoices only:

```sql
h.sth_flag = 'C'
```

- Use exclusive date boundaries:

```sql
h.sec_insert_date >= @date_from
AND h.sec_insert_date < @date_to
```

- For Odoo date filters, convert user `date_to` to the next day before sending
  it to BConnect.
- For replicated dashboard reports, prefer `r_sales_trans_h` and
  `r_sales_trans_d`.
- For live invoice status, returns, and returnable quantities, use
  `sales_trans_h` and `sales_trans_d`.
- Quantities must respect E-Plus unit conversion:

```sql
CASE d.itm_unit
  WHEN 1 THEN ISNULL(d.qnty,0) - ISNULL(d.itm_back,0)
  WHEN 2 THEN (ISNULL(d.qnty,0) - ISNULL(d.itm_back,0)) / NULLIF(ic.itm_unit1_unit2,0)
  WHEN 3 THEN (ISNULL(d.qnty,0) - ISNULL(d.itm_back,0)) / NULLIF(ic.itm_unit1_unit3,0)
  ELSE ISNULL(d.qnty,0) - ISNULL(d.itm_back,0)
END
```

- Use `NULLIF` for every unit divisor.
- Header totals (`total_bill_net`) are the source for invoice-level KPIs.
- Detail-derived sales amounts may not reconcile perfectly with header totals
  if header discounts, rounding, or invoice-level adjustments exist.

## Performance Rules

- Push aggregation to SQL Server using `SUM`, `COUNT`, `COUNT DISTINCT`,
  `GROUP BY`, `CASE`, and `TOP`.
- Do not load raw sales or stock rows into Python for dashboard rendering.
- Do not use unlimited `fetchall()` for large reports.
- Do not allow unrestricted date ranges.
- Do not return unlimited invoice or item rows to the browser.
- Prefer one bounded SQL refresh that populates a temporary invoice base inside
  SQL Server, then query dashboard widgets from that base.
- A dashboard snapshot should store only aggregated, bounded results.

Recommended initial limits:

| Parameter | Suggested value |
| --- | ---: |
| Dashboard refresh range | 31 days |
| Detailed report range | 31 days |
| Export range | 90 days |
| Top users/items/invoices | 20, configurable up to 100 |
| Heavy reporting concurrency | 1 job |

## BConnect Base Query Pack

These queries are the baseline E-Plus query pack for future dashboard and report
development. They must remain parameterized. Do not concatenate user input into
SQL.

### 1. Sales Per Day By Store/Product

```sql
SELECT sh.sto_id, sd.itm_id,
       SUM(CASE sd.itm_unit
             WHEN 1 THEN ISNULL(sd.qnty,0)-ISNULL(sd.itm_back,0)
             WHEN 2 THEN (ISNULL(sd.qnty,0)-ISNULL(sd.itm_back,0)) / NULLIF(ic.itm_unit1_unit2,0)
             WHEN 3 THEN (ISNULL(sd.qnty,0)-ISNULL(sd.itm_back,0)) / NULLIF(ic.itm_unit1_unit3,0)
             ELSE ISNULL(sd.qnty,0)-ISNULL(sd.itm_back,0)
           END) AS sales_qty
FROM r_sales_trans_d sd WITH (NOLOCK)
JOIN r_sales_trans_h sh WITH (NOLOCK)
  ON sd.sth_id = sh.sth_id
 AND sd.std_stock_id = sh.sto_id
JOIN item_catalog ic WITH (NOLOCK)
  ON ic.itm_id = sd.itm_id
WHERE sd.sec_insert_date >= ?
  AND sd.sec_insert_date < ?
  AND sh.sto_id IN (?)
GROUP BY sh.sto_id, sd.itm_id;
```

### 2. Total Inventory By Product Across Stores

```sql
SELECT
    ics.itm_id,
    SUM(CAST(ics.itm_qty / NULLIF(ic.itm_unit1_unit3, 0) AS decimal(18,2))) AS balance
FROM Item_Class_Store ics WITH (NOLOCK)
JOIN item_catalog ic WITH (NOLOCK)
  ON ic.itm_id = ics.itm_id
WHERE ic.itm_active = 1
  AND ics.sto_id IN (?)
GROUP BY ics.itm_id
HAVING SUM(CAST(ics.itm_qty / NULLIF(ic.itm_unit1_unit3, 0) AS decimal(18,2))) > 0;
```

### 3. Inventory By Product/Store

```sql
SELECT
    ics.itm_id,
    ics.sto_id,
    SUM(CAST(ics.itm_qty / NULLIF(ic.itm_unit1_unit3, 0) AS decimal(18,2))) AS balance
FROM Item_Class_Store ics WITH (NOLOCK)
JOIN item_catalog ic WITH (NOLOCK)
  ON ic.itm_id = ics.itm_id
WHERE ic.itm_active = 1
  AND ics.sto_id IN (?)
GROUP BY ics.itm_id, ics.sto_id
HAVING SUM(CAST(ics.itm_qty / NULLIF(ic.itm_unit1_unit3, 0) AS decimal(18,2))) > 0;
```

### 4. Batch Stock For One Product/Store

```sql
SELECT
    ics.c_id,
    ics.itm_id,
    ics.sto_id,
    ics.sell_price,
    ics.itm_qty AS qty_small,
    ics.itm_qty / NULLIF(ic.itm_unit1_unit3,0) AS qty,
    ics.pharm_price + ics.sell_tax AS cost,
    ics.itm_expiry_date
FROM item_class_store ics
JOIN item_catalog ic
  ON ic.itm_id = ics.itm_id
WHERE ics.sto_id = ?
  AND ics.itm_id = ?
  AND ics.itm_qty > 0;
```

### 5. Invoice Details / Returnable Quantity

```sql
SELECT
    sd.std_id,
    sd.sth_id,
    sd.itm_id,
    sd.c_id,
    sd.qnty,
    sd.itm_unit,
    sd.itm_sell,
    sd.itm_cost,
    sd.itm_aver_cost,
    sd.itm_back,
    sd.itm_nexist,
    ic.itm_unit1_unit2,
    ic.itm_unit1_unit3
FROM sales_trans_d sd
JOIN item_catalog ic
  ON ic.itm_id = sd.itm_id
WHERE sd.sth_id = ?
ORDER BY sd.std_id;
```

## Dashboard Query Strategy

For management dashboard refreshes, prefer the consolidated replica tables:

```text
r_sales_trans_h
r_sales_trans_d
```

For a single-store database, use:

```text
sales_trans_h
sales_trans_d
```

and remove this replicated-table join condition:

```sql
d.std_stock_id = h.sto_id
```

### Recommended Temporary Table Base

Use one SQL Server session for the full dashboard refresh and create
`#invoice_base` once. Temporary tables are connection-scoped, so all dependent
queries must run on the same MSSQL connection.

```sql
DECLARE @date_from DATETIME = '2026-07-01';
DECLARE @date_to   DATETIME = '2026-07-10'; -- exclusive
DECLARE @store_id INT = NULL;               -- NULL = all permitted stores

IF OBJECT_ID('tempdb..#invoice_base') IS NOT NULL DROP TABLE #invoice_base;

SELECT
    h.sth_id,
    h.sto_id,
    h.cust_id,
    h.emp_id,
    h.sec_insert_date,
    CAST(ISNULL(h.total_bill_net, 0) AS DECIMAL(18,2)) AS net_amount,
    CAST(ISNULL(h.fh_company_part, 0) AS DECIMAL(18,2)) AS company_part,
    CASE WHEN h.bill_typ = 4 THEN 1 ELSE 0 END AS is_delivery,
    CASE
        WHEN ISNULL(h.fh_contract_id, 0) <> 0
          OR ISNULL(h.fh_company_part, 0) <> 0
          OR NULLIF(LTRIM(RTRIM(ISNULL(h.fh_medins_rec_name, ''))), '') IS NOT NULL
        THEN 1 ELSE 0
    END AS is_contract,
    CASE
        WHEN ISNULL(h.total_des_mon, 0) <> 0
          OR ISNULL(h.total_dis_per, 0) <> 0
          OR ISNULL(h.sth_pnt_dis, 0) <> 0
          OR ISNULL(detail_offer.has_detail_discount, 0) = 1
        THEN 1 ELSE 0
    END AS is_offer,
    CASE
        WHEN ISNULL(h.total_des_mon, 0) <> 0
          OR ISNULL(h.total_dis_per, 0) <> 0
          OR ISNULL(h.sth_pnt_dis, 0) <> 0
          OR ISNULL(detail_offer.has_detail_discount, 0) = 1
        THEN 'offer'
        WHEN ISNULL(h.fh_contract_id, 0) <> 0
          OR ISNULL(h.fh_company_part, 0) <> 0
        THEN 'contract'
        WHEN h.bill_typ = 4
        THEN 'delivery'
        ELSE 'cash'
    END AS collection_category
INTO #invoice_base
FROM r_sales_trans_h h WITH (NOLOCK)
OUTER APPLY (
    SELECT TOP (1) 1 AS has_detail_discount
    FROM r_sales_trans_d d WITH (NOLOCK)
    WHERE d.sth_id = h.sth_id
      AND d.std_stock_id = h.sto_id
      AND (
          ISNULL(d.itm_dis_mon, 0) <> 0
          OR ISNULL(d.itm_dis_per, 0) <> 0
      )
) detail_offer
WHERE h.sec_insert_date >= @date_from
  AND h.sec_insert_date < @date_to
  AND h.sth_flag = 'C'
  AND (@store_id IS NULL OR h.sto_id = @store_id);
```

Implementation notes:

- `collection_category` uses the same header/detail discount logic as
  `is_offer`, so products on sale, coupons, and line-level discounts are
  categorized as `offer`.
- The dashboard normalizes collection payloads to the four bounded categories:
  `cash`, `delivery`, `contract`, and `offer`; categories with no sales are
  returned as zero-value cards.
- If the base grows large, create a temporary index after the insert:

```sql
CREATE INDEX IX_invoice_base_sto_sth ON #invoice_base (sto_id, sth_id);
CREATE INDEX IX_invoice_base_emp ON #invoice_base (emp_id);
```

Only create temp indexes when the measured refresh workload benefits from them.

### Top KPIs

```sql
DECLARE @days DECIMAL(18,4) = NULLIF(DATEDIFF(DAY, @date_from, @date_to), 0);
DECLARE @prev_from DATETIME = DATEADD(MONTH, -1, @date_from);
DECLARE @prev_to   DATETIME = DATEADD(MONTH, -1, @date_to);

SELECT
    SUM(net_amount) AS total_sales,
    SUM(net_amount) / @days AS avg_daily_sales,
    (
        SELECT SUM(ISNULL(h.total_bill_net, 0)) / @days
        FROM r_sales_trans_h h WITH (NOLOCK)
        WHERE h.sec_insert_date >= @prev_from
          AND h.sec_insert_date < @prev_to
          AND h.sth_flag = 'C'
          AND (@store_id IS NULL OR h.sto_id = @store_id)
    ) AS prev_period_avg_daily_sales
FROM #invoice_base;
```

Note: the current module compares against the immediately preceding period. The
business decision should confirm whether comparison must be previous same-length
period or same dates shifted one month backward.

### Collection Method Cards

```sql
SELECT
    collection_category,
    COUNT(*) AS invoice_count,
    SUM(net_amount) AS total_sales,
    100.0 * SUM(net_amount) / NULLIF((SELECT SUM(net_amount) FROM #invoice_base), 0) AS pct_of_total
FROM #invoice_base
GROUP BY collection_category
ORDER BY total_sales DESC;
```

Required categories:

- `cash`
- `delivery`
- `contract`
- `offer`

Classification priority must be documented. Current proposed priority is:

```text
offer -> contract -> delivery -> cash
```

This matters because an invoice can potentially be delivery and contract, or
delivery and offer.

### Contract Customer-Bearing Percentage

```sql
SELECT
    SUM(CASE WHEN is_contract = 1 THEN net_amount ELSE 0 END) AS customer_bearing_amount,
    SUM(CASE WHEN is_contract = 1 THEN company_part ELSE 0 END) AS company_part_amount,
    100.0 * SUM(CASE WHEN is_contract = 1 THEN net_amount ELSE 0 END)
        / NULLIF(SUM(CASE WHEN is_contract = 1 THEN net_amount + company_part ELSE 0 END), 0) AS bearing_pct
FROM #invoice_base;
```

For contract invoices generated by the Odoo contract flow, `total_bill_net`
maps to the customer-paid share and `fh_company_part` maps to the
insurance/company share. The bearing denominator is therefore
`net_amount + company_part`; subtracting company share from `net_amount` can
produce false negative bearing percentages.
Any future finance report must revalidate that meaning with business owners.

### Sales By Employee

Confirmed metadata uses `Employee.e_Name`.

```sql
SELECT TOP (20)
    h.emp_id,
    COALESCE(e.e_Name, CONVERT(VARCHAR(20), h.emp_id)) AS employee_name,
    COUNT(*) AS invoice_count,
    SUM(h.net_amount) AS total_sales,
    100.0 * SUM(h.net_amount) / NULLIF((SELECT SUM(net_amount) FROM #invoice_base), 0) AS pct_of_total
FROM #invoice_base h
LEFT JOIN Employee e WITH (NOLOCK)
  ON e.e_id = h.emp_id
GROUP BY h.emp_id, e.e_Name
ORDER BY total_sales DESC;
```

### Medicine Vs Non-Medicine

Confirmed metadata uses `item_catalog.itm_ismedicine`.

```sql
SELECT
    CASE WHEN ISNULL(ic.itm_ismedicine, 1) = 1 THEN 'medicine' ELSE 'non_medicine' END AS item_type,
    SUM(
        ((ISNULL(d.qnty,0) - ISNULL(d.itm_back,0)) * ISNULL(d.itm_sell,0))
        * (1 - (ISNULL(d.itm_dis_per, 0) / 100.0))
        - ISNULL(d.itm_dis_mon,0)
    ) AS sales_amount
FROM r_sales_trans_d d WITH (NOLOCK)
JOIN #invoice_base h
  ON h.sth_id = d.sth_id
 AND h.sto_id = d.std_stock_id
JOIN item_catalog ic WITH (NOLOCK)
  ON ic.itm_id = d.itm_id
GROUP BY CASE WHEN ISNULL(ic.itm_ismedicine, 1) = 1 THEN 'medicine' ELSE 'non_medicine' END;
```

Accuracy note: this is a detail-line calculation. It may differ from
invoice-header totals when header-level discounts, rounding, or adjustments are
present.

### Top Sold Items With Current Balance

Product names should preferably come from Odoo `ab_product` by `eplus_serial`
because E-Plus plain name columns may not be reliable.

```sql
SELECT TOP (20)
    d.itm_id,
    ic.itm_code,
    COUNT(DISTINCT d.sth_id) AS sale_times,
    SUM(CASE d.itm_unit
            WHEN 1 THEN ISNULL(d.qnty,0) - ISNULL(d.itm_back,0)
            WHEN 2 THEN (ISNULL(d.qnty,0) - ISNULL(d.itm_back,0)) / NULLIF(ic.itm_unit1_unit2,0)
            WHEN 3 THEN (ISNULL(d.qnty,0) - ISNULL(d.itm_back,0)) / NULLIF(ic.itm_unit1_unit3,0)
            ELSE ISNULL(d.qnty,0) - ISNULL(d.itm_back,0)
        END) AS sold_qty,
    ISNULL(b.balance, 0) AS current_balance
FROM r_sales_trans_d d WITH (NOLOCK)
JOIN #invoice_base h
  ON h.sth_id = d.sth_id
 AND h.sto_id = d.std_stock_id
JOIN item_catalog ic WITH (NOLOCK)
  ON ic.itm_id = d.itm_id
OUTER APPLY (
    SELECT SUM(CAST(ics.itm_qty / NULLIF(ic_balance.itm_unit1_unit3,0) AS DECIMAL(18,2))) AS balance
    FROM Item_Class_Store ics WITH (NOLOCK)
    JOIN item_catalog ic_balance WITH (NOLOCK)
      ON ic_balance.itm_id = ics.itm_id
    WHERE ics.itm_id = d.itm_id
      AND (@store_id IS NULL OR ics.sto_id = @store_id)
) b
GROUP BY d.itm_id, ic.itm_code, b.balance
ORDER BY sale_times DESC, sold_qty DESC;
```

Recommended performance improvement:

- Aggregate top item IDs first, limited by `TOP`.
- Then join/apply current balance only for those top item IDs.

### Recent Customer Invoices

```sql
SELECT TOP (20)
    h.sth_id AS invoice_no,
    h.sec_insert_date,
    COALESCE(
      NULLIF(LTRIM(RTRIM(sdi.contact)), ''),
      NULLIF(LTRIM(RTRIM(cd.cd_contact_person)), ''),
      CASE
        WHEN NULLIF(LTRIM(RTRIM(c.cust_name_ar)), '') LIKE 'spare%' THEN NULL
        ELSE NULLIF(LTRIM(RTRIM(c.cust_name_ar)), '')
      END,
      NULLIF(LTRIM(RTRIM(cd.cd_tel)), ''),
      CASE WHEN ISNULL(h.cust_id, 0) = 0 THEN 'Cash Customer' ELSE CONVERT(VARCHAR(20), h.cust_id) END
    ) AS customer_name,
    h.net_amount AS invoice_total,
    COUNT(d.std_id) AS item_count,
    STRING_AGG(CONVERT(NVARCHAR(MAX), COALESCE(ic.itm_code, CONVERT(VARCHAR(20), d.itm_id))), N', ') AS items,
    STRING_AGG(
      CONVERT(NVARCHAR(MAX), CONCAT(CONVERT(VARCHAR(20), d.itm_id), NCHAR(31), COALESCE(ic.itm_code, CONVERT(VARCHAR(20), d.itm_id)))),
      NCHAR(30)
    ) AS item_pairs
FROM #invoice_base h
LEFT JOIN Customer c WITH (NOLOCK)
  ON c.cust_id = h.cust_id
LEFT JOIN Customer_Delivery cd WITH (NOLOCK)
  ON cd.cd_cust_id = h.cust_id
 AND cd.cd_id = 1
OUTER APPLY (
  SELECT TOP (1) sdi.contact
  FROM sales_deliv_info sdi WITH (NOLOCK)
  WHERE sdi.sth_id = h.sth_id
    AND sdi.cust_id = h.cust_id
) sdi
JOIN r_sales_trans_d d WITH (NOLOCK)
  ON d.sth_id = h.sth_id
 AND d.std_stock_id = h.sto_id
JOIN item_catalog ic WITH (NOLOCK)
  ON ic.itm_id = d.itm_id
GROUP BY h.sth_id, h.sto_id, h.sec_insert_date, h.cust_id,
         sdi.contact, cd.cd_contact_person, c.cust_name_ar, cd.cd_tel, h.net_amount
ORDER BY h.sec_insert_date DESC, h.sth_id DESC, h.sto_id DESC;
```

Recommended performance improvement:

- Select the latest `TOP (20)` invoices from `#invoice_base` first.
- Join details only for those invoices.
- This avoids aggregating all invoice details for the full reporting period.
- Resolve `item_pairs` to Odoo `ab_product.name` by E-Plus `itm_id` /
  `eplus_serial`; fall back to the E-Plus item code only when no Odoo product
  mapping exists.

## Store Scope And Security

Dashboard store filters must be intersected with the user's permitted stores on
the server.

Required behavior:

```text
requested_store_ids INTERSECT permitted_store_ids
```

If the result is empty, the request must fail safely or return an empty scoped
result according to business policy.

Users must not be able to pass arbitrary `store_id` values from the browser and
read other branches.

Candidate existing store scopes:

- `ab_store.eplus_serial`
- `ab_store.allow_sale`
- `ab_replica_db.allowed_sales_store_ids`
- module-specific management group permissions

## Snapshot And Review Policy

Management reports should be reviewable. The recommended flow is:

```text
BConnect aggregate query
  -> Odoo dashboard snapshot
  -> management review
  -> optional export from the reviewed snapshot
```

Snapshots should include:

- date range
- selected stores
- generated timestamp
- generated by user
- source note, such as `BConnect replica r_sales_trans_h/d`
- query strategy/version if report formulas change

## NOLOCK Policy

`WITH (NOLOCK)` is acceptable only for management dashboards where stale or dirty
reads are acceptable. For financial reconciliation, audited reports, or stock
critical operations, the consistency requirement must be explicitly reviewed.

## Upgrade Priorities

1. Enforce server-side store permissions.
2. Add max date-range validation before any BConnect query.
3. Move BConnect refresh to a queued job instead of a long HTTP request.
4. Use one `#invoice_base` per refresh instead of repeating the invoice CTE for
   every dashboard widget.
5. Fix collection category classification so detail discounts count as offers.
6. Optimize recent invoices and top items by limiting base rows before joining
   detail/stock tables.
7. Add structured logging for query duration, row counts, selected stores, date
   range, and snapshot ID.
8. Add async streaming exports for detail reports.
9. Add tests for date limits, store scope, category classification, and SQL
   parameter construction.

## Read-Only Rule

This module must not write to E-Plus / BConnect. It may only read source data and
store reviewed report snapshots inside Odoo PostgreSQL.
