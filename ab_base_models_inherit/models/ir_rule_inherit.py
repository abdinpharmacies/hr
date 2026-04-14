from odoo import api, fields, models


class MyIrRule(models.Model):
    """Add ref to ir.rule context"""

    _name = "ir.rule"
    _inherit = "ir.rule"

    # @api.model
    # def _eval_context(self):
    #     context = super()._eval_context()
    #     context['ref'] = self.env.ref
    #     self.clear_cache()
    #     return context
