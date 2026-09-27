from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class AbdinPurchaseDetails(models.Model):
    _name = "ab_purchase_line"
    _description = "Abdin Purchase Details"
    _rec_name = "product_id"

    source_id = fields.Many2one(
        'ab_product_source', required=True, delegate=True, index=True, ondelete='cascade', auto_join=True)

    header_id = fields.Many2one('ab_purchase_header', required=True, index=True, ondelete='cascade', auto_join=True)
    line_purchase_price = fields.Float(digits=(16, 3), compute="_compute_line_purchase_price",
                                       inverse="_inverse_line_purchase_price")
    line_price = fields.Float(digits=(16, 3), compute='_compute_line_price')
    line_cost = fields.Float(digits=(16, 3), compute='_compute_line_cost',
                             inverse='_inverse_line_cost')

    confirm = fields.Boolean(default=False)
    notice_qty = fields.Char(compute='_compute_qty')
    line_taxes_value = fields.Float(digits=(10, 3), compute='_compute_line_taxes_value')
    net_qty = fields.Float(compute='_compute_qty')
    supplier_id = fields.Many2one(related='header_id.supplier_id')
    header_status = fields.Selection(related='header_id.status')

    # eplus fields
    eplus_serial = fields.Integer(index=True, readonly=True)
    eplus_serial_header = fields.Integer(related='header_id.eplus_serial', string='ePlus Serial Header')

    last_update_date = fields.Datetime(index=True, readonly=True)

    disc_tax_no_effect_value = fields.Float(default=0.0)
    _eplus_serial_unique = models.Constraint(
        'UNIQUE(eplus_serial)',
        'ePlus Serial CAN NOT BE DUPLICATED!',
    )

    @api.onchange('product_id')
    def _onchange_product(self):
        self.uom_id = self.product_id.unit_l_id.id

    @api.depends('unit_taxes_value', 'bonus', 'qty')
    def _compute_line_taxes_value(self):
        for rec in self:
            rec.line_taxes_value = rec.unit_taxes_value * (rec.qty + rec.bonus)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"[{rec.id}] - {rec.product_id.display_name}"

    @api.depends('line_purchase_price', 'line_taxes_value', 'source_id.extra_discount_percentage')
    def _compute_line_cost(self):
        for rec in self:
            extra_discount_percentage = rec.source_id.extra_discount_percentage / 100

            net_purchase_price = rec.line_purchase_price * (1 - extra_discount_percentage)

            rec.line_cost = net_purchase_price + rec.line_taxes_value

    # @api.onchange("line_cost")
    def _inverse_line_cost(self):
        for rec in self:
            if rec.qty > 0:
                b = rec.bonus
                q = rec.qty
                d = rec.source_id.extra_discount_percentage
                t2 = sum(tax.percentage / 100 for tax in rec.taxes_ids if tax.apply_on_total)
                t1 = sum(tax.percentage / 100 for tax in rec.taxes_ids if not tax.apply_on_total)
                c = rec.line_cost
                p = c / (q + t1 * (b + q) + t2 * (b + q) + t1 * t2 * q * (b + q))
                net_purchase_price = p / (1 - d / 100)

                rec.purchase_price = net_purchase_price

    @api.depends("source_id.price", "source_id.qty")
    def _compute_line_price(self):
        for line in self:
            line.update({"line_price": line.source_id.qty * line.source_id.price})

    @api.depends("source_id.purchase_price", "source_id.qty")
    def _compute_line_purchase_price(self):
        for line in self:
            line.update({"line_purchase_price": line.source_id.purchase_price * line.source_id.qty})

    @api.onchange("line_purchase_price")
    def _inverse_line_purchase_price(self):
        for line in self:
            line.update({"purchase_price": line.line_purchase_price / line.source_id.qty})

    @api.depends("source_id.qty_large", "source_id.qty", "source_id.product_id")
    def _compute_qty(self):
        for rec in self:
            rec.notice_qty = 0.0  # f"{rounded_notice_qty} {notice_type}"
            rec.net_qty = 0.0  # purchase_qty + total_notice_qty

    @api.onchange("product_id", "supplier_id")
    def _on_change_product_id(self):
        if self.product_id:
            domain = [
                ("product_id", "=", self.product_id.id),
                ("supplier_id", "=", self.supplier_id.id),
            ]
            product_last_purchase = self.search(domain, order="create_date desc", limit=1)
            if not product_last_purchase:
                domain = [("product_id", "=", self.product_id.id)]
                product_last_purchase = self.search(domain, order="create_date desc", limit=1)
            if product_last_purchase:
                self.update(
                    {
                        "price": product_last_purchase.price,
                        "purchase_price": product_last_purchase.purchase_price,
                        "taxes_ids": (
                                product_last_purchase.taxes_ids
                                or self.env.ref("ab_taxes.ab_tax_exempt")
                        ),
                    }
                )

    def write(self, vals):
        if any(rec.header_id.status == 'saved' for rec in self):
            raise UserError(_("Saved purchase invoice lines cannot be changed."))
        with self.env.cr.savepoint():
            result = super().write(vals)
            if {'qty', 'bonus', 'source_id', 'uom_id'} & vals.keys():
                for rec in self.filtered(lambda line: line.header_id.status == 'pending'):
                    rec.env['ab_inventory_process'].inventory_write(
                        rec, rec.qty + rec.bonus, rec.header_id.store_id.id,
                        status='pending',
                    )
        return result

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            header = self.env['ab_purchase_header'].browse(vals.get('header_id'))
            if header.exists() and header.status != 'prepending':
                raise ValidationError(_("Purchase lines cannot be added or deleted after submission."))
        return super().create(vals_list)

    def unlink(self):
        if any(line.header_id.status != 'prepending' for line in self):
            raise ValidationError(_("Purchase lines cannot be added or deleted after submission."))
        return super().unlink()
