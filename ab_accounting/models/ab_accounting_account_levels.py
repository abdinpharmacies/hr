from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class AccountingAccountLevel1(models.Model):
    _name = 'ab_accounting_account_first_level'
    _description = 'ab_accounting_account_first_level'

    name = fields.Char(required=True)
    internal_group = fields.Selection([
        ('equity', 'Equity'),
        ('asset', 'Asset'),
        ('liability', 'Liability'),
        ('income', 'Income'),
        ('expense', 'Expense'),
        ('off_balance', 'Off Balance'),

    ], string="Internal Group",
        required=True,
        help="The 'Internal Group' is used to filter accounts based on the internal group set on the account type.")

    nature = fields.Selection([
        ('debit', 'Debit'),
        ('credit', 'Credit'),
        ('switch', 'Switch'),
    ], compute='_compute_nature')

    @api.depends('internal_group')
    def _compute_nature(self):
        for rec in self:
            if rec.internal_group in ('asset', 'expense'):
                rec.nature = 'debit'
            elif rec.internal_group in ('equity', 'liability', 'income'):
                rec.nature = 'credit'
            else:
                rec.nature = 'switch'


class AccountingAccountLevel2(models.Model):
    _name = 'ab_accounting_account_second_level'
    _description = 'ab_accounting_account_second_level'

    account_first_level_id = fields.Many2one('ab_accounting_account_first_level', required=True)
    name = fields.Char(required=True)


class AccountingAccount(models.Model):
    _name = 'ab_accounting_account'
    _description = 'ab_accounting_account'

    account_second_level_id = fields.Many2one('ab_accounting_account_second_level', required=True)
    account_first_level_id = fields.Many2one(related='account_second_level_id.account_first_level_id')
    nature = fields.Selection(related='account_first_level_id.nature')
    internal_group = fields.Selection(related='account_first_level_id.internal_group')

    name = fields.Char(required=True)

    def copy(self, default=None):
        default = default or {}
        default['name'] = self.name + ' copy'
        return super().copy(default=default)

    _sql_constraints = [
        ('ab_accounting_account_name_unique', 'unique(name)', 'NAME CAN NOT BE DUPLICATED.'),
    ]
