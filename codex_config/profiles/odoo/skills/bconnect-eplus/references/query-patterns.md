# Preserved Query Patterns

Source: repository AGENTS.md. These are reference examples, not ready-to-run production queries. Read the relevant subsection only.

Before adaptation: bind authorized branches; `@store_id=NULL` may expose all stores and is only valid for explicitly authorized cross-branch reporting. The invoice-detail example lacks a branch predicate: add the appropriate header/store join and caller-authorized filter. Confirm whether sth_id is unique across stores before COUNT(DISTINCT). Use decimal division and validate nonzero/null conversion factors; several original queries omit NULLIF. Unknown itm_unit values must be validated rather than assumed safe. Current balances and period sales use different time semantics. Plain names may be empty/encrypted. Verify the medicine field (`itm_ismedicine` was observed) and returns/discount/tax definitions. Parameterize dates and values; expand IN placeholders through the connector. NOLOCK requires an explicit consistency decision. Temp-table SQL belongs to a controlled connection and is not permission for external business-data writes.

## Sales, Inventory and Returns

```sql
-- 1) E-Plus sales per day by store/product
SELECT sh.sto_id, sd.itm_id,
       SUM(CASE sd.itm_unit
             WHEN 1 THEN ISNULL(sd.qnty,0)-ISNULL(sd.itm_back,0)
             WHEN 2 THEN (ISNULL(sd.qnty,0)-ISNULL(sd.itm_back,0)) / NULLIF(ic.itm_unit1_unit2,0)
             WHEN 3 THEN (ISNULL(sd.qnty,0)-ISNULL(sd.itm_back,0)) / NULLIF(ic.itm_unit1_unit3,0)
             ELSE ISNULL(sd.qnty,0)-ISNULL(sd.itm_back,0)
           END) AS sales_qty
FROM r_sales_trans_d sd WITH (NOLOCK)
JOIN r_sales_trans_h sh WITH (NOLOCK) ON sd.sth_id = sh.sth_id AND sd.std_stock_id = sh.sto_id
JOIN item_catalog ic WITH (NOLOCK) ON ic.itm_id = sd.itm_id
WHERE sd.sec_insert_date >= ? AND sd.sec_insert_date < ? AND sh.sto_id IN (?)
GROUP BY sh.sto_id, sd.itm_id;

-- 2) E-Plus total inventory by product across stores
SELECT ics.itm_id, SUM(CAST(ics.itm_qty / ic.itm_unit1_unit3 AS decimal(18,2))) AS balance
FROM Item_Class_Store ics WITH (NOLOCK)
JOIN item_catalog ic WITH (NOLOCK) ON ic.itm_id = ics.itm_id
WHERE ic.itm_active = 1 AND ics.sto_id IN (?)
GROUP BY ics.itm_id
HAVING SUM(CAST(ics.itm_qty / ic.itm_unit1_unit3 AS decimal(18,2))) > 0;

-- 3) E-Plus inventory by product/store
SELECT ics.itm_id, ics.sto_id,
       SUM(CAST(ics.itm_qty / ic.itm_unit1_unit3 AS decimal(18,2))) AS balance
FROM Item_Class_Store ics WITH (NOLOCK)
JOIN item_catalog ic WITH (NOLOCK) ON ic.itm_id = ics.itm_id
WHERE ic.itm_active = 1 AND ics.sto_id IN (?)
GROUP BY ics.itm_id, ics.sto_id
HAVING SUM(CAST(ics.itm_qty / ic.itm_unit1_unit3 AS decimal(18,2))) > 0;

-- 4) E-Plus batch stock for one product/store
SELECT ics.c_id, ics.itm_id, ics.sto_id, ics.sell_price,
       ics.itm_qty AS qty_small,
       ics.itm_qty / ic.itm_unit1_unit3 AS qty,
       ics.pharm_price + ics.sell_tax AS cost,
       ics.itm_expiry_date
FROM item_class_store ics
JOIN item_catalog ic ON ic.itm_id = ics.itm_id
WHERE ics.sto_id = ? AND ics.itm_id = ? AND ics.itm_qty > 0;

-- 5) E-Plus invoice details / returnable qty
SELECT sd.std_id, sd.sth_id, sd.itm_id, sd.c_id, sd.qnty, sd.itm_unit,
       sd.itm_sell, sd.itm_cost, sd.itm_aver_cost, sd.itm_back, sd.itm_nexist,
       ic.itm_unit1_unit2, ic.itm_unit1_unit3
FROM sales_trans_d sd
JOIN item_catalog ic ON ic.itm_id = sd.itm_id
WHERE sd.sth_id = ?
ORDER BY sd.std_id;
```

