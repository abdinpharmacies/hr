from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PurchaseNoticeLine(models.Model):
    _name = 'ab_purchase_notice_line'
    _description = 'Abdin Purchase Notice Line'

    header_id = fields.Many2one(
        'ab_purchase_notice_header', required=True, ondelete='cascade', auto_join=True)

    purchase_header_num = fields.Integer(compute='_compute_purchase_header_id')

    source_id = fields.Many2one('ab_product_source', store=True, )

    product_id = fields.Many2one(related='source_id.product_id')
    available_qty = fields.Float(compute='_compute_invoice_available_qty')
    qty = fields.Float(default=0, digits=(16, 2))
    bonus = fields.Integer(default=0)
    last_inventory_id = fields.Many2one('ab_inventory', compute='_compute_last_inventory_id')
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
    costcenter_id = fields.Many2one(related='supplier_id.costcenter_id')
    je_header_id = fields.Many2one(related='header_id.je_header_id')
    doc_code = fields.Char(related='header_id.doc_code')
    eplus_g_header_serial = fields.Integer(related='header_id.eplus_g_header_serial')
    eplus_serial_calc = fields.Integer(related='header_id.eplus_serial_calc')
    je_line_ids = fields.One2many(related='header_id.line_ids')
    related_claim_id = fields.Many2one(related='header_id.related_claim_id')
    purchase_header_id = fields.Many2one(related='header_id.purchase_header_id')
    invoice_number = fields.Char(related='purchase_header_id.doc_code', string='Invoice Number')
    pur_eplus_serial = fields.Integer(
        related='purchase_header_id.eplus_serial',
        string='Pur ePlus Serial'
    )

    _sql_constraints = [
        ('eplus_serial_unique', 'unique(eplus_serial)', 'ePlus Serial For Notice CAN NOT BE DUPLICATED!'),
        ('eplus_serial_g_return_unique', 'unique(eplus_serial_g_return)',
         'ePlus Serial For G.Notice CAN NOT BE DUPLICATED!'),
    ]

    def _get_source_id_domain(self):
        pending = self.env['ab_product_source_pending'].search([])
        return [('id', 'in', pending.ids)]

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

    @api.depends('source_id')
    def _compute_last_inventory_id(self):
        for rec in self:
            last_inventory = self.env['ab_inventory'].search([
                ('source_id', '=', rec.source_id.id),
                ('status', '=', 'pending_main'),
            ],
                limit=1,
                order='id desc')

            rec.last_inventory_id = last_inventory.id

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

    @api.depends('product_id', 'source_id', 'uom_id')
    def _compute_invoice_available_qty(self):
        for rec in self:
            inventory_pending = self.env['ab_inventory'].search(
                [('source_id', '=', rec.source_id.id), ('status', '=', 'pending_main')])

            inventory_all = self.env['ab_inventory'].search([('source_id', '=', rec.source_id.id), ])

            # get min(pending , all) qty
            # EXAMPLE OF EQUATION AT END OF FILE
            available_qty_pending_s_unit = sum(inv.qty for inv in inventory_pending)
            available_qty_all_s_unit = sum(inv.qty for inv in inventory_all)
            available_qty_s_unit = min(available_qty_pending_s_unit, available_qty_all_s_unit)

            available_qty_with_bonus = rec.product_id.qty_from_small(available_qty_s_unit, rec.uom_id.unit_size)

            # check if this line was returned before (to define actual rest of bonus)
            rec.available_qty = available_qty_with_bonus - rec.available_bonus

    # def unlink(self):
    #     for rec in self:
    #         if rec.header_id.status == 'saved':
    #             raise ValidationError(
    #                 "Can not delete, Notice is saved")
    #         if self.env['ab_inventory'].search_count([('model_ref', '=', rec._name), ('res_id', '=', rec.id)]):
    #             raise ValidationError(
    #                 "Can not delete, Item is returned before ")
    #     return super().unlink()

# source_id	qty	status
# 123	30	saved	        pur_line
# 123  -10	store_pending	pur_notice-
# 123	10	store_pending	pur_notice+
# 123  -10	saved	        sales
# 123  -20	saved	        transfer
# 123	10	main_pending	transfer
# 123	10	store_pending	transfer
