from odoo import fields, models
from odoo.exceptions import UserError


def preserve_account_classification(records):
    if records:
        raise UserError(records.env._('Legacy account classifications must be migrated before removing this module.'))


class AccountGuide(models.Model):
    _inherit = 'ab_accounting_account_guide'

    internal_type = fields.Selection(
        selection_add=[('contract_deduction', 'Contract Deduction')],
        ondelete={'contract_deduction': preserve_account_classification},
    )
