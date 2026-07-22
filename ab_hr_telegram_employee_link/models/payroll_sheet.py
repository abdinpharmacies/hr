# -*- coding: utf-8 -*-
from odoo import api, models


class AbHrPayrollSheet(models.Model):
    _inherit = "ab.hr.payroll.sheet"

    def _resolve_manager_chat_id(self):
        self.ensure_one()
        if not self.manager_id:
            return False
        telegram_service = self._get_telegram_service()
        if telegram_service is False:
            return False
        return telegram_service._get_recipient_chat_id(self.manager_id)

    def _resolve_employee_chat_id(self):
        self.ensure_one()
        if not self.employee_id:
            return False
        telegram_service = self._get_telegram_service()
        if telegram_service is False:
            return False
        return telegram_service._get_recipient_chat_id(self.employee_id)

    @api.model
    def _get_telegram_service(self):
        if "ab_telegram_bot" not in self.env:
            return False
        return self.env["ab_telegram_bot"].sudo()
