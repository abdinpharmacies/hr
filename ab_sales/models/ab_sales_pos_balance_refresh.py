# -*- coding: utf-8 -*-
import math
import logging
from time import perf_counter

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ConcurrencyError, UserError
from psycopg2.errors import SerializationFailure, DeadlockDetected

PARAM_STR = "?"
_logger = logging.getLogger(__name__)


class AbSalesPosBalanceRefresh(models.TransientModel):
    _name = 'ab_sales_pos_api'
    _inherit = ["ab_sales_pos_api", "ab_sales_external_connector"]

    def _get_store_record(self, store_id):
        if not store_id:
            raise UserError(_("Store is required."))
        store = self.env["ab_store"].browse(int(store_id)).exists()
        if not store:
            raise UserError(_("Invalid store."))
        store.check_access("read")
        self.env['ab_sales_header'].check_access('read')
        if not (self.env.su or self.env.user.has_group('base.group_system')
                or self.env.user.has_group('ab_sales.group_ab_sales_manager')):
            allowed = self.env['ab_sales_header']._get_allowed_store_ids()
            user = self.env.user.sudo()
            assigned = (user.ab_department_ids | user.ab_employee_ids.department_id).store_id
            if store.id not in allowed or (assigned and store not in assigned):
                raise AccessError(_("The selected store is not in the replica Allowed Sales Stores."))
        return store

    def _get_store_server(self, store):
        target_ip = store.ip1
        replica_db = self.env["ab_replica_db"].sudo().get_current_from_config()
        if (
            replica_db
            and replica_db.default_sales_store_id
            and replica_db.default_sales_store_id.id == store.id
        ):
            target_ip = "192.168.1.150"
        if not target_ip:
            raise UserError(_("No IP for this store."))
        return target_ip

    @api.model
    def pos_refresh_pos_balances(self, store_id=None, product_ids=None, include_sync_metadata=False):
        self._require_models("ab_product", "ab_sales_inventory", "ab_store")
        store = self._get_store_record(store_id)
        try:
            store_eplus_serial = int(store.eplus_serial or 0)
        except Exception:
            store_eplus_serial = 0

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
        serials = []
        for row in products:
            serial = row.get("eplus_serial")
            try:
                serial = int(serial or 0)
            except Exception:
                serial = 0
            if not serial:
                continue
            serials.append(serial)

        serials = sorted(set(serials))
        Inventory = self.env["ab_sales_inventory"].sudo()

        def cached_result(success):
            if not include_sync_metadata and not success:
                return {}
            cached = Inventory.search(fields.Domain('store_id', '=', store.id)
                                      & fields.Domain('product_eplus_serial', 'in', serials))
            by_serial = {line.product_eplus_serial: line for line in cached}
            result = {}
            for product in products:
                line = by_serial.get(int(product.get('eplus_serial') or 0))
                if include_sync_metadata:
                    result[product['id']] = {
                        'balance': line.balance if line else None,
                        'last_sync_at': fields.Datetime.to_string(line.last_sync_at) if line and line.last_sync_at else False,
                        'refresh_success': bool(success and line),
                    }
                elif line:
                    result[product['id']] = line.balance
            return result

        if not serials or not store_eplus_serial:
            return cached_result(False)

        balances_by_serial = {serial: 0.0 for serial in serials}
        prices_by_serial = {}
        started = perf_counter()
        sync_at = fields.Datetime.now()
        try:
            store_server = self._get_store_server(store)
            with self._connect_pos_balance_read(
                    server=store_server,
                    param_str=PARAM_STR,
                    charset="CP1256",
            ) as conn:
                with conn.cursor() as crx:
                    placeholders = ",".join([PARAM_STR] * len(serials))
                    price_sql = f"""
                        SELECT itm_id, itm_def_sell_price
                        FROM item_catalog
                        WHERE itm_active = 1 AND itm_unit1_unit3 > 0 AND itm_id IN ({placeholders})
                    """
                    crx.execute(price_sql, tuple(serials))
                    for row in crx.fetchall():
                        if len(row) != 2 or isinstance(row[0], bool) or int(row[0]) != row[0]:
                            raise ValueError("Invalid E-Plus row")
                        prod_serial = int(row[0])
                        price = float(row[1])
                        if (prod_serial != row[0] or prod_serial not in balances_by_serial or prod_serial in prices_by_serial
                                or not math.isfinite(price) or price < 0):
                            raise ValueError("Invalid E-Plus price result")
                        prices_by_serial[prod_serial] = price
                    if set(prices_by_serial) != set(serials):
                        raise ValueError("Incomplete E-Plus price result")

                    sql = f"""
                        SELECT
                            main.itm_id AS product_eplus_serial,
                            CASE WHEN COUNT(main.itm_qty) = COUNT(*) AND MIN(ic.itm_unit1_unit3) > 0
                                 THEN SUM(CAST(CAST(main.itm_qty AS decimal(28, 8)) /
                                     NULLIF(ic.itm_unit1_unit3, 0) AS decimal(18, 2)))
                                 ELSE NULL END AS balance
                        FROM Item_Class_Store main
                        JOIN item_catalog ic ON main.itm_id = ic.itm_id
                        WHERE ic.itm_active = 1
                          AND main.sto_id = {PARAM_STR}
                          AND main.itm_id IN ({placeholders})
                        GROUP BY main.itm_id
                    """
                    params = [store_eplus_serial] + serials
                    crx.execute(sql, tuple(params))
                    rows = crx.fetchall()
                    seen = set()
                    for row in rows:
                        if len(row) != 2 or isinstance(row[0], bool) or int(row[0]) != row[0]:
                            raise ValueError("Invalid E-Plus row")
                        prod_serial = int(row[0])
                        balance = float(row[1])
                        if (prod_serial != row[0] or prod_serial not in balances_by_serial or prod_serial in seen
                                or not math.isfinite(balance) or balance < 0):
                            raise ValueError("Invalid E-Plus stock result")
                        seen.add(prod_serial)
                        balances_by_serial[prod_serial] = balance
            rows = [(serial, store_eplus_serial, balance) for serial, balance in balances_by_serial.items()]
            Inventory._apply_store_balance_rows(
                store, store_eplus_serial, rows, sync_at, product_serials=serials, prices=prices_by_serial)
        except (AccessError, SerializationFailure, DeadlockDetected, ConcurrencyError):
            raise
        except Exception:
            _logger.warning("POS balance refresh unavailable for store %s (%s products, %.2fs)",
                            store.id, len(prod_ids), perf_counter() - started)
            return cached_result(False)
        return cached_result(True)
