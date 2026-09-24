from odoo import api, fields, models, _
from odoo.exceptions import UserError

PAYMENT_NATURE = [('cash', 'Cash'), ('non_cash', 'Non-cash')]
BUSINESS_CATEGORY = [('medicine', 'Medicine'), ('cosmetics', 'Cosmetics'), ('other', 'Other')]
TAX_CLASSIFICATION = [
    ('through_supplier', 'Through Supplier'),
    ('tax_payment', 'Tax Payment'),
    ('non_tax_payment', 'Non-tax Payment'),
]


class Supplier(models.Model):
    _inherit = 'ab_supplier'

    payment_nature = fields.Selection(PAYMENT_NATURE, required=True, default='non_cash')
    business_category = fields.Selection(BUSINESS_CATEGORY, required=True, default='other')

    @api.model
    def _search_display_name(self, operator, value):
        # Preserve the caller's operator, including negative searches.
        domains = [fields.Domain('name', operator, value), fields.Domain('code', operator, value)]
        return fields.Domain.AND(domains) if operator in ('not ilike', 'not like', '!=', 'not in') else fields.Domain.OR(domains)

    @api.ondelete(at_uninstall=True)
    def _prevent_supplier_deletion(self):
        raise UserError(_('Archive suppliers instead of deleting them.'))
