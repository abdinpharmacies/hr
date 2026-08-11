from odoo import fields, models, _
from odoo.exceptions import UserError


class AbSalesHeader(models.Model):
    _inherit = "ab_sales_header"

    sales_channel_id = fields.Many2one(
        "ab_sales_channel",
        string="Sales Channel",
        ondelete="restrict",
    )

    def _validate_before_push(self):
        super()._validate_before_push()
        for header in self:
            if not header.sales_channel_id:
                raise UserError(_("Sales channel is required before submit."))