When implementing these patterns in Odoo modules, keep them parameterized. Expand `IN (?)` placeholders using the established B-Connect connector helper rather than string-concatenating branch IDs.

## E-Plus Dashboard Query Pack

Use this as the E-Plus-only query pack for future dashboard and migration work. The default assumption is that dashboards read from consolidated replica tables `r_sales_trans_h` and `r_sales_trans_d`. For a single-store database, replace them with `sales_trans_h` and `sales_trans_d` and remove `d.std_stock_id = h.sto_id` from joins.

```sql
DECLARE @date_from DATETIME = '2026-07-01';
DECLARE @date_to   DATETIME = '2026-07-10'; -- exclusive
DECLARE @store_id INT = NULL;               -- NULL = all stores

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
    CASE WHEN ISNULL(h.fh_contract_id, 0) <> 0
           OR ISNULL(h.fh_company_part, 0) <> 0
           OR NULLIF(LTRIM(RTRIM(ISNULL(h.fh_medins_rec_name, ''))), '') IS NOT NULL
         THEN 1 ELSE 0 END AS is_contract,
    CASE WHEN ISNULL(h.total_des_mon, 0) <> 0
           OR ISNULL(h.total_dis_per, 0) <> 0
           OR ISNULL(h.sth_pnt_dis, 0) <> 0
           OR EXISTS (
                SELECT 1
                FROM r_sales_trans_d d WITH (NOLOCK)
                WHERE d.sth_id = h.sth_id
                  AND d.std_stock_id = h.sto_id
                  AND (ISNULL(d.itm_dis_mon, 0) <> 0 OR ISNULL(d.itm_dis_per, 0) <> 0)
           )
         THEN 1 ELSE 0 END AS is_offer,
    CASE
        WHEN ISNULL(h.total_des_mon, 0) <> 0 OR ISNULL(h.total_dis_per, 0) <> 0 OR ISNULL(h.sth_pnt_dis, 0) <> 0 THEN 'offer'
        WHEN ISNULL(h.fh_contract_id, 0) <> 0 OR ISNULL(h.fh_company_part, 0) <> 0 THEN 'contract'
        WHEN h.bill_typ = 4 THEN 'delivery'
        ELSE 'cash'
    END AS collection_category
INTO #invoice_base
FROM r_sales_trans_h h WITH (NOLOCK)
WHERE h.sec_insert_date >= @date_from
  AND h.sec_insert_date < @date_to
  AND h.sth_flag = 'C'
  AND (@store_id IS NULL OR h.sto_id = @store_id);

-- Top KPIs
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

-- Collection method cards: cash / delivery / contracts / offers
SELECT
    collection_category,
    COUNT(*) AS invoice_count,
    SUM(net_amount) AS total_sales,
    100.0 * SUM(net_amount) / NULLIF((SELECT SUM(net_amount) FROM #invoice_base), 0) AS pct_of_total
FROM #invoice_base
GROUP BY collection_category
ORDER BY total_sales DESC;

-- Contract تحمل percentage
SELECT
    SUM(CASE WHEN is_contract = 1 THEN net_amount - company_part ELSE 0 END) AS customer_bearing_amount,
    SUM(CASE WHEN is_contract = 1 THEN company_part ELSE 0 END) AS company_part_amount,
    100.0 * SUM(CASE WHEN is_contract = 1 THEN net_amount - company_part ELSE 0 END)
        / NULLIF(SUM(CASE WHEN is_contract = 1 THEN net_amount ELSE 0 END), 0) AS bearing_pct
FROM #invoice_base;

-- Sales by user
SELECT TOP (20)
    h.emp_id,
    COALESCE(e.e_name_ar, e.e_name, CONVERT(VARCHAR(20), h.emp_id)) AS employee_name,
    COUNT(*) AS invoice_count,
    SUM(h.net_amount) AS total_sales,
    100.0 * SUM(h.net_amount) / NULLIF((SELECT SUM(net_amount) FROM #invoice_base), 0) AS pct_of_total
FROM #invoice_base h
LEFT JOIN employee e WITH (NOLOCK) ON e.e_id = h.emp_id
GROUP BY h.emp_id, e.e_name_ar, e.e_name
ORDER BY total_sales DESC;
```

