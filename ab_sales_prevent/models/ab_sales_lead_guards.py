from odoo import api, models


class AbSalesLead(models.Model):
    _name = "ab_sales_lead"
    _inherit = ["ab_sales_lead", "ab_sales_prevent.access.mixin"]

    def action_set_in_review(self):
        self._raise_sales_prevented()
        return super().action_set_in_review()

    def action_set_contacted(self):
        self._raise_sales_prevented()
        return super().action_set_contacted()

    def action_set_closed(self):
        self._raise_sales_prevented()
        return super().action_set_closed()

    def action_set_cancelled(self):
        self._raise_sales_prevented()
        return super().action_set_cancelled()

    @api.model
    def pos_create_lead(self, payload=None):
        self._raise_sales_prevented()
        return super().pos_create_lead(payload=payload)

    @api.model
    def pos_item_report(self, product_id=None):
        self._raise_sales_prevented()
        return super().pos_item_report(product_id=product_id)
