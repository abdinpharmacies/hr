from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import ValidationError


class InventoryAdjustHeaderGet(models.Model):
    _name = 'ab_inventory_adjust_header'
    _inherit = 'ab_inventory_adjust_header'

    def btn_change_header_to_done(self):
        pending_adjust_h_ids = self.search([('status', '=', 'pending')]).mapped('eplus_inv_id')
        pending_adjust_h_str = ','.join([str(p_id) for p_id in pending_adjust_h_ids])
        if pending_adjust_h_str:
            store_ip = self.store_id.ip2 if self.adjust_type == 'main_adjust' else self.store_id.ip1
            with self.connect_eplus(server=store_ip) as conn:
                with conn.cursor() as cr:
                    sql_inv_h = f"""SELECT inv_id FROM inventory_h 
                    WHERE inv_id in ({pending_adjust_h_str})
                    and inv_flag != 'P'
                    """
                    cr.execute(sql_inv_h)
                    recs = [rec[0] for rec in cr.fetchall()]
                    self.search([('eplus_inv_id', 'in', recs)]).status = 'done'

    def _get_product_id(self, eplus_serial):
        product = self.env['ab_product'].with_context(active_test=False).sudo().search([
            ('eplus_serial', '=', eplus_serial)
        ])

        return product.id

    def btn_get_eplus_inventory(self):
        try:
            self.btn_change_header_to_done()
            # try:
            #     self.replicate_ab_product()
            # except:
            #     pass

            last_update_date = self._get_last_update_date('ab_inventory_eplus', store_id=self.store_id.id)

            where_condition = self._get_where_condition(last_update_date)
            inventory_eplus_mo = self.env['ab_inventory_eplus'].sudo()
            store_eplus_serial = self.store_id.eplus_serial
            sql = f"""SELECT
                    main.itm_id as product_eplus_serial,
                    main.sto_id as store_eplus_serial,
                    main.c_id as c_id,
                    cast(main.itm_qty/ic.itm_unit1_unit3 as decimal(18,2)) as qty,
                    main.sell_price as sell_price,
                    main.itm_expiry_date,
                    main.pharm_price + main.sell_tax as cost,
                    main.sell_tax as sell_tax,
                    main.pharm_price as pharm_price,
                    main.sec_update_date as last_update_date
                FROM Item_Class_Store main WITH (NOLOCK) 
                JOIN item_catalog ic on main.itm_id = ic.itm_id
                {where_condition} and  main.sto_id = {store_eplus_serial} 
                ORDER BY last_update_date
                """
            store_ip = self.store_id.ip2 if self.adjust_type == 'main_adjust' else self.store_id.ip1
            chunks = self._fetch_eplus_data(sql, last_update_date, server=store_ip)
            odoo_lines_to_create = []
            odoo_lines_to_update = []

            for chunk in self.web_progress_iter(chunks, msg='Preparing Inventory Lines'):
                for line in chunk:
                    product_id = self._get_product_id(line['product_eplus_serial'])
                    store_id = self.store_id.id
                    inv_line = inventory_eplus_mo.search([
                        ('store_id', '=', store_id),
                        ('product_id', '=', product_id),
                        ('c_id', '=', line['c_id']),
                    ])
                    if inv_line:
                        odoo_lines_to_update.append({
                            'id': inv_line.id,
                            'qty': line['qty'],
                            'sell_price': line['sell_price'],
                            'last_update_date': line['last_update_date'],
                        })
                    else:
                        odoo_lines_to_create.append({
                            'product_id': product_id,
                            'store_id': self.store_id.id,
                            'c_id': line['c_id'],
                            'qty': line['qty'],
                            'sell_price': line['sell_price'],
                            'itm_expiry_date': line['itm_expiry_date'],
                            'cost': line['cost'],
                            'sell_tax': line['sell_tax'],
                            'pharm_price': line['pharm_price'],
                            'last_update_date': line['last_update_date'],
                        })

            # create new records
            inventory_eplus_mo.create(odoo_lines_to_create)

            # update existing records
            for record in odoo_lines_to_update:
                record_id = record.pop('id')
                adjust_line = inventory_eplus_mo.browse(record_id)
                adjust_line.write(record)

            created_count = len(odoo_lines_to_create)
            updated_count = len(odoo_lines_to_update)
            msg = f"""
            <div>New Inventory Lines are: <span class="text-success">{created_count}</span> line(s)</div> 
            <div>Updated Inventory Lines are: <span class="text-success">{updated_count}</span> line(s)</div> 
            """
            return self.ab_msg(title="Done", message=msg)

        except Exception as e:
            raise ValidationError(repr(e))
