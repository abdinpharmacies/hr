import datetime

import re
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PurchaseNoticeHeader(models.Model):
    _name = 'ab_purchase_notice_header'
    _description = 'Abdin Purchase Notice Header'
    _inherit = ['ab_purchase_je_header_delegate_common',
                'mail.thread', 'mail.activity.mixin', 'ab_inventory_process']

    supplier_id = fields.Many2one("ab_supplier", required=True, tracking=True)

    related_claim_id = fields.Many2one('ab_purchase_claim', compute='_compute_related_claim_id')

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

    @api.depends('je_header_id')
    def _compute_related_claim_id(self):
        supplier_account = self.env.ref('ab_accounting.ab_accounting_account_guide_suppliers')
        for rec in self:
            claim = False

            je_supplier_line = rec.je_header_id.line_ids.filtered(lambda je: je.account_id == supplier_account)
            if je_supplier_line:
                claim = je_supplier_line[0].claim_id
            rec.related_claim_id = claim and claim.id

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
        purchase_source_ids = self.purchase_header_id.line_ids.mapped('source_id.id')
        source_ids = self.env['ab_product_source_pending'].search([('id', 'in', purchase_source_ids)]).ids

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

    def _validate_notice(self):
        for rec in self.line_ids:
            unit_size = rec.uom_id.unit_size

            # if user enter product on more than one line
            notice_qty_s = sum(line.product_id.qty_to_small(line.qty, unit_size)
                               for line in self.line_ids if line.source_id.id == rec.source_id.id)

            available_qty_s = rec.product_id.qty_to_small(rec.available_qty, unit_size)
            # @todo: activate this condition again
            # if notice_qty_s > available_qty_s or rec.bonus > rec.available_bonus:
            #     raise ValidationError(_(f"Not Enough Pending Balance For {rec.source_id.product_id.name}"))

    def btn_submit_inventory(self):
        # remove zero qty zero bonus lines
        self.line_ids.filtered(lambda l: (l.qty == 0 and l.bonus == 0)).unlink()

        inventory = self.env['ab_inventory']
        self._validate_notice()
        purchase_notice_lines = self.line_ids
        print(self.line_ids)

        # negative will be true if credit_notice
        sign = -1 if self.notice_type == 'credit_notice' else 1
        for line in purchase_notice_lines:
            inventory_line = inventory.search(
                [('model_ref', '=', line._name), ('res_id', '=', line.id)])
            if len(inventory_line) == 1:
                raise ValidationError(_("Product is returned before."))
            elif len(inventory_line) == 0:
                qty_total = line.qty + line.bonus
                store_id = line.last_inventory_id.store_id.id
                self.inventory_write(line, qty_total, store_id, sign=sign, status='pending_main')

            else:
                raise UserError(_("Error in Invoice, Contact Support"))

        self.status = 'saved'

    def write(self, vals):
        res = super().write(vals)
        if self.je_header_id.line_ids:
            je_vals = {}
            pur_doc_code = self.purchase_header_id.doc_code
            doc_code = pur_doc_code if pur_doc_code else self.doc_code
            if "supplier_id" in vals:
                je_vals.update({'costcenter_id': self.supplier_id.costcenter_id.id})
            if "doc_code" in vals:
                je_vals.update({'doc_no': doc_code})
            if je_vals:
                self.sudo().je_header_id.line_ids.write(je_vals)

        return res

    def name_get(self):
        res = []
        for rec in self:
            res.append((rec.id, f"{rec.purchase_header_id.doc_code} - [{rec.doc_code}]"))
        return res

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        args = list(args or [])
        args += ['|',
                 ('doc_code', operator, name),
                 ('purchase_header_id.doc_code', operator, name),
                 ]

        ids = self._search(args, limit=limit, access_rights_uid=name_get_uid)
        return ids
