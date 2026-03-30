# -*- coding: utf-8 -*-
import math
from time import perf_counter

from odoo import api, models, _
from odoo.exceptions import UserError

PARAM_STR = "?"


class AbSalesPosBalanceRefresh(models.TransientModel):
    _name = 'ab_sales_pos_api'
    _inherit = ["ab_sales_pos_api", "ab_eplus_connect"]

    def _get_store_record(self, store_id):
        if not store_id:
            raise UserError(_("Store is required."))
        store = self.env["ab_store"].browse(int(store_id)).exists()
        if not store:
            raise UserError(_("Invalid store."))
        if not store.ip1:
            raise UserError(_("No IP for this store."))
        return store

    @api.model
    def pos_refresh_pos_balances(self, store_id=None, product_ids=None):
        self._require_models("ab_product", "ab_sales_inventory", "ab_store")
        store = self._get_store_record(store_id)
        try:
            store_eplus_serial = int(store.eplus_serial or 0)
        except Exception:
            store_eplus_serial = 0
        if not store_eplus_serial:
            raise UserError(_("Store is missing E-Plus serial."))

        prod_ids = []
        for pid in product_ids or []:
            try:
                pid = int(pid)
            except Exception:
                pid = 0
            if pid:
                prod_ids.append(pid)
        prod_ids = list(dict.fromkeys(prod_ids))
        if not prod_ids:
            return {}

        products = self.env["ab_product"].browse(prod_ids).read(["id", "eplus_serial"])
        prod_by_serial = {}
        serials = []
        for row in products:
            serial = row.get("eplus_serial")
            try:
                serial = int(serial or 0)
            except Exception:
                serial = 0
            if not serial:
                continue
            prod_by_serial.setdefault(serial, []).append(int(row["id"]))
            serials.append(serial)

        serials = sorted(set(serials))
        if not serials:
            return {}

        balances_by_serial = {serial: 0.0 for serial in serials}
        prices_by_serial = {}

        try:
            with self.connect_eplus(
                    server=store.ip1,
                    param_str=PARAM_STR,
                    charset="CP1256",
            ) as conn:
                with conn.cursor() as crx:
                    placeholders = ",".join([PARAM_STR] * len(serials))
                    price_sql = f"""
                        SELECT itm_id, itm_def_sell_price
                        FROM item_catalog WITH (NOLOCK)
                        WHERE itm_id IN ({placeholders})
                    """
                    crx.execute(price_sql, tuple(serials))
                    for row in crx.fetchall():
                        try:
                            prod_serial = int(row[0])
                            price = float(row[1] or 0.0)
                        except Exception:
                            continue
                        prices_by_serial[prod_serial] = price

                    sql = f"""
                        SELECT
                            main.itm_id AS product_eplus_serial,
                            SUM(CAST(main.itm_qty / ic.itm_unit1_unit3 AS decimal(18, 2))) AS balance
                        FROM Item_Class_Store main WITH (NOLOCK)
                        JOIN item_catalog ic WITH (NOLOCK) ON main.itm_id = ic.itm_id
                        WHERE ic.itm_active = 1
                          AND main.sto_id = {PARAM_STR}
                          AND main.itm_id IN ({placeholders})
                        GROUP BY main.itm_id
                        HAVING SUM(CAST(main.itm_qty / ic.itm_unit1_unit3 AS decimal(18, 2))) > 0
                    """
                    params = [store_eplus_serial] + serials
                    crx.execute(sql, tuple(params))
                    rows = crx.fetchall()
                    for row in rows:
                        try:
                            prod_serial = int(row[0])
                            balance = float(row[1] or 0.0)
                        except Exception:
                            continue
                        if prod_serial in balances_by_serial:
                            balances_by_serial[prod_serial] = balance
        except Exception:
            return {}

        Inventory = self.env["ab_sales_inventory"].sudo()
        existing = Inventory.search([
            ("store_id", "=", store.id),
            ("product_eplus_serial", "in", serials),
        ])
        existing_by_serial = {int(line.product_eplus_serial): line for line in existing}

        to_create = []
        for serial in serials:
            balance = float(balances_by_serial.get(serial, 0.0) or 0.0)
            new_price = prices_by_serial.get(serial)
            line = existing_by_serial.get(serial)
            if line:
                vals = {}
                if not math.isclose(balance, line.balance or 0.0, abs_tol=0.01):
                    vals["balance"] = balance
                if new_price is not None:
                    try:
                        curr_price = float(line.default_price or 0.0)
                    except Exception:
                        curr_price = 0.0
                    if not math.isclose(new_price, curr_price, abs_tol=0.01):
                        vals["default_price"] = new_price
                if vals:
                    line.write(vals)
            else:
                create_vals = {
                    "product_eplus_serial": serial,
                    "store_id": store.id,
                    "balance": balance,
                }
                if new_price is not None:
                    create_vals["default_price"] = new_price
                to_create.append(create_vals)
        if to_create:
            Inventory.create(to_create)

        result = {}
        for serial, balance in balances_by_serial.items():
            for prod_id in prod_by_serial.get(serial, []):
                result[prod_id] = balance
        return result
