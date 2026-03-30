# -*- coding: utf-8 -*-

from odoo import api, models, _
from odoo.exceptions import UserError

from .ab_sales_return_header import PARAM_STR


class AbSalesReturnUomRepair(models.Model):
    _inherit = "ab_sales_return_header"

    @api.model
    def fix_legacy_return_uom_rows(self, store_ids=None, header_ids=None, dry_run=True, limit=0):
        """
        Repair historical return rows posted with wrong unit assumptions.

        Fixes:
        - sales_trans_d metadata: itm_unit + std_r_itm_* markers
        - item_class_store.itm_qty: remove over-added qty caused by multiplying
          return qty by itm_unit1_unit3 when line qty was already in small unit.
        """
        dry_run = bool(dry_run)
        limit = int(limit or 0)

        store_ids = store_ids or []
        if isinstance(store_ids, (int, str)):
            store_ids = [store_ids]
        parsed_store_ids = []
        for sid in store_ids:
            try:
                parsed_store_ids.append(int(sid))
            except Exception:
                continue

        header_ids = header_ids or []
        if isinstance(header_ids, (int, str)):
            header_ids = [header_ids]
        parsed_header_ids = []
        for hid in header_ids:
            try:
                parsed_header_ids.append(int(hid))
            except Exception:
                continue

        # try:
        #     allowed_store_ids = self.env["ab_sales_header"]._get_allowed_store_ids()
        # except Exception:
        #     allowed_store_ids = self.env["ab_store"].search([("allow_sale", "=", True)]).ids
        #
        # if parsed_store_ids:
        #     target_store_ids = [sid for sid in parsed_store_ids if sid in allowed_store_ids]
        #     if not target_store_ids:
        #         raise UserError(_("No valid stores selected for repair."))
        # else:
        #     target_store_ids = allowed_store_ids
        target_store_ids = parsed_store_ids
        
        stores = self.env["ab_store"].browse(target_store_ids).exists()
        stores = stores.filtered(lambda s: s.ip1)
        if not stores:
            raise UserError(_("No stores with valid IP found for repair."))

        emp_id = int(self.env["ab_sales_header"]._get_eplus_emp_id() or 1)
        if emp_id <= 0:
            emp_id = 1

        detect_sql = f"""
            SELECT
                sd.std_id,
                sd.sth_id,
                sd.itm_id,
                sd.c_id,
                CAST(ISNULL(sd.qnty, 0) AS DECIMAL(38,6)) AS qnty,
                ISNULL(sd.itm_unit, 0) AS itm_unit,
                CAST(ISNULL(sd.itm_sell, 0) AS DECIMAL(38,6)) AS itm_sell,
                CAST(ISNULL(sd.itm_cost, 0) AS DECIMAL(38,6)) AS itm_cost,
                CAST(ISNULL(sd.itm_dis_mon, 0) AS DECIMAL(38,6)) AS itm_dis_mon,
                CAST(ISNULL(sd.itm_dis_per, 0) AS DECIMAL(38,6)) AS itm_dis_per,
                CAST(ISNULL(sd.itm_back, 0) AS DECIMAL(38,6)) AS itm_back,
                CAST(ISNULL(sd.itm_back_price, 0) AS DECIMAL(38,6)) AS itm_back_price,
                CAST(ISNULL(sd.itm_aver_cost, 0) AS DECIMAL(38,6)) AS itm_aver_cost,
                CAST(ISNULL(ic.itm_def_sell_price, 0) AS DECIMAL(38,6)) AS itm_def_sell_price,
                CAST(ISNULL(ic.itm_unit1_unit2, 1) AS DECIMAL(38,6)) AS itm_unit1_unit2,
                CAST(ISNULL(ic.itm_unit1_unit3, 1) AS DECIMAL(38,6)) AS itm_unit1_unit3,
                h.sto_id
            FROM sales_trans_d sd
            JOIN item_catalog ic ON sd.itm_id = ic.itm_id
            JOIN sales_trans_h h ON h.sth_id = sd.sth_id
            WHERE sd.itm_back > 0
              AND sd.itm_unit = 1
              AND ISNULL(sd.std_r_itm_stock, 11) = 11
              AND ISNULL(sd.std_r_itm_unit1_unit2, 1) = 1
              AND ISNULL(sd.std_r_itm_unit1_unit3, 1) = 1
              AND ISNULL(ic.itm_unit1_unit3, 1) <> 1
              AND ISNULL(sd.itm_sell, 0) <> 0
              AND (ISNULL(ic.itm_def_sell_price, 0) / NULLIF(sd.itm_sell, 0)) > 1.8
        """

        stock_rows_sql = f"""
            SELECT
                c_id,
                CAST(ISNULL(itm_qty, 0) AS DECIMAL(38,6)) AS itm_qty
            FROM item_class_store WITH (READPAST)
            WHERE itm_id = {PARAM_STR}
              AND sto_id = {PARAM_STR}
            ORDER BY c_id
        """

        update_stock_row_sql = f"""
            UPDATE Item_Class_Store WITH (ROWLOCK)
               SET itm_qty = itm_qty - {PARAM_STR},
                   sec_update_uid = {PARAM_STR},
                   sec_update_date = GETDATE()
             WHERE itm_id = {PARAM_STR}
               AND c_id = {PARAM_STR}
               AND sto_id = {PARAM_STR}
               AND itm_qty - {PARAM_STR} >= 0
        """

        stock_sum_sql = f"""
            SELECT CAST(ISNULL(SUM(itm_qty), 0) AS DECIMAL(38,6))
            FROM item_class_store
            WHERE itm_id = {PARAM_STR}
              AND sto_id = {PARAM_STR}
        """

        update_sd_sql = f"""
            UPDATE sales_trans_d
               SET itm_unit = 3,
                   col1 = CASE
                              WHEN ISNULL(col1, '') = '' THEN {PARAM_STR}
                              ELSE col1 + ' | ' + {PARAM_STR}
                          END,
                   sec_update_uid = {PARAM_STR},
                   sec_update_date = GETDATE(),
                   std_r_itm_purchase_unit = 1,
                   std_r_itm_unit1_unit2 = {PARAM_STR},
                   std_r_itm_unit1_unit3 = {PARAM_STR},
                   std_r_itm_stock = {PARAM_STR}
             WHERE sth_id = {PARAM_STR}
               AND itm_id = {PARAM_STR}
               AND c_id = {PARAM_STR}
               AND std_id = {PARAM_STR}
        """

        summary = {
            "dry_run": dry_run,
            "employee_id": emp_id,
            "stores": [],
            "total_candidates": 0,
            "total_fixed_rows": 0,
            "total_qty_correction_small": 0.0,
        }

        for store in stores:
            store_summary = {
                "store_id": int(store.id),
                "store_code": store.code or "",
                "store_name": store.display_name or "",
                "candidates": 0,
                "fixed_rows": 0,
                "skipped_rows": 0,
                "qty_correction_small": 0.0,
                "sample_rows": [],
            }
            try:
                with self.connect_eplus(
                        server=store.ip1,
                        autocommit=False,
                        charset="UTF-8",
                        param_str=PARAM_STR,
                ) as conn:
                    cur = conn.cursor()
                    cur.execute("SET DEADLOCK_PRIORITY LOW")
                    cur.execute("SET LOCK_TIMEOUT 2000")
                    sql = detect_sql
                    params = []
                    if parsed_header_ids:
                        placeholders = ",".join([PARAM_STR] * len(parsed_header_ids))
                        sql += f" AND sd.sth_id IN ({placeholders})"
                        params.extend(parsed_header_ids)
                    sql += " ORDER BY sd.sth_id, sd.std_id"
                    cur.execute(sql, tuple(params))
                    rows = list(cur.fetchall() or [])
                    if limit > 0:
                        rows = rows[:limit]

                    store_summary["candidates"] = len(rows)
                    summary["total_candidates"] += len(rows)

                    for row in rows:
                        std_id = int(row[0] or 0)
                        sth_id = int(row[1] or 0)
                        itm_id = int(row[2] or 0)
                        c_id = int(row[3] or 0)
                        itm_back = float(row[10] or 0.0)
                        unit12 = float(row[14] or 1.0)
                        unit13 = float(row[15] or 1.0)
                        sto_id = int(row[16] or 0)
                        if not sto_id:
                            sto_id = int(store.eplus_serial or 0)

                        if itm_back <= 0 or unit13 <= 1:
                            continue

                        # Old buggy behavior added itm_back * unit13 to stock while
                        # itm_back was already in small unit, so over-add is:
                        over_added_small = itm_back * (unit13 - 1.0)
                        if over_added_small <= 0:
                            continue

                        if not dry_run:
                            try:
                                cur.execute(stock_rows_sql, (itm_id, sto_id))
                                stock_rows = list(cur.fetchall() or [])
                                wrong_itm_qty = sum(float((sr[1] or 0.0)) for sr in stock_rows)
                                corrected_itm_qty = wrong_itm_qty - over_added_small
                                backup_text = (
                                    f"wrong_itm_qty={wrong_itm_qty:.6f}; "
                                    f"corrected_itm_qty={corrected_itm_qty:.6f}"
                                )

                                max_removable = 0.0
                                for sr in stock_rows:
                                    row_qty = float((sr[1] or 0.0))
                                    max_removable += max(0.0, row_qty)

                                if max_removable + 1e-6 < over_added_small:
                                    store_summary["skipped_rows"] += 1
                                    if len(store_summary["sample_rows"]) < 20:
                                        store_summary["sample_rows"].append(
                                            {
                                                "sth_id": sth_id,
                                                "std_id": std_id,
                                                "itm_id": itm_id,
                                                "c_id": c_id,
                                                "itm_back": itm_back,
                                                "unit1_unit3": unit13,
                                                "over_added_small": over_added_small,
                                                "skipped": True,
                                                "reason": "insufficient_nonnegative_capacity",
                                            }
                                        )
                                    continue

                                cur.execute("SAVE TRANSACTION ab_uom_fix_row")
                                remain_to_subtract = float(over_added_small)
                                failed_nonnegative_guard = False
                                for sr in stock_rows:
                                    if remain_to_subtract <= 1e-6:
                                        break

                                    row_c_id = int(sr[0] or 0)
                                    row_qty = float(sr[1] or 0.0)
                                    row_capacity = max(0.0, row_qty)
                                    if row_capacity <= 1e-9:
                                        continue

                                    row_take = min(remain_to_subtract, row_capacity)
                                    if row_take <= 1e-9:
                                        continue

                                    cur.execute(
                                        update_stock_row_sql,
                                        (
                                            row_take,
                                            emp_id,
                                            itm_id,
                                            row_c_id,
                                            sto_id,
                                            row_take,
                                        ),
                                    )
                                    if int(cur.rowcount or 0) <= 0:
                                        failed_nonnegative_guard = True
                                        break
                                    remain_to_subtract -= row_take

                                if failed_nonnegative_guard or remain_to_subtract > 1e-4:
                                    cur.execute("ROLLBACK TRANSACTION ab_uom_fix_row")
                                    store_summary["skipped_rows"] += 1
                                    if len(store_summary["sample_rows"]) < 20:
                                        store_summary["sample_rows"].append(
                                            {
                                                "sth_id": sth_id,
                                                "std_id": std_id,
                                                "itm_id": itm_id,
                                                "c_id": c_id,
                                                "itm_back": itm_back,
                                                "unit1_unit3": unit13,
                                                "over_added_small": over_added_small,
                                                "skipped": True,
                                                "reason": "nonnegative_guard_or_partial_subtract",
                                            }
                                        )
                                    continue

                                cur.execute(stock_sum_sql, (itm_id, sto_id))
                                stock_total = float((cur.fetchone() or [0.0])[0] or 0.0)
                                cur.execute(
                                    update_sd_sql,
                                    (
                                        backup_text,
                                        backup_text,
                                        emp_id,
                                        unit12,
                                        unit13,
                                        stock_total,
                                        sth_id,
                                        itm_id,
                                        c_id,
                                        std_id,
                                    ),
                                )

                                conn.commit()
                            except Exception as row_ex:
                                try:
                                    conn.rollback()
                                except Exception:
                                    pass
                                store_summary["skipped_rows"] += 1
                                if len(store_summary["sample_rows"]) < 20:
                                    store_summary["sample_rows"].append(
                                        {
                                            "sth_id": sth_id,
                                            "std_id": std_id,
                                            "itm_id": itm_id,
                                            "c_id": c_id,
                                            "itm_back": itm_back,
                                            "unit1_unit3": unit13,
                                            "over_added_small": over_added_small,
                                            "skipped": True,
                                            "reason": "row_exception",
                                            "error": repr(row_ex),
                                        }
                                    )
                                continue

                        store_summary["fixed_rows"] += 1
                        store_summary["qty_correction_small"] += over_added_small
                        if len(store_summary["sample_rows"]) < 20:
                            store_summary["sample_rows"].append(
                                {
                                    "sth_id": sth_id,
                                    "std_id": std_id,
                                    "itm_id": itm_id,
                                    "c_id": c_id,
                                    "itm_back": itm_back,
                                    "unit1_unit3": unit13,
                                    "over_added_small": over_added_small,
                                }
                            )

                    if dry_run:
                        conn.rollback()
                    else:
                        conn.commit()

            except Exception as ex:
                if not dry_run:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                store_summary["error"] = repr(ex)

            summary["stores"].append(store_summary)
            summary["total_fixed_rows"] += int(store_summary["fixed_rows"])
            summary["total_qty_correction_small"] += float(store_summary["qty_correction_small"])

        return summary
