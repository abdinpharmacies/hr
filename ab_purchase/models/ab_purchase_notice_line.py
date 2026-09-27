from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PurchaseNoticeLine(models.Model):
    _name = 'ab_purchase_notice_line'
    _description = 'Abdin Purchase Notice Line'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            header = self.env['ab_purchase_notice_header'].browse(vals.get('header_id'))
            if header.exists() and header.status == 'saved':
                raise ValidationError(_("Saved notice lines cannot be changed."))
        return super().create(vals_list)

    def write(self, vals):
        if any(line.header_id.status == 'saved' for line in self):
            raise ValidationError(_("Saved notice lines cannot be changed."))
        return super().write(vals)

    def unlink(self):
        if any(line.header_id.status == 'saved' for line in self):
            raise ValidationError(_("Saved notice lines cannot be changed."))
        return super().unlink()

    header_id = fields.Many2one(
        'ab_purchase_notice_header', required=True, ondelete='cascade', auto_join=True)

    purchase_header_num = fields.Integer(compute='_compute_purchase_header_id')

    source_id = fields.Many2one('ab_product_source', store=True, )

    product_id = fields.Many2one(related='source_id.product_id')
    available_qty = fields.Float(compute='_compute_invoice_available_qty')
    qty = fields.Float(default=0, digits=(16, 2))
    bonus = fields.Integer(default=0)
    invoice_bonus = fields.Integer(related='source_id.bonus', string="Invoice Bonus")
    invoice_qty = fields.Float(related='source_id.qty', string="Invoice Qty")
    available_bonus = fields.Integer(compute='_compute_invoice_available_bonus')
    price = fields.Float(related='source_id.price')
    line_price = fields.Float(compute='_compute_line_calc')
    line_cost = fields.Float(compute='_compute_line_calc')
    line_taxes_value = fields.Float(compute='_compute_line_taxes_value')
    unit_cost = fields.Float(related='source_id.unit_cost')
    unit_taxes_value = fields.Float(related='source_id.unit_taxes_value')
    uom_id = fields.Many2one(related='source_id.uom_id')

    source_id_domain = fields.Binary(compute='_compute_source_id_domain')

    # eplus fields
    eplus_serial = fields.Integer(index=True, readonly=True)

    eplus_serial_g_return = fields.Integer(index=True, readonly=True)

    last_update_date = fields.Datetime(index=True, readonly=True)

    # header related
    supplier_id = fields.Many2one(related='header_id.supplier_id')
    doc_code = fields.Char(related='header_id.doc_code')
    eplus_g_header_serial = fields.Integer(related='header_id.eplus_g_header_serial')
    eplus_serial_calc = fields.Integer(related='header_id.eplus_serial_calc')
    purchase_header_id = fields.Many2one(related='header_id.purchase_header_id')
    invoice_number = fields.Char(related='purchase_header_id.doc_code', string='Invoice Number')
    pur_eplus_serial = fields.Integer(
        related='purchase_header_id.eplus_serial',
        string='Pur ePlus Serial'
    )

    _eplus_serial_unique = models.Constraint(
        'UNIQUE(eplus_serial)',
        'ePlus Serial For Notice CAN NOT BE DUPLICATED!',
    )
    _eplus_serial_g_return_unique = models.Constraint(
        'UNIQUE(eplus_serial_g_return)',
        'ePlus Serial For G.Notice CAN NOT BE DUPLICATED!',
    )

    @api.depends('source_id')
    def _compute_purchase_header_id(self):
        purchase_line_mo = self.env['ab_purchase_line'].sudo()
        for rec in self:
            purchase_line = purchase_line_mo.search([('source_id', '=', rec.source_id.id)])
            if purchase_line:
                rec.purchase_header_num = purchase_line.header_id.id
            else:
                rec.purchase_header_num = 0

    @api.depends('header_id.purchase_header_id.line_ids.source_id', 'header_id.line_ids.source_id')
    def _compute_source_id_domain(self):
        for rec in self:
            domain = fields.Domain.TRUE
            purchase_lines = rec.header_id.purchase_header_id.mapped('line_ids')
            if purchase_lines:
                source_purchase_lines = [s._origin.id if getattr(s, '_origin', None) else s.id for s in
                                         purchase_lines.mapped('source_id')]

                domain = fields.Domain('id', 'in', source_purchase_lines)

            entered_source_ids = rec.header_id.line_ids.mapped('source_id')
            entered_source_ids = [s._origin.id if getattr(s, '_origin', None) else s.id for s in entered_source_ids]
            domain &= fields.Domain('id', 'not in', entered_source_ids)
            rec.source_id_domain = list(domain)

    @api.depends('source_id', 'source_id.qty', 'source_id.bonus', 'source_id.unit_taxes_value',
                 'source_id.unit_cost', 'source_id.price')
    def _compute_line_calc(self):
        for rec in self:
            rec.line_cost = rec.qty * rec.unit_cost + (rec.bonus * rec.unit_taxes_value)
            rec.line_price = rec.qty * rec.price + (rec.bonus * rec.unit_taxes_value)

    @api.depends('qty', 'bonus')
    def _compute_line_taxes_value(self):
        for rec in self:
            rec.line_taxes_value = (rec.bonus + rec.qty) * rec.unit_taxes_value

    @api.depends('product_id', 'source_id', 'uom_id')
    def _compute_invoice_available_bonus(self):
        for rec in self:
            if rec.source_id.bonus == 0:
                rec.available_bonus = 0
            else:
                purchase_notice = self.search([
                    ('source_id', '=', rec.source_id.id),
                    ('header_id.status', '=', 'saved'),
                ])

                total_return_bonus = sum(purchase_notice.mapped('bonus'))

                rec.available_bonus = rec.invoice_bonus - total_return_bonus

    @api.depends('product_id', 'source_id', 'uom_id', 'header_id.purchase_header_id.store_id')
    def _compute_invoice_available_qty(self):
        for rec in self:
            store = rec.header_id.purchase_header_id.store_id
            if not store or not rec.source_id or not rec.product_id:
                rec.available_qty = 0
                continue
            balance = self.env['ab_inventory_process'].get_balance(
                store.id, source_id=rec.source_id.id,
            )
            unit_size = rec.uom_id.unit_size
            smallest_per_large = rec.product_id.unit_s_id.unit_no or 0
            if unit_size == 'large':
                rec.available_qty = balance / smallest_per_large if smallest_per_large else 0
            elif unit_size == 'medium':
                medium_per_large = rec.product_id.unit_m_id.unit_no or 0
                rec.available_qty = (balance * medium_per_large / smallest_per_large
                                     if smallest_per_large else 0)
            else:
                rec.available_qty = balance
