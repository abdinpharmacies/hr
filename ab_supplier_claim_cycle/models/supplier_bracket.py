from odoo import api, models


class SupplierBracket(models.Model):
    _inherit = 'ab_supplier_bracket'

    @api.depends('payment_type', 'credit_days', 'discount')
    def _compute_display_name(self):
        # Reviewers need not read the cost-center master to select terms.
        labels = dict(self._fields['payment_type']._description_selection(self.env))
        for bracket in self:
            bracket.display_name = self.env._('%(payment)s · %(days)s days · %(discount)s%%',
                payment=labels.get(bracket.payment_type, self.env._('Payment Terms')),
                days=bracket.credit_days, discount=bracket.discount)
