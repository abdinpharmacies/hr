from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import ValidationError


class AbdinInventoryEplusHeader(models.Model):
    _name = 'ab_inventory_adjust_header'
    _description = 'ab_inventory_adjust_header'
    _order = 'id desc'
    _inherit = ['ab_eplus_replication', 'abdin_et.extra_tools', 'ab_eplus_connect']

    store_id = fields.Many2one('ab_store', required=True)
    store_code = fields.Char(related='store_id.code')
    product_ids = fields.One2many('ab_inventory_adjust_product', 'header_id')
    price_difference = fields.Float(compute="compute_price_difference")
    number_of_products = fields.Integer(compute="compute_number_of_products")
    barcode_scanner_input = fields.Char()
    description = fields.Text()
    status = fields.Selection(selection=[('pending', 'Pending'), ('done', 'Done')], default='pending', required=True)
    line_ids = fields.One2many(comodel_name='ab_inventory_adjust_line', inverse_name='header_id')
    eplus_inv_id = fields.Integer(readonly=True)
    last_adjust_days = fields.Integer(default=3)
    adjust_type = fields.Selection(
        selection=[('main_adjust', 'Main Adjust'),
                   ('self_adjust', 'Self Adjust'),
                   ], default='main_adjust')
    excel_text = fields.Text()

    def write(self, values):
        if self.status == 'done':
            raise ValidationError(_("Document is Done!"))

        res = super().write(values)
        return res

    def compute_price_difference(self):
        for line in self:
            total_old_prices = sum(rec.sell_price * rec.new_qty for rec in line.line_ids if rec.qty > 0.0)
            total_new_prices = sum(rec.sell_price * rec.qty for rec in line.line_ids if rec.qty > 0.0)
            line.price_difference = total_new_prices - total_old_prices

    @api.depends("line_ids")
    def compute_number_of_products(self):
        for line in self:
            line.number_of_products = len(set(line.line_ids))

    def btn_unlink_all_lines(self):
        self.line_ids.unlink()

    def btn_unlink_all_product(self):
        self.product_ids.unlink()

    def btn_get_products_details(self):
        self.line_ids.unlink()
        inventory_line_mo = self.env['ab_inventory_eplus'].sudo()
        inv_lines = inventory_line_mo.search([
            ('store_id', '=', self.store_id.id),
            ('product_id', 'in', self.product_ids.mapped('product_id.id'))
        ])

        adjust_lines = self.line_ids.mapped('inventory_line_id')
        new_lines = inv_lines - adjust_lines

        adjust_data = [
            {'product_id': prod.product_id.id, 'act_qty': prod.act_qty}
            for prod in self.product_ids]

        inventory_lines = sorted(
            [{'inventory_line_id': line.id,
              'product_id': line.product_id.id,
              'c_id': line.c_id,
              'qty': line.qty,
              'new_qty': 0,
              'sell_price': line.sell_price}
             for line in new_lines],
            key=lambda x: (x['product_id'], -x['c_id'])
        )

        inventory_lines = self.calculate_new_qty_for_all_products(adjust_data, inventory_lines)
        if inventory_lines:
            self.write({
                'line_ids': [(0, 0, {
                    'inventory_line_id': inv['inventory_line_id'],
                    'new_qty': inv['new_qty'],
                    'new_sell_price': inv['sell_price'],
                }) for inv in inventory_lines if not (inv['new_qty'] == 0 and inv['qty'] == 0)]
            })

    # @api.onchange('product_ids')
    # def _onchange_ab_adjust_header(self):
    #     self.btn_get_products_details()

    def calculate_new_qty_for_all_products(self, adjustment_data, inventory_lines):
        # Iterate over each product in inventory data
        # Distribute act_qty on inventory lines

        for adjustment in adjustment_data:
            product_id = adjustment["product_id"]
            act_qty = adjustment["act_qty"]

            lines_for_product = [line for line in inventory_lines if line["product_id"] == product_id]

            for i, line in enumerate(lines_for_product):
                if act_qty >= line["qty"]:
                    line["new_qty"] = line["qty"]
                    act_qty -= line["qty"]
                else:
                    line["new_qty"] = act_qty
                    act_qty = 0

                # If this is the last line and there's still some act_qty left, add it to the new_qty
                if i == len(lines_for_product) - 1 and act_qty > 0:
                    # put extra qty on highest c_id
                    lines_for_product[0]["new_qty"] += act_qty
                    act_qty = 0

        return inventory_lines

    def btn_filter_adjust_lines(self):
        return {
            'name': _('.'),
            "type": "ir.actions.act_window",
            "res_model": "ab_inventory_adjust_line",
            "views": [[False, "tree"]],
            "domain": [('header_id', '=', self.id)],
            "target": "current",
        }

    def btn_set_act_qty_diff(self):
        for line in self.product_ids:
            diff_qty = line.act_qty
            inv_qty = line.inv_qty
            print(line.product_id.code, diff_qty, line.inv_qty, inv_qty)
            line.write({'act_qty': inv_qty + diff_qty})

    def btn_add_from_excel(self):
        if self.excel_text:
            lines = self.excel_text.strip().split('\n')
            for line in lines:
                code, act_qty = line.split()
                product_id = self.env['ab_product'].with_context(active_test=False).search(
                    [('code', '=ilike', code)]).id
                act_qty = float(act_qty)
                self.write({
                    'product_ids': [(0, 0, {
                        'product_id': product_id,
                        'act_qty': act_qty,
                    })]
                })
