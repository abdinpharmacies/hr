import math

from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import UserError
from .ab_sales_header import PARAM_STR
import logging

_logger = logging.getLogger(__name__)
DEFAULT_STORE_DIRECT_SERVER = "192.168.1.150"

SQL_TOTAL = """
            SELECT main.itm_id                                                    AS product_eplus_serial,
                   SUM(CAST(main.itm_qty / ic.itm_unit1_unit3 AS decimal(18, 2))) AS balance
            FROM Item_Class_Store main WITH (NOLOCK)
        JOIN item_catalog ic
            WITH (NOLOCK)
            ON main.itm_id = ic.itm_id
                JOIN Store s on s.sto_id = main.sto_id
            WHERE ic.itm_active=1 and main.sto_id in ({store_placeholders})
            GROUP BY main.itm_id
            HAVING SUM (CAST (main.itm_qty/ic.itm_unit1_unit3 AS decimal (18, 2))) > 0
            ORDER BY main.itm_id, balance desc -- order by sec_insert_date desc    \
            """

SQL_PER_POS = """
              SELECT main.itm_id                                                    AS product_eplus_serial,
                     main.sto_id                                                    AS store_eplus_serial,
                     SUM(CAST(main.itm_qty / ic.itm_unit1_unit3 AS decimal(18, 2))) AS balance
              FROM Item_Class_Store main WITH (NOLOCK)
        JOIN item_catalog ic
              WITH (NOLOCK)
              ON main.itm_id = ic.itm_id
                  JOIN Store s on s.sto_id = main.sto_id
              WHERE ic.itm_active = 1 and main.sto_id in ({store_placeholders})
              GROUP BY main.itm_id, main.sto_id
              HAVING SUM (CAST (main.itm_qty / ic.itm_unit1_unit3 AS decimal (18, 2))) > 0
              ORDER BY main.itm_id, main.sto_id, balance desc -- order by sec_insert_date desc   \
              """


