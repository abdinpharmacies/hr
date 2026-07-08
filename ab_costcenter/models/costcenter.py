# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.tools.translate import _
from odoo.exceptions import ValidationError


class ClsCostCenters(models.Model):
    _name = 'ab_costcenter'
    _description = 'Abdin Cost Centers'

    name = fields.Char(required=True, index=True)
    costcenter_type = fields.Integer()
    tel_no = fields.Char()
    branch_id = fields.Integer()
    hr_name = fields.Char()
    bc_id = fields.Integer()
    code = fields.Char(size=16, required=True, index=True)
    official_name = fields.Char()
    special_id = fields.Char()
    active = fields.Boolean(default=True)
    costcenter_space_sep = fields.Char(search='_search_costcenter_space_sep', compute='_compute_costcenter_space_sep', )
    mobile_phone = fields.Char('Work Mobile')
    user_id = fields.Many2one('res.users', index=True)
    password = fields.Char(groups='base.group_system')
    work_email = fields.Char('Work Email')
    work_phone = fields.Char()
    supplier_type = fields.Selection(
        selection=[
            ('advance_payment', 'Advance Payment'),
            ('withholding_tax', 'Withholding Tax'),
            ('non_taxable', 'Non-Taxable'),
        ],
        string='Supplier Type',
    )
    representative_phone = fields.Char(string='Representative Phone')
    english_name = fields.Char()
    religion = fields.Selection(selection=[('muslim', 'Muslim'), ('christian', 'Christian'), ('other', 'Other'), ])
    gender = fields.Selection(
        selection=[
            ('male', 'Male'),
            ('female', 'Female'),
        ], )

    is_company = fields.Boolean(string='Is a Company', default=False,
                                help="Check if the partner is a company, otherwise it is a person")

    identification_id = fields.Char()
    birthday = fields.Date()
    establishment_date = fields.Date()
    supplier_claim_activity = fields.Html(
        string='Supplier Activity',
        compute='_compute_supplier_claim_activity',
        readonly=True,
        sanitize=False,
    )
    supplier_activity_status = fields.Selection(
        selection=[('active', 'Active'), ('non_active', 'Non Active')],
        string='Supplier Activity Status',
        compute='_compute_supplier_activity_status',
    )
    supplier_performance_html = fields.Html(
        string='Supplier Performance',
        compute='_compute_supplier_performance_html',
        sanitize=False,
    )

    def _compute_costcenter_space_sep(self):
        for rec in self:
            rec.costcenter_space_sep = rec.id

    def _search_costcenter_space_sep(self, operator, value):
        if operator in ['in', 'ilike', 'not in', 'not ilike']:
            value = [v.strip() for v in value.split()]
            operator = 'in' if operator in ['in', 'ilike'] else 'not in'

        ids = self.sudo().search([('code', operator, value)]).ids
        return [('id', 'in', ids)]

    @api.model
    def _search_display_name(self, operator, value):
        code_ids = self._search([('code', '=', value)])
        if code_ids:
            return [('id', 'in', code_ids)]
        return [('name', operator, value)]

    def _compute_supplier_claim_activity(self):
        for rec in self:
            rec.supplier_claim_activity = ''

    def _compute_supplier_activity_status(self):
        for rec in self:
            rec.supplier_activity_status = 'non_active'

    def _compute_supplier_performance_html(self):
        for rec in self:
            rec.supplier_performance_html = ''

    def write(self, vals):
        res = super(ClsCostCenters, self).write(vals)
        return res
