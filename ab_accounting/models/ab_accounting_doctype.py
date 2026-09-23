# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ClsDocType(models.Model):
    _name = 'ab_accounting_doctype'
    _description = 'ab_accounting_doctype'
    _order = 'name'
    name = fields.Char()
    internal_type = fields.Selection(selection=lambda self: self._get_internal_type_selection())

    def _get_internal_type_selection(self):
        account_guide = self.env['ab_accounting_account_guide']
        account_guide_fields = account_guide.fields_get(allfields=['internal_type'])
        return account_guide_fields['internal_type']['selection']

    _sql_constraints = [
        ('ab_accounting_doctype_name_unique', 'unique(name)', 'NAME CAN NOT BE DUPLICATED.'),
    ]
