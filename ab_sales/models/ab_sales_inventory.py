import math

from odoo import fields, models, api
from odoo.tools.translate import _
from odoo.tools import config
from odoo.exceptions import UserError
from .ab_sales_header import PARAM_STR
import logging

_logger = logging.getLogger(__name__)

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
            ORDER BY main.itm_id, balance desc -- order by sec_insert_date desc   \
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
              ORDER BY main.itm_id, main.sto_id, balance desc -- order by sec_insert_date desc  \
              """


class InventoryEplus(models.Model):
    _name = 'ab_sales_inventory'
    _inherit = ['ab_eplus_connect']
    _description = 'ab_sales_inventory'

    product_eplus_serial = fields.Integer(index=True)
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

    def _get_available_bconnect_server(self, port=1433):
        """Return the first reachable BConnect server or False for background syncs."""
        candidates = [config.get("bconnect_ip1"), config.get("bconnect_ip2")]
        for server in candidates:
            if server and self.is_port_open(server, port=port):
                return server
        return False

    def btn_update_balance_total(self):
        eInv = self.env['ab_sales_inventory'].sudo()

        stores = self.env['ab_store'].sudo().search([('allow_sale', '=', True)])
        store_eplus_serials = [int(x) for x in stores.mapped('eplus_serial') if x]
        has_bal_list = []
        try:
            if not store_eplus_serials:
                self.search([]).write({'balance': 0})
                return

            def _chunks(seq, size):
                for i in range(0, len(seq), size):
                    yield seq[i:i + size]

            server = self._get_available_bconnect_server()
            if not server:
                _logger.warning("Inventory total sync skipped: all BConnect servers are offline.")
                return

            with self.connect_eplus(server=server, param_str=PARAM_STR, charset='CP1256') as conn:
                with conn.cursor() as crx:
                    totals_by_product = {}
                    # SQL Server has a 2100-parameter limit; keep some margin.
                    for store_chunk in _chunks(store_eplus_serials, 2000):
                        store_placeholders = ",".join([PARAM_STR] * len(store_chunk))
                        sql = SQL_TOTAL.format(store_placeholders=store_placeholders)
                        crx.execute(sql, tuple(store_chunk))
                        chunk_rows = crx.fetchall()  # [(prod_eplus_ser, balance)]
                        for prod_eplus_ser, balance in chunk_rows:
                            totals_by_product[int(prod_eplus_ser)] = (
                                    float(totals_by_product.get(int(prod_eplus_ser), 0.0)) + float(balance or 0.0)
                            )

                    rows = sorted(totals_by_product.items(), key=lambda r: r[0])
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
                        if not inv_lines:
                            inv_lines = eInv.create({
                                'product_eplus_serial': prod_eplus_ser,
                                'store_id': False,
                                'balance': balance,
                            })

                        balances = inv_lines.mapped('balance')
                        if any(not math.isclose(balance, b, abs_tol=0.01) for b in balances):
                            inv_lines.write({'balance': balance})

                    self.search([
                        ('product_eplus_serial', 'not in', has_bal_list),
                        ('store_id', '=', False),
                    ]).write({'balance': 0})
        except Exception as ex:
            _logger.error(repr(ex))

    def btn_update_balance_per_pos(self):
        """
        Update balances per store (POS) into ab_sales_inventory(store_id, product_eplus_serial).
        If a store has no products, its balances are set to 0.
        """
        eInv = self.env['ab_sales_inventory'].sudo()

        stores = self.env['ab_store'].sudo().search([('allow_sale', '=', True)])
        store_pairs = []
        for store in stores:
            try:
                store_eplus_serial = int(store.eplus_serial or 0)
            except Exception:
                store_eplus_serial = 0
            if store_eplus_serial:
                store_pairs.append((store, store_eplus_serial))

        if not store_pairs:
            eInv.search([('store_id', '!=', False)]).write({'balance': 0})
            return

        def _chunks(seq, size):
            for i in range(0, len(seq), size):
                yield seq[i:i + size]

        try:
            server = self._get_available_bconnect_server()
            if not server:
                _logger.warning("Inventory per-store sync skipped: all BConnect servers are offline.")
                return

            with self.connect_eplus(server=server, param_str=PARAM_STR, charset='CP1256') as conn:
                with conn.cursor() as crx:
                    for store, store_eplus_serial in store_pairs:
                        try:
                            _logger.info(
                                "Inventory per store sync started: %s (eplus=%s)",
                                store.display_name, store_eplus_serial
                            )

                            eInv.search([('store_id', '=', store.id)]).write({'balance': 0})

                            sql = SQL_PER_POS.format(store_placeholders=PARAM_STR)
                            crx.execute(sql, (store_eplus_serial,))
                            rows = crx.fetchall()  # [(prod_eplus_ser, store_eplus_ser, balance)]

                            balances_by_product = {}
                            for prod_eplus_ser, store_eplus_ser, balance in rows:
                                try:
                                    prod_eplus_ser = int(prod_eplus_ser)
                                    store_eplus_ser = int(store_eplus_ser)
                                    balance = float(balance or 0.0)
                                except Exception:
                                    continue

                                if store_eplus_ser != store_eplus_serial:
                                    continue
                                if balance <= 0.0:
                                    continue
                                balances_by_product[prod_eplus_ser] = balance

                            product_serials = sorted(balances_by_product.keys())
                            existing_by_product = {}
                            for prod_chunk in _chunks(product_serials, 1000):
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
                                if not inv_line:
                                    created_vals.append({
                                        'product_eplus_serial': prod_eplus_ser,
                                        'store_id': store.id,
                                        'balance': balance,
                                    })
                                    continue

                                if not math.isclose(balance, inv_line.balance, abs_tol=0.01):
                                    inv_line.write({'balance': balance})
                                    updated_count += 1

                            if created_vals:
                                eInv.create(created_vals)

                            _logger.info(
                                "Inventory per store sync finished: %s (eplus=%s) products=%s created=%s updated=%s",
                                store.display_name,
                                store_eplus_serial,
                                len(product_serials),
                                len(created_vals),
                                updated_count,
                            )
                            self.env.cr.commit()
                        except Exception as ex:
                            self.env.cr.rollback()
                            _logger.error(
                                "Inventory per store sync failed: %s (eplus=%s) error=%s",
                                store.display_name, store_eplus_serial, repr(ex)
                            )
        except Exception as ex:
            _logger.error(repr(ex))
