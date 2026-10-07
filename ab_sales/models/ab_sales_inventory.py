
from odoo import api, fields, models
from odoo.tools.translate import _



class InventoryEplus(models.Model):
    _name = 'ab_sales_inventory'
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
    def _get_default_sales_store(self):
        replica_db = self.env["ab_replica_db"].sudo().get_current_from_config()
        return replica_db.default_sales_store_id if replica_db and replica_db.default_sales_store_id else self.env["ab_store"]
