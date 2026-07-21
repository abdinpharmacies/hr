from odoo import api, models


class AbTelegramService(models.AbstractModel):
    _inherit = "ab_telegram_service"

    @api.model
    def _dispatch_telegram_message(self, message_data):
        result = super()._dispatch_telegram_message(message_data) or {}
        if result.get("note") == "employee_telegram_linked":
            self.env["ab_supplier_claim_telegram_registration"].sudo()._ensure_registration_from_employee_code(
                message_data.get("text")
            )
            return result
        if result.get("handled"):
            return result
        result = self.env["ab_supplier_claim_telegram_registration"].sudo()._link_employee_from_telegram_message(
            message_data
        ) or {}
        return result
