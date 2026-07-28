def build_overstock_sql(
    fn_balance_sales,
    placeholder,
    and_store_ids_str,
    and_item_type_str,
    and_excluded_items_str,
    include_last_trans_date=False,
):
    if not include_last_trans_date:
        return f"""
            SELECT 
                s1.store_id,
                s1.item_id,
                s1.available_balance,
                s1.qty_sales,
                s1.balance,
                s2.sales_x_qty
            FROM (
                SELECT store_id, item_id, balance - ISNULL(qty_sales, 0) AS available_balance, qty_sales, balance
                FROM {fn_balance_sales}({placeholder}, {placeholder})
                WHERE (balance - ISNULL(qty_sales, 0)) >= 1 {and_store_ids_str} {and_item_type_str}
                {and_excluded_items_str or ''}
            ) AS s1
            LEFT JOIN (
                SELECT store_id, item_id, qty_sales AS sales_x_qty
                FROM {fn_balance_sales}({placeholder}, {placeholder})
                WHERE (1=1) {and_item_type_str} {and_store_ids_str} {and_excluded_items_str}
            ) AS s2
              ON s1.store_id = s2.store_id 
             AND s1.item_id  = s2.item_id
        """, False

    return f"""
        SELECT 
            s1.store_id,
            s1.item_id,
            s1.available_balance,
            s1.qty_sales,
            s1.balance,
            s2.sales_x_qty,
            s3.last_trans_date
        FROM (
            SELECT store_id, item_id, balance - ISNULL(qty_sales, 0) AS available_balance, qty_sales, balance
            FROM {fn_balance_sales}({placeholder}, {placeholder})
            WHERE (balance - ISNULL(qty_sales, 0)) >= 1 {and_store_ids_str} {and_item_type_str}
            {and_excluded_items_str or ''}
        ) AS s1
        LEFT JOIN (
            SELECT store_id, item_id, qty_sales AS sales_x_qty
            FROM {fn_balance_sales}({placeholder}, {placeholder})
            WHERE (1=1) {and_item_type_str} {and_store_ids_str} {and_excluded_items_str}
        ) AS s2
          ON s1.store_id = s2.store_id 
         AND s1.item_id  = s2.item_id
        LEFT JOIN (
            SELECT
                d.st_from_store AS store_id,
                d.st_itm_id AS item_id,
                MAX(h.sec_insert_date) AS last_trans_date
            FROM Store_Trans_h AS h
            JOIN Store_Trans AS d
              ON h.stnh_id = d.stnh_id
             AND h.stnh_f_sto_id = d.st_from_store
            GROUP BY d.st_from_store, d.st_itm_id
        ) AS s3
          ON s1.store_id = s3.store_id
         AND s1.item_id = s3.item_id
    """, True
