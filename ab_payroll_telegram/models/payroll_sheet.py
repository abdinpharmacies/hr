# -*- coding: utf-8 -*-
from odoo import api, models


class AbPayrollTelegramSheet(models.Model):
    _inherit = "ab.hr.payroll.sheet"

    @api.model
    def _resolve_recipient_chat_id(self, recipient):
        recipient = recipient.sudo().exists() if recipient else recipient
        if not recipient:
            return False
        telegram_service = self._get_telegram_service()
        if telegram_service is False:
            return False
        return telegram_service._get_recipient_chat_id(recipient)

    @api.model
    def _get_telegram_service(self):
        if "ab_telegram_bot" not in self.env:
            return False
        return self.env["ab_telegram_bot"].sudo()
