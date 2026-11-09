# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class AbReconciliationEmployeeApproval(models.Model):
    _name = 'ab_reconciliation_employee_approval'
    _description = 'ab_reconciliation_employee_approval'

    account_id = fields.Many2one('ab_custody_request_account', domain=[('is_recon', '=', True)])
    employee_id = fields.Many2one('ab_hr_employee')
    store_ids = fields.Many2many(
        comodel_name='ab_store',
        relation='ab_recon_approval_store_rel',
        column1='recon_id',
        column2='store_id',
        string='Stores')
