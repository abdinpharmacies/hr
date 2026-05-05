import html
import logging

from odoo import models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class AbRequest(models.Model):
    _inherit = "ab_request"

    def _notify_request_created(self):
        result = super()._notify_request_created()
        self.filtered(lambda record: record.state != "draft")._notify_department_manager_telegram()
        return result

    def _notify_department_manager_telegram(self):
        BotLink = self.env["ab_hr_bot"].sudo()
        TelegramService = self.env["ab.telegram.service"]
        for record in self:
            manager = record.manager_id or record.request_type_id.department_id.manager_id
            if not manager:
                _logger.info("ab_request_telegram: request %s has no department manager.", record.id)
                continue

            try:
                bot_link = BotLink.find_or_register_employee_chat(manager)
            except ValidationError as exc:
                _logger.warning(
                    "ab_request_telegram: manager Telegram binding conflict request_id=%s manager_employee_id=%s reason=%s",
                    record.id,
                    manager.id,
                    str(exc),
                )
                continue
            if not bot_link:
                _logger.info(
                    "ab_request_telegram: no Telegram mapping found or auto-created for manager employee_id=%s request_id=%s",
                    manager.id,
                    record.id,
                )
                continue

            sent = TelegramService.send_telegram_message(bot_link.chat_id, record._build_manager_telegram_message())
            _logger.info(
                "ab_request_telegram: manager notification request_id=%s manager_employee_id=%s chat_id=%s sent=%s",
                record.id,
                manager.id,
                bot_link.chat_id,
                sent,
            )

    def _build_manager_telegram_message(self):
        self.ensure_one()
        notification_kind = self._get_telegram_notification_kind()
        lines = [
            f"📢 <b>New {html.escape(notification_kind)}</b>",
            f"👤 <b>Employee:</b> {html.escape(self.employee_id.name or 'N/A')}",
            f"🏢 <b>Department:</b> {html.escape(self.department_id.name or 'N/A')}",
            f"📝 <b>Type:</b> {html.escape(self.request_type_id.name or self.request_category_id.name or 'N/A')}",
            f"📝 <b>Title:</b> {html.escape(self.subject or '')}",
            "",
            html.escape(self.description or ""),
        ]
        return "\n".join(lines)

    def _get_telegram_notification_kind(self):
        self.ensure_one()
        source_text = " ".join(
            filter(
                None,
                [
                    self.request_category_id.name,
                    self.request_type_id.name,
                ],
            )
        ).lower()
        complaint_markers = {"complaint", "complaints", "شكوى", "شكاوى"}
        if any(marker in source_text for marker in complaint_markers):
            return "Complaint"
        return "Request"