class InventoryEplus(models.Model):
    _name = 'ab_sales_inventory'
    _inherit = ['ab_eplus_connect']
    _description = 'ab_sales_inventory'

    product_eplus_serial = fields.Integer(index=True)
    product_id = fields.Many2one('ab_product', index=True, readonly=True)
    product_code = fields.Char(index=True, readonly=True)
    store_id = fields.Many2one('ab_store', index=True)
    balance = fields.Float()
    default_price = fields.Float()

    def init(self):
        super().init()
        # Speed up POS balance lookups used by the product search modal.
        self.env.cr.execute("""
                            CREATE INDEX IF NOT EXISTS ab_sales_inventory_store_prod_pos_bal_idx
                                ON ab_sales_inventory (store_id, product_eplus_serial)
                                WHERE store_id IS NOT NULL AND balance > 0
                            """)
        self.env.cr.execute("""
                            CREATE INDEX IF NOT EXISTS ab_sales_inventory_prod_global_bal_idx
                                ON ab_sales_inventory (product_eplus_serial)
                                WHERE store_id IS NULL AND balance > 0
                            """)
        self.env.cr.execute("""
                            CREATE INDEX IF NOT EXISTS ab_sales_inventory_prod_store_sum_idx
                                ON ab_sales_inventory (product_eplus_serial)
                                WHERE store_id IS NOT NULL AND balance != 0
                            """)
        self.env.cr.execute("""
                            CREATE INDEX IF NOT EXISTS ab_sales_inventory_product_store_bal_idx
                                ON ab_sales_inventory (product_id, store_id)
                                WHERE product_id IS NOT NULL AND balance > 0
                            """)
        self.env.cr.execute("""
                            CREATE INDEX IF NOT EXISTS ab_sales_inventory_store_product_bal_idx
                                ON ab_sales_inventory (store_id, product_id)
                                WHERE product_id IS NOT NULL AND balance > 0
                            """)
        self.env.cr.execute("""
                            CREATE INDEX IF NOT EXISTS ab_sales_inventory_product_code_idx
                                ON ab_sales_inventory (product_code)
                                WHERE product_code IS NOT NULL
                            """)

    @api.model
    def _product_lookup_by_eplus_serial(self, product_serials):
        serials = sorted({
            int(serial)
            for serial in product_serials
            if serial
        })
        if not serials:
            return {}

        products = self.env['ab_product'].with_context(active_test=False).search(
            [('eplus_serial', 'in', serials)],
            order='eplus_serial, active desc, id',
        )
        products_by_serial = {}
        for product in products:
            serial = int(product.eplus_serial or 0)
            if serial and serial not in products_by_serial:
                products_by_serial[serial] = product
        return products_by_serial

    @api.model
    def _product_sync_vals(self, product_serial, products_by_serial):
        product = products_by_serial.get(int(product_serial or 0))
        if not product:
            return {
                'product_id': False,
                'product_code': False,
            }
        return {
            'product_id': product.id,
            'product_code': product.code or False,
        }

    @api.model
    def _needs_product_sync(self, inventory_lines, product_vals):
        target_product_id = product_vals.get('product_id') or False
        target_product_code = product_vals.get('product_code') or False
        return any(
            line.product_id.id != target_product_id
            or (line.product_code or False) != target_product_code
            for line in inventory_lines
        )

    def _resync_empty_product_fields(self, domain):
        inventory_lines = self.search(
            list(domain or []) + [
                ('product_eplus_serial', '!=', False),
                '|',
                ('product_id', '=', False),
                ('product_code', '=', False),
            ]
        )
        if not inventory_lines:
            return 0

        products_by_serial = self._product_lookup_by_eplus_serial(
            inventory_lines.mapped('product_eplus_serial')
        )
        buckets = {}
        for line in inventory_lines:
            product_vals = self._product_sync_vals(line.product_eplus_serial, products_by_serial)
            if not self._needs_product_sync(line, product_vals):
                continue
            key = (
                product_vals.get('product_id') or False,
                product_vals.get('product_code') or False,
            )
            buckets.setdefault(key, self.browse())
            buckets[key] = buckets[key] | line

        updated_count = 0
        for (product_id, product_code), lines in buckets.items():
            lines.write({
                'product_id': product_id,
                'product_code': product_code,
            })
            updated_count += len(lines)
        return updated_count

    @api.model
    def _chunks(self, seq, size):
        for i in range(0, len(seq), size):
            yield seq[i:i + size]

    @api.model
    def _get_default_sales_store(self):
        replica_db = self.env["ab_replica_db"].sudo().get_current_from_config()
        return replica_db.default_sales_store_id if replica_db and replica_db.default_sales_store_id else self.env["ab_store"]

    @api.model
    def _store_eplus_serial(self, store):
        try:
            return int(store.eplus_serial or 0)
        except Exception:
            return 0

    @api.model
    def _get_working_balance_store_pairs(self, exclude_default=False, default_store=None):
        stores = self.env['ab_store'].sudo().search([('has_working_balance', '=', True)])
        if default_store is None:
            default_store = self._get_default_sales_store() if exclude_default else self.env["ab_store"]
        store_pairs = []
        for store in stores:
            if default_store and store.id == default_store.id:
                continue
            store_eplus_serial = self._store_eplus_serial(store)
            if store_eplus_serial:
                store_pairs.append((store, store_eplus_serial))
        return store_pairs

    @api.model
    def _get_default_sales_store_direct_server(self, store):
        if not store:
            return False
        # Existing POS store-connection helpers route the local/default store through this direct server.
        return DEFAULT_STORE_DIRECT_SERVER

    @api.model
    def _apply_store_balance_rows(self, store, store_eplus_serial, rows):
        eInv = self.sudo()
        eInv.search([('store_id', '=', store.id)]).write({'balance': 0})

        balances_by_product = {}
        for prod_eplus_ser, row_store_eplus_ser, balance in rows or []:
            try:
                prod_eplus_ser = int(prod_eplus_ser)
                row_store_eplus_ser = int(row_store_eplus_ser)
                balance = float(balance or 0.0)
            except Exception:
                continue

            if row_store_eplus_ser != store_eplus_serial:
                continue
            if balance <= 0.0:
                continue
            balances_by_product[prod_eplus_ser] = balance

        product_serials = sorted(balances_by_product.keys())
        products_by_serial = eInv._product_lookup_by_eplus_serial(product_serials)
        existing_by_product = {}
        for prod_chunk in self._chunks(product_serials, 1000):
            existing_lines = eInv.search([
                ('store_id', '=', store.id),
                ('product_eplus_serial', 'in', prod_chunk),
            ])
            for line in existing_lines:
                existing_by_product[int(line.product_eplus_serial)] = line

        created_vals = []
        updated_count = 0
        for prod_eplus_ser, balance in balances_by_product.items():
            inv_line = existing_by_product.get(prod_eplus_ser)
            product_vals = eInv._product_sync_vals(prod_eplus_ser, products_by_serial)
            if not inv_line:
                created_vals.append({
                    'product_eplus_serial': prod_eplus_ser,
                    'store_id': store.id,
                    'balance': balance,
                    **product_vals,
                })
                continue

            write_vals = {}
            if not math.isclose(balance, inv_line.balance, abs_tol=0.01):
                write_vals['balance'] = balance
            if eInv._needs_product_sync(inv_line, product_vals):
                write_vals.update(product_vals)
            if write_vals:
                inv_line.write(write_vals)
                updated_count += 1

        if created_vals:
            eInv.create(created_vals)
        product_resynced_count = eInv._resync_empty_product_fields([
            ('store_id', '=', store.id),
        ])
        return {
            "product_count": len(product_serials),
            "created_count": len(created_vals),
            "updated_count": updated_count,
            "product_resynced_count": product_resynced_count,
        }

    def btn_update_balance_total(self):
        eInv = self.env['ab_sales_inventory'].sudo()

        stores = self.env['ab_store'].sudo().search([('has_working_balance', '=', True)])
        store_eplus_serials = [int(x) for x in stores.mapped('eplus_serial') if x]
        has_bal_list = []
        try:
            if not store_eplus_serials:
                eInv.search([]).write({'balance': 0})
                eInv._resync_empty_product_fields([])
                return

            with self.connect_eplus(param_str=PARAM_STR, charset='CP1256') as conn:
                with conn.cursor() as crx:
                    totals_by_product = {}
                    # SQL Server has a 2100-parameter limit; keep some margin.
                    for store_chunk in self._chunks(store_eplus_serials, 2000):
                        store_placeholders = ",".join([PARAM_STR] * len(store_chunk))
                        sql = SQL_TOTAL.format(store_placeholders=store_placeholders)
                        crx.execute(sql, tuple(store_chunk))
                        chunk_rows = crx.fetchall()  # [(prod_eplus_ser, balance)]
                        for prod_eplus_ser, balance in chunk_rows:
                            totals_by_product[int(prod_eplus_ser)] = (
                                    float(totals_by_product.get(int(prod_eplus_ser), 0.0)) + float(balance or 0.0)
                            )

                    rows = sorted(totals_by_product.items(), key=lambda r: r[0])
                    products_by_serial = eInv._product_lookup_by_eplus_serial(
                        prod_eplus_ser for prod_eplus_ser, _balance in rows
                    )
                    i = 1
                    for j, (prod_eplus_ser, balance) in enumerate(rows, 1):
                        if j % 1000 == 0:
                            _logger.info(f"######### Line {i * j}")
                            i += 1

                        # do not nullify has_bal_list
                        has_bal_list.append(prod_eplus_ser)

                        inv_lines = eInv.search([
                            ('product_eplus_serial', '=', prod_eplus_ser),
                            ('store_id', '=', False),
                        ])
                        product_vals = eInv._product_sync_vals(prod_eplus_ser, products_by_serial)
                        if not inv_lines:
                            inv_lines = eInv.create({
                                'product_eplus_serial': prod_eplus_ser,
                                'store_id': False,
                                'balance': balance,
                                **product_vals,
                            })

                        balances = inv_lines.mapped('balance')
                        write_vals = {}
                        if any(not math.isclose(balance, b, abs_tol=0.01) for b in balances):
                            write_vals['balance'] = balance
                        if eInv._needs_product_sync(inv_lines, product_vals):
                            write_vals.update(product_vals)
                        if write_vals:
                            inv_lines.write(write_vals)

                    self.search([
                        ('product_eplus_serial', 'not in', has_bal_list),
                        ('store_id', '=', False),
                    ]).write({'balance': 0})
                    eInv._resync_empty_product_fields([('store_id', '=', False)])
        except Exception as ex:
            _logger.error(repr(ex))

    def btn_update_balance_per_pos(self):
        """
        Update remote-store balances into ab_sales_inventory(store_id, product_eplus_serial).
        When a default sales store is configured, it is refreshed by
        btn_update_balance_default_sales_store() through the direct store connection.
        If a store has no products, its balances are set to 0.
        """
        eInv = self.env['ab_sales_inventory'].sudo()

        default_store = self._get_default_sales_store()
        store_pairs = self._get_working_balance_store_pairs(exclude_default=bool(default_store))

        if not store_pairs:
            if not default_store:
                eInv.search([('store_id', '!=', False)]).write({'balance': 0})
                eInv._resync_empty_product_fields([('store_id', '!=', False)])
            _logger.info("Inventory remote per-store sync skipped: no remote working stores.")
            return

        try:
            with self.connect_eplus(param_str=PARAM_STR, charset='CP1256') as conn:
                with conn.cursor() as crx:
                    for store, store_eplus_serial in store_pairs:
                        try:
                            _logger.info(
                                "Inventory remote per-store sync started: %s (eplus=%s)",
                                store.display_name, store_eplus_serial
                            )

                            sql = SQL_PER_POS.format(store_placeholders=PARAM_STR)
                            crx.execute(sql, (store_eplus_serial,))
                            rows = crx.fetchall()  # [(prod_eplus_ser, store_eplus_ser, balance)]

                            stats = eInv._apply_store_balance_rows(store, store_eplus_serial, rows)

                            _logger.info(
                                "Inventory remote per-store sync finished: %s (eplus=%s) products=%s created=%s updated=%s product_resynced=%s",
                                store.display_name,
                                store_eplus_serial,
                                stats["product_count"],
                                stats["created_count"],
                                stats["updated_count"],
                                stats["product_resynced_count"],
                            )
                            self.env.cr.commit()
                        except Exception as ex:
                            self.env.cr.rollback()
                            _logger.error(
                                "Inventory remote per-store sync failed: %s (eplus=%s) error=%s",
                                store.display_name, store_eplus_serial, repr(ex)
                            )
        except Exception as ex:
            _logger.error(repr(ex))

    def btn_update_balance_default_sales_store(self):
        """
        Update the configured default sales store through its direct local server.
        This method owns only ab_sales_inventory rows for default_sales_store_id.
        """
        eInv = self.env['ab_sales_inventory'].sudo()
        store = self._get_default_sales_store()
        if not store:
            _logger.info("Inventory default-store sync skipped: no default sales store configured.")
            return

        store_eplus_serial = self._store_eplus_serial(store)
        if not store_eplus_serial:
            _logger.warning(
                "Inventory default-store sync skipped: %s has no E-Plus serial.",
                store.display_name,
            )
            return

        store_server = self._get_default_sales_store_direct_server(store)
        if not store_server:
            _logger.warning(
                "Inventory default-store sync skipped: %s has no direct server.",
                store.display_name,
            )
            return

        try:
            _logger.info(
                "Inventory default-store direct sync started: %s (eplus=%s, server=%s)",
                store.display_name, store_eplus_serial, store_server,
            )
            with self.connect_eplus(
                    server=store_server,
                    param_str=PARAM_STR,
                    charset='CP1256',
            ) as conn:
                with conn.cursor() as crx:
                    sql = SQL_PER_POS.format(store_placeholders=PARAM_STR)
                    crx.execute(sql, (store_eplus_serial,))
                    rows = crx.fetchall()  # [(prod_eplus_ser, store_eplus_ser, balance)]

            stats = eInv._apply_store_balance_rows(store, store_eplus_serial, rows)
            _logger.info(
                "Inventory default-store direct sync finished: %s (eplus=%s) products=%s created=%s updated=%s product_resynced=%s",
                store.display_name,
                store_eplus_serial,
                stats["product_count"],
                stats["created_count"],
                stats["updated_count"],
                stats["product_resynced_count"],
            )
            self.env.cr.commit()
        except Exception as ex:
            self.env.cr.rollback()
            _logger.error(
                "Inventory default-store direct sync failed: %s (eplus=%s, server=%s) error=%s",
                store.display_name, store_eplus_serial, store_server, repr(ex),
            )
