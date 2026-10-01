import logging

from odoo import fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AbSalesHeader(models.Model):
    _inherit = "ab_sales_header"

    delivery_notify = fields.Boolean(string="Notify Delivery Bot", default=False, copy=False)
    delivery_instructions = fields.Text(string="Delivery Instructions", copy=False)

    def _validate_delivery_notification(self):
        for header in self:
            if header.is_delivery and header.delivery_notify and not (header.delivery_instructions or "").strip():
                raise UserError(_("Delivery instructions are required when notifying the delivery bot."))

    def action_push_to_eplus(self):
        self.check_access("write")
        self._validate_delivery_notification()
        result = super().action_push_to_eplus()
        for header in self.filtered(
            lambda rec: rec.is_delivery and rec.delivery_notify
            and rec.eplus_serial and rec.push_state == "success"
        ):
            try:
                with self.env.cr.savepoint():
                    request = self.env["ab_delivery_request"].create_from_sale_header(header)
                    request.queue_send_to_telegram()
            except Exception:
                _logger.exception(
                    "Failed to queue delivery Telegram notification for sales header %s",
                    header.id,
                )
        return result
