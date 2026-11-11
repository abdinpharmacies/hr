from odoo import fields, models
from odoo.exceptions import UserError


def preserve_private_addresses(records):
    if records:
        raise UserError(records.env._('Private addresses must be securely migrated before removing this module.'))


class ResPartner(models.Model):
    _inherit = 'res.partner'

    type = fields.Selection(selection_add=[('private', 'Private Address')],
                            ondelete={'private': preserve_private_addresses})
