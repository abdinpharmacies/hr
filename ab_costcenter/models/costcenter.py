# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
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

    def _compute_costcenter_space_sep(self):
        for rec in self:
            rec.costcenter_space_sep = rec.id

    def _search_costcenter_space_sep(self, operator, value):
        if operator in ['in', 'ilike', 'not in', 'not ilike']:
            value = [v.strip() for v in value.split()]
            operator = 'in' if operator in ['in', 'ilike'] else 'not in'

        ids = self.sudo().search([('code', operator, value)]).ids
        return [('id', 'in', ids)]

    @api.constrains('code')
    def constrains_ab_costcenter(self):
        for rec in self:
            if ' ' in rec.code:
                raise ValidationError(_("Code must not have spaces"))
            if not rec.bc_id:
                if not (rec.code.startswith('0-') or rec.code.startswith('1-')):
                    raise ValidationError(_("Code must starts with 0- or 1-"))

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        args = list(args or [])
        code_args = args + [('code', '=', name), ]

        ids = (self.with_user(name_get_uid) if name_get_uid else self).search(code_args, limit=limit).ids
        if not ids:
            args += [('name', operator, name), ]
            ids = (self.with_user(name_get_uid) if name_get_uid else self).search(args, limit=limit).ids
        return ids

    @api.model
    def name_search(self, name="", domain=None, operator="ilike", limit=100):
        """Expose the existing search order through the Odoo 19 public API."""
        ids = self._name_search(name, args=domain, operator=operator, limit=limit)
        return [(record.id, record.display_name) for record in self.browse(ids)]

    @api.model
    def _search_display_name(self, operator, value):
        """Keep code/barcode/name matching in relational search domains too."""
        if operator in ('in', 'not in') and isinstance(value, (list, tuple)):
            domain = fields.Domain.OR(self._search_display_name('=', item) for item in value)
            return list(~domain if operator == 'not in' else domain)
        ids = self._name_search(value or '', operator=operator, limit=None)
        return [('id', 'in', ids)]

    _ab_costcenter_code_unique = models.Constraint('unique(code)', 'CODE CAN NOT BE DUPLICATED.')

    def write(self, vals):
        res = super(ClsCostCenters, self).write(vals)
        return res
