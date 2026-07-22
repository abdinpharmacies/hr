import html
import logging

from odoo import _, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class AbQualityAssuranceVisit(models.Model):
    _inherit = "ab_quality_assurance_visit"

    telegram_submitted_manager_ids = fields.Char(readonly=True, copy=False)

    def _notify_visit_submitted(self):
        result = super()._notify_visit_submitted()
        self._notify_section_department_managers_telegram("submitted")
        return result

    def _notify_section_department_managers_telegram(self, status):
        TelegramBot = self.env["ab_telegram_bot"].sudo()
        for record in self:
            manager_sections = record._get_unique_section_department_managers()
            if not manager_sections:
                _logger.info(
                    "ab_quality_assurance: visit %s has no section department managers for Telegram notification.",
                    record.id,
                )
                continue

            sent_chat_ids = set()
            notified_manager_ids = record._get_telegram_notified_manager_ids(status)
            for manager_data in manager_sections.values():
                manager = manager_data["manager"]
                sections = manager_data["sections"]
                if manager.id in notified_manager_ids:
                    continue

                message = record._build_section_manager_telegram_message(status, sections)
                result = TelegramBot.send_to_record(manager, message)
                chat_id = result.get("chat_id")
                if result.get("sent") and chat_id and chat_id not in sent_chat_ids:
                    sent_chat_ids.add(chat_id)
                    record._mark_telegram_manager_notified(status, manager.id)
                _logger.info(
                    "ab_quality_assurance: section manager notification visit_id=%s manager_employee_id=%s status=%s sent=%s reason=%s",
                    record.id,
                    manager.id,
                    status,
                    result.get("sent"),
                    result.get("reason"),
                )

    def _get_telegram_notified_manager_ids(self, status):
        self.ensure_one()
        field_name = self._get_telegram_status_field_name(status)
        raw_value = self[field_name] or ""
        return {
            int(manager_id)
            for manager_id in raw_value.split(",")
            if manager_id.strip().isdigit()
        }

    def _mark_telegram_manager_notified(self, status, manager_id):
        self.ensure_one()
        field_name = self._get_telegram_status_field_name(status)
        notified_manager_ids = self._get_telegram_notified_manager_ids(status)
        notified_manager_ids.add(manager_id)
        value = ",".join(str(current_id) for current_id in sorted(notified_manager_ids))
        super(AbQualityAssuranceVisit, self.sudo().with_context(allow_submitted_visit_write=True)).write(
            {field_name: value}
        )

    def _get_telegram_status_field_name(self, status):
        if status == "submitted":
            return "telegram_submitted_manager_ids"
        raise ValidationError(_("Unsupported Telegram notification status."))

    def _get_unique_section_department_managers(self):
        self.ensure_one()
        manager_sections = {}
        for section in self.visit_section_ids:
            manager = section.department_manager_id
            if not manager:
                continue
            if manager.id not in manager_sections:
                manager_sections[manager.id] = {
                    "manager": manager,
                    "sections": self.env["ab_quality_assurance_visit_section"],
                }
            manager_sections[manager.id]["sections"] |= section
        return manager_sections

    def _build_section_manager_telegram_message(self, status, sections):
        self.ensure_one()
        status_label = _("Submitted")
        title = _("Quality Assurance Visit Submitted")
        section_names = [
            section.name
            for section in sections.sorted(lambda current_section: (current_section.sequence, current_section.id))
            if section.name
        ]
        lines = [
            "📋 <b>%s</b>" % html.escape(title),
            "<b>%s:</b> %s" % (html.escape(_("Reference")), html.escape(self.name or "N/A")),
            "<b>%s:</b> %s" % (html.escape(_("Department")), html.escape(self.department_id.name or "N/A")),
            "<b>%s:</b> %s" % (html.escape(_("Status")), html.escape(status_label)),
        ]
        if section_names:
            lines.append("<b>%s:</b> %s" % (html.escape(_("Sections")), html.escape(", ".join(section_names))))
        lines.extend(
            [
                "",
                html.escape(_("A Quality Assurance Visit requires your review.")),
                html.escape(_("Please review the assigned standards/evaluations and take the required action.")),
            ]
        )
        return "\n".join(lines)
