from odoo import api, models


class AbSalesPosApi(models.TransientModel):
    _inherit = "ab_sales_pos_api"

    @api.model
    def _pos_allowed_header_fields(self):
        return super()._pos_allowed_header_fields() | {"sales_channel_id"}