Replace `ic.itm_is_medicine` with the real E-Plus medicine/classification column if different.

```sql
-- Medicine vs non-medicine
SELECT
    CASE WHEN ISNULL(ic.itm_is_medicine, 1) = 1 THEN 'medicine' ELSE 'non_medicine' END AS item_type,
    SUM((ISNULL(d.qnty,0) - ISNULL(d.itm_back,0)) * ISNULL(d.itm_sell,0) - ISNULL(d.itm_dis_mon,0)) AS sales_amount
FROM r_sales_trans_d d WITH (NOLOCK)
JOIN #invoice_base h ON h.sth_id = d.sth_id AND h.sto_id = d.std_stock_id
JOIN item_catalog ic WITH (NOLOCK) ON ic.itm_id = d.itm_id
GROUP BY CASE WHEN ISNULL(ic.itm_is_medicine, 1) = 1 THEN 'medicine' ELSE 'non_medicine' END;

-- Top sold items + current balance
SELECT TOP (20)
    d.itm_id,
    COALESCE(ic.itm_name_ar, ic.itm_name, ic.itm_code, CONVERT(VARCHAR(20), d.itm_id)) AS item_name,
    COUNT(DISTINCT d.sth_id) AS sale_times,
    SUM(CASE d.itm_unit
            WHEN 1 THEN ISNULL(d.qnty,0) - ISNULL(d.itm_back,0)
            WHEN 2 THEN (ISNULL(d.qnty,0) - ISNULL(d.itm_back,0)) / NULLIF(ic.itm_unit1_unit2,0)
            WHEN 3 THEN (ISNULL(d.qnty,0) - ISNULL(d.itm_back,0)) / NULLIF(ic.itm_unit1_unit3,0)
            ELSE ISNULL(d.qnty,0) - ISNULL(d.itm_back,0)
        END) AS sold_qty,
    ISNULL(b.balance, 0) AS current_balance
FROM r_sales_trans_d d WITH (NOLOCK)
JOIN #invoice_base h ON h.sth_id = d.sth_id AND h.sto_id = d.std_stock_id
JOIN item_catalog ic WITH (NOLOCK) ON ic.itm_id = d.itm_id
OUTER APPLY (
    SELECT SUM(CAST(ics.itm_qty / NULLIF(ic.itm_unit1_unit3,0) AS DECIMAL(18,2))) AS balance
    FROM Item_Class_Store ics WITH (NOLOCK)
    WHERE ics.itm_id = d.itm_id
      AND (@store_id IS NULL OR ics.sto_id = @store_id)
) b
GROUP BY d.itm_id, ic.itm_name_ar, ic.itm_name, ic.itm_code, b.balance
ORDER BY sale_times DESC, sold_qty DESC;

-- Recent customer invoices
SELECT TOP (20)
    h.sth_id AS invoice_no,
    h.sec_insert_date,
    COALESCE(c.cust_name_ar, CONVERT(VARCHAR(20), h.cust_id)) AS customer_name,
    h.net_amount AS invoice_total,
    COUNT(d.std_id) AS item_count,
    STRING_AGG(COALESCE(ic.itm_name_ar, ic.itm_name, ic.itm_code), N'، ') AS items
FROM #invoice_base h
LEFT JOIN Customer c WITH (NOLOCK) ON c.cust_id = h.cust_id
JOIN r_sales_trans_d d WITH (NOLOCK) ON d.sth_id = h.sth_id AND d.std_stock_id = h.sto_id
JOIN item_catalog ic WITH (NOLOCK) ON ic.itm_id = d.itm_id
GROUP BY h.sth_id, h.sec_insert_date, h.cust_id, c.cust_name_ar, h.net_amount
ORDER BY h.sec_insert_date DESC;
```

For write-sensitive tables and transaction boundaries, read
[synchronization](synchronization.md). Examples do not authorize writes.
