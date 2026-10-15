# -*- coding: utf-8 -*-
import math
import logging
from time import perf_counter

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from psycopg2 import errors
from .ab_sales_inventory import InventorySyncBusy

PARAM_STR = "?"
_logger = logging.getLogger(__name__)


class AbSalesPosBalanceRefresh(models.TransientModel):
    _name = 'ab_sales_pos_api'
    _inherit = ["ab_sales_pos_api", "ab_eplus_connect"]

    def _get_store_record(self, store_id):
        if not store_id:
            raise UserError(_("Store is required."))
        store = self.env["ab_store"].browse(int(store_id)).exists()
        if not store:
            raise UserError(_("Invalid store."))
        store.check_access("read")
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

        Inventory = self.env["ab_sales_inventory"].sudo()

        def result(success):
            if not include_sync_metadata and not success:
                return {}
            metadata = Inventory._branch_sync_metadata(store, serials)
            output = {}
            for serial, ids in prod_by_serial.items():
                cached = metadata.get(serial)
                for pid in ids:
                    if include_sync_metadata:
                        output[pid] = {**(cached or {'balance': None, 'last_sync_at': False}),
                                       'refresh_success': success}
                    elif cached:
                        output[pid] = cached['balance']
            return output

        if store_eplus_serial <= 0:
            return result(False)
        sync_at = fields.Datetime.now()
        completed = False
        committed_read = self.env.context.get('_ab_sales_backend_committed_read') is True
        balances_by_serial = {serial: 0.0 for serial in serials}
        prices_by_serial = {}
        started = perf_counter()
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
                        FROM item_catalog WITH (NOLOCK)
                        WHERE itm_id IN ({placeholders})
                    """
                    if committed_read:
                        price_sql = price_sql.replace(' WITH (NOLOCK)', '').replace(
                            'WHERE itm_id IN', 'WHERE itm_active = 1 AND itm_unit1_unit3 > 0 AND itm_id IN')
                    crx.execute(price_sql, tuple(serials))
                    for row in crx.fetchall():
                        if len(row) != 2 or isinstance(row[0], bool) or int(row[0]) != row[0]:
                            raise ValueError("Invalid E-Plus row")
                        prod_serial = int(row[0])
                        price = float(row[1])
                        if (prod_serial not in balances_by_serial or prod_serial in prices_by_serial
                                or not math.isfinite(price) or price < 0):
                            raise ValueError("Invalid E-Plus price result")
                        prices_by_serial[prod_serial] = price
                    if set(prices_by_serial) != set(serials):
                        raise ValueError("Incomplete E-Plus price result")

                    # Informational POS snapshot only: preserve the existing
                    # NOLOCK read policy, not a stock reservation or sale check.
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
                    if committed_read:
                        sql = sql.replace(' WITH (NOLOCK)', '')
                    params = [store_eplus_serial] + serials
                    crx.execute(sql, tuple(params))
                    rows = crx.fetchall()
                    seen = set()
                    for row in rows:
                        if len(row) != 2 or isinstance(row[0], bool) or int(row[0]) != row[0]:
                            raise ValueError("Invalid E-Plus row")
                        prod_serial = int(row[0])
                        balance = float(row[1])
                        if (prod_serial not in balances_by_serial or prod_serial in seen
                                or not math.isfinite(balance) or balance < 0):
                            raise ValueError("Invalid E-Plus stock result")
                        seen.add(prod_serial)
                        balances_by_serial[prod_serial] = balance
                    completed = True
            if not completed:
                raise ValueError("Incomplete E-Plus snapshot")
        except (AccessError, errors.SerializationFailure, errors.DeadlockDetected):
            raise
        except Exception:
            _logger.warning("POS balance refresh unavailable for store %s (%s products, %.2fs)",
                            store.id, len(prod_ids), perf_counter() - started)
            return result(False)

        try:
            Inventory._apply_store_balance_rows(
                store, store_eplus_serial,
                [(serial, store_eplus_serial, balance) for serial, balance in balances_by_serial.items()],
                sync_at, requested_serials=serials, prices=prices_by_serial)
        except (AccessError, errors.SerializationFailure, errors.DeadlockDetected):
            # Odoo must retry the entire transaction with a fresh snapshot.
            raise
        except (InventorySyncBusy, errors.UniqueViolation, errors.LockNotAvailable):
            _logger.info("POS inventory cache busy for store %s", store.id)
            return result(False)
        return result(True)
