import html
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class AbRequest(models.Model):
    _inherit = "ab_request"

    def _notify_request_created(self):
        result = super()._notify_request_created()
        self.filtered(lambda record: record.state != "draft")._notify_department_manager_telegram()
        return result

    def _notify_department_manager_telegram(self):
        TelegramBot = self.env["ab_telegram_bot"].sudo()
        for record in self:
            manager = record.manager_id or record.request_type_id.department_id.manager_id
            if not manager:
                _logger.info("ab_request_telegram: request %s has no department manager.", record.id)
                continue

            result = TelegramBot.send_to_record(manager, record._build_manager_telegram_message())
            _logger.info(
                "ab_request_telegram: manager notification request_id=%s manager_employee_id=%s sent=%s reason=%s",
                record.id,
                manager.id,
                result.get("sent"),
                result.get("reason"),
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
