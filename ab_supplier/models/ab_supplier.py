# -*- coding: utf-8 -*-

from odoo import models, fields, api


class Supplier(models.Model):
    _name = 'ab_supplier'
    _description = 'ab_supplier'

    _parent_store = True
    _parent_name = "parent_id"  # optional if field is 'parent_id'
    parent_path = fields.Char(index=True)

    parent_id = fields.Many2one('ab_supplier',
                                string='Parent Supplier',
                                ondelete='restrict',
                                index=True)

    child_ids = fields.One2many(
        'ab_supplier', 'parent_id',
        string='Sub Suppliers')
    name = fields.Char()
    costcenter_id = fields.Many2one('ab_costcenter', index=True)
    code = fields.Char(required=True, index=True)
    telephone = fields.Char()
    address = fields.Char()
    registration_number = fields.Char()
    end_date = fields.Date()
    max_credit = fields.Float()
    current_credit = fields.Float()
    return_interval = fields.Integer()
    tax_type = fields.Selection([('through_supplier', 'Through Supplier'),
                                 ('tax_payment', 'Tax Payment'),
                                 ('non_tax_payment', 'Non-tax Payment')])
    section = fields.Selection([('medical', 'Medical'), ('imp_med', 'Imported Med'),
                                ('cosmo', 'Cosmetics'), ('imp_cosmo', 'Imported Cosmetics'),
                                ('other', 'Other')])
    territory = fields.Selection([('upper_egypt', 'Upper Egypt'),
                                  ('lower_egypt', 'Lower Egypt'),
                                  ('both', 'Both'),
                                  ], default='both')

    purchase_limit = fields.Float()
    active = fields.Boolean(default=True)
    description = fields.Text()

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        args = list(args or [])
        code_args = args + [('code', '=ilike', name), ]
        ids = self._search(code_args, limit=limit,
                           access_rights_uid=name_get_uid)
        if not ids:
            args += [('name', operator, name), ]
            ids = self._search(args, limit=limit,
                               access_rights_uid=name_get_uid)
        return ids

    @api.model
    def create(self, vals):
        return super().create(vals)

    def unlink(self):
        return super().unlink()
