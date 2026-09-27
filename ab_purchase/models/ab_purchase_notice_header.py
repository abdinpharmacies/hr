import datetime

import re
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class PurchaseNoticeHeader(models.Model):
    _name = 'ab_purchase_notice_header'
    _description = 'Abdin Purchase Notice Header'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_names_search = ['doc_code', 'purchase_header_id.doc_code']

    supplier_id = fields.Many2one("ab_supplier", required=True, tracking=True)

    purchase_header_ids = fields.Many2many('ab_purchase_header', string='Invoice Numbers')

    purchase_header_id = fields.Many2one('ab_purchase_header', string='Invoice')
    pur_eplus_serial = fields.Integer(
        related='purchase_header_id.eplus_serial',
        string='Pur ePlus Serial'
    )
    eplus_serial_calc = fields.Integer(
        compute='_compute_eplus_serial_calc',
        search='_search_eplus_serial_calc',
    )
    lines_count = fields.Integer(compute='compute_totals')
    total_cost = fields.Float(compute='compute_totals', digits=(12, 3))
    total_taxes_value = fields.Float(compute='compute_totals', digits=(12, 3))
    description = fields.Text()
    doc_date = fields.Date(default=lambda self: datetime.date.today())
    doc_code = fields.Char(required=True, default='0000000000')
    invoice_number = fields.Char(related='purchase_header_id.doc_code', string='Invoice Number')
    eplus_g_header_serial = fields.Integer()
    # @todo: activate 'Debit Notice'
    #    1. only on invoice(s)
    #    2. show all product_source_lines of invoice(s)
    #    3. update - or reverse - journal entries
    notice_type = fields.Selection([('credit_notice', 'Credit Notice'),
                                    ('debit_notice', 'Debit Notice'), ],
                                   required=True, default='credit_notice', readonly=True)

    status = fields.Selection(
        selection=[('pending', 'Pending'), ('saved', 'Saved')],
        default='pending',
        index=True,
    )

    line_ids = fields.One2many(comodel_name='ab_purchase_notice_line',
                               inverse_name='header_id', required=True)

    def _compute_eplus_serial_calc(self):
        for rec in self:
            if rec.purchase_header_id:
                rec.eplus_serial_calc = rec.purchase_header_id.eplus_serial
            else:
                rec.eplus_serial_calc = rec.eplus_g_header_serial

    def _search_eplus_serial_calc(self, operator, val):
        ids = self.env['ab_purchase_notice_header'].search([('eplus_g_header_serial', operator, val)]).ids
        ids += self.env['ab_purchase_notice_header'].search([('pur_eplus_serial', operator, val)]).ids
        return [('id', 'in', ids)]

    @api.onchange('purchase_header_id')
    def _onchange_purchase_notice_header(self):
        if self.purchase_header_id:
            self.supplier_id = self.purchase_header_id.supplier_id.id

    @api.depends('line_ids', 'line_ids.line_cost')
    def compute_totals(self):
        pur_line_mo = self.env['ab_purchase_line'].sudo()

        def _get_pur_line_disc_diff_tax(line):
            pur_line = pur_line_mo.search([('source_id', '=', line.source_id.id)])
            return pur_line.disc_tax_no_effect_value * -1
            # if pur_line.disc_tax_no_effect_value >= 0:
            #     return 0
            # else:
            #     return pur_line.disc_tax_no_effect_value * -1

        for rec in self:
            total_inv_qty = sum(line.qty + line.bonus for line in rec.purchase_header_id.line_ids)
            total_notice_qty = sum(line.qty + line.bonus for line in rec.line_ids)
            if total_inv_qty == total_notice_qty:
                rec.total_cost = rec.purchase_header_id.net_invoice
                rec.total_taxes_value = rec.purchase_header_id.net_tax
            else:
                rec.total_cost = sum(line.line_cost + _get_pur_line_disc_diff_tax(line) for line in rec.line_ids)
                rec.total_taxes_value = sum(line.line_taxes_value for line in rec.line_ids)

            rec.lines_count = len(rec.line_ids)

    # @api.depends('line_ids', 'line_ids.line_cost')
    # def compute_totals(self):
    #     for rec in self:
    #         rec.total_cost = sum(line.line_cost for line in rec.line_ids)
    #         rec.total_taxes_value = sum(line.line_taxes_value for line in rec.line_ids)
    #         rec.lines_count = len(rec.line_ids)
    #
    def btn_get_all_line_ids(self):
        self.ensure_one()
        source_ids = self.purchase_header_id.line_ids.mapped('source_id').ids
        current_line_ids = self.line_ids.mapped('source_id.id')
        self.write({'line_ids': [(0, 0, {'source_id': source_id})
                                 for source_id in source_ids
                                 if source_id not in current_line_ids
                                 ]})

    @api.constrains('doc_code', 'purchase_header_id', 'line_ids')
    def constrains_ab_purchase_header(self):
        for rec in self:
            # if not self.validate_doc_code(rec.doc_code):
            #     raise ValidationError(_('Notice Number must be digits and dashes.'))
            if rec.purchase_header_id:

                supplier_id = rec.purchase_header_id.supplier_id.id
                if supplier_id != rec.supplier_id.id:
                    raise ValidationError(_('Invoice supplier is not same as Notice Supplier!'))
                if rec.line_ids:
                    purchase_lines = rec.purchase_header_id.mapped('line_ids').mapped('source_id.id')
                    entered_lines = rec.line_ids.mapped('source_id.id')
                    if set(entered_lines) - set(purchase_lines):
                        raise ValidationError(_('Source IDs not compatible with Invoice'))

    def validate_doc_code(self, doc_code):
        return re.match(r'^[a-zA-Z0-9-]+$', doc_code)

    def btn_submit_inventory(self):
        self.ensure_one()
        if not (self.env.user.has_group('base.group_system')
                or self.env.user.has_group('ab_purchase.group_ab_purchase_manager')):
            raise AccessError(_("Only purchase managers can save notices into stock."))
        if self.status == 'saved':
            return True
        if not self.purchase_header_id or not self.purchase_header_id.store_id:
            raise ValidationError(_("Link a purchase invoice and store before saving the notice."))
        if self.purchase_header_id.status != 'saved':
            raise ValidationError(_("Save the purchase receipt before posting a notice."))
        if any(line.qty < 0 or line.bonus < 0 for line in self.line_ids):
            raise ValidationError(_("Purchase quantities and bonuses cannot be negative."))
        lines = self.line_ids.filtered(lambda line: line.qty + line.bonus > 0)
        if not lines:
            raise ValidationError(_("Add a notice line with a positive quantity."))
        sign = -1 if self.notice_type == 'credit_notice' else 1
        with self.env.cr.savepoint():
            for line in lines:
                self.env['ab_inventory_process'].inventory_write(
                    line, line.qty + line.bonus,
                    self.purchase_header_id.store_id.id,
                    sign=sign, status='saved',
                )
            super(PurchaseNoticeHeader, self).write({'status': 'saved'})
        return True

    @api.model_create_multi
    def create(self, vals_list):
        if any(vals.get('status', 'pending') != 'pending' for vals in vals_list):
            raise ValidationError(_("Create purchase notices as pending."))
        return super().create(vals_list)

    def write(self, vals):
        if 'status' in vals:
            raise ValidationError(_("Use the notice Submit action to save inventory."))
        return super().write(vals)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.purchase_header_id.doc_code or ''} - [{rec.doc_code or ''}]"
