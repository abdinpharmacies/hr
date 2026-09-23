# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError


class AuthGroup(models.Model):
    _name = 'ab_accounting_auth_group'
    _description = 'ab_accounting_auth_group'

    name = fields.Char(required=True)
    account_auth_ids = fields.One2many('ab_accounting_account_auth',
                                       copy=True,
                                       inverse_name='group_id')
    doctype_ids = fields.Many2many(comodel_name="ab_accounting_doctype",
                                   relation="doctype_group_auth_rel",
                                   column1="group_id",
                                   column2="acc_id",
                                   copy=True,
                                   string="Doc Type Auth", )

    allowed_field_ids = fields.One2many(comodel_name="ab_accounting_allowed_field_auth",
                                        inverse_name='group_id',
                                        copy=True,
                                        string="Allowed Fields", )

    user_ids = fields.One2many('res.users', 'accounting_auth_group_id', string='Users')

    def remove_doc_auth(self):
        self.ensure_one()
        self.write({'doctype_ids': [(5, 0, 0)]})

    def btn_all_doc_auth(self):
        self.ensure_one()
        self.write({
            'doctype_ids': self.env['ab_accounting_doctype'].search([])
        })

    def btn_all_account_auth(self):
        self.ensure_one()
        self.write({
            'account_auth_ids': [(0, 0,
                                  {
                                      'account_id': fld.id,
                                      'group_id': self.id,
                                  }) for fld in self.env['ab_accounting_account_guide']
                                 .search([('is_final', '=', True),
                                          ('id', 'not in', self.account_auth_ids.mapped("account_id.id"))
                                          ])]
        })

    def remove_account_auth(self):
        self.ensure_one()
        self.account_auth_ids.unlink()

    def btn_all_allowed_fields_auth(self):
        self.ensure_one()
        self.write({
            'allowed_field_ids': [(0, 0,
                                   {
                                       'allowed_field_id': fld.id,
                                       'group_id': self.id,
                                   }) for fld in self.env['ab_accounting_allowed_field']
                                  .search([('id', 'not in', self.allowed_field_ids.mapped("allowed_field_id.id"))])]
        })

    def remove_allowed_fields_auth(self):
        self.ensure_one()
        self.allowed_field_ids.unlink()


class UserAccountAuth(models.Model):
    _name = 'ab_accounting_account_auth'
    _description = 'ab_accounting_account_auth'
    _rec_name = 'account_id'

    account_id = fields.Many2one('ab_accounting_account_guide',
                                 required=True,
                                 index=True, )

    parent_path = fields.Char(related='account_id.parent_path')
    account_serial = fields.Integer(related='account_id.id', string="Account ID")
    group_id = fields.Many2one('ab_accounting_auth_group', required=True, index=True)
    own_account = fields.Boolean(default=False, index=True)
    allow_account = fields.Boolean(default=False, index=True)
    prevent_enquiry = fields.Boolean(default=False, index=True)
    always_show_account = fields.Boolean(default=False, index=True)

    _sql_constraints = [
        ('ab_accounting_account_auth_group_account_unique', 'UNIQUE(account_id,group_id)',
         'ACCOUNT an USER must be unique'),
    ]


class AllowedFieldsAuth(models.Model):
    _name = 'ab_accounting_allowed_field_auth'
    _description = 'ab_accounting_allowed_field_auth'
    _rec_name = 'allowed_field_id'

    allowed_field_id = fields.Many2one('ab_accounting_allowed_field', required=True)
    group_id = fields.Many2one('ab_accounting_auth_group', required=True, index=True)
    allow_entry = fields.Boolean(default=True)
    allow_review = fields.Boolean(default=False)

    _sql_constraints = [
        ('ab_user_allowed_field_group_unique', 'UNIQUE(allowed_field_id,group_id)', 'Field an USER must be unique'),
    ]
