import logging

from odoo import models

_logger = logging.getLogger(__name__)


class AbSalesHeader(models.Model):
    _inherit = "ab_sales_header"

    def action_push_to_eplus(self):
        result = super().action_push_to_eplus()
        for header in self.filtered(lambda rec: rec.is_delivery and rec.eplus_serial):
            try:
                request = self.env["ab_delivery_request"].sudo().create_from_sale_header(header)
                request.queue_send_to_telegram()
            except Exception:
                _logger.exception(
                    "Failed to queue delivery Telegram notification for sales header %s",
                    header.id,
                )
        return result
