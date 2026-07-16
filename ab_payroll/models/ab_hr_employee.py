# -*- coding: utf-8 -*-
import logging
import re

from odoo import api, fields, models
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)

TELEGRAM_SERVICE_MODEL = "ab_telegram_service"


class AbHrEmployee(models.Model):
    _inherit = "ab_hr_employee"

    telegram_chat_id = fields.Char(
        string="Telegram Chat ID",
        groups="ab_hr.group_ab_hr_co,ab_payroll.group_ab_hr_payroll_sheet_admin",
        copy=False,
    )
    telegram_user_id = fields.Char(
        string="Telegram User ID",
        groups="ab_hr.group_ab_hr_co,ab_payroll.group_ab_hr_payroll_sheet_admin",
        copy=False,
    )
    telegram_username = fields.Char(
        string="Telegram Username",
        groups="ab_hr.group_ab_hr_co,ab_payroll.group_ab_hr_payroll_sheet_admin",
        copy=False,
    )
    telegram_linked_at = fields.Datetime(
        string="Telegram Linked At",
        groups="ab_hr.group_ab_hr_co,ab_payroll.group_ab_hr_payroll_sheet_admin",
        readonly=True,
        copy=False,
    )

    @api.model
    def _normalize_telegram_employee_code(self, value):
        return re.sub(r"[^0-9A-Za-z]+", "", value or "").upper()

    @api.model
    def _extract_telegram_employee_code(self, text):
        cleaned = (text or "").strip()
        if not cleaned:
            return False
        normalized = " ".join(cleaned.replace("_", " ").replace("-", " ").split())
        parts = normalized.split()
        if len(parts) == 1 and self._normalize_telegram_employee_code(parts[0]) and any(char.isdigit() for char in parts[0]):
            return parts[0]
        command_words = {"employee", "emp", "code", "link", "hr", "موظف", "كود", "ربط"}
        if not any(part.lower() in command_words for part in parts):
            return False
        candidates = [part for part in parts if part.lower() not in command_words]
        return candidates[-1] if candidates else False

    @api.model
    def _find_employee_by_telegram_code(self, code):
        normalized_code = self._normalize_telegram_employee_code(code)
        if not normalized_code:
            return self
        fields_to_check = [field for field in ("barcode", "identification_id", "accid") if field in self._fields]
        employee = self.sudo().search([("costcenter_id.code", "=", code), ("active", "=", True)], limit=2)
        if len(employee) == 1:
            return employee
        for field_name in fields_to_check:
            employee = self.sudo().search([(field_name, "=", code), ("active", "=", True)], limit=2)
            if len(employee) == 1:
                return employee
        candidates = self.sudo().search([("active", "=", True)])
        matched = candidates.filtered(
            lambda emp: (
                self._normalize_telegram_employee_code(emp.costcenter_id.code) == normalized_code
                or any(self._normalize_telegram_employee_code(emp[field_name]) == normalized_code for field_name in fields_to_check)
            )
        )
        if len(matched) == 1:
            return matched
        return self

    @api.model
    def _find_telegram_chat_message_by_employee_code(self, code):
        if "ab_telegram_chat_message" not in self.env:
            return False
        normalized_code = self._normalize_telegram_employee_code(code)
        if not normalized_code:
            return False
        messages = self.env["ab_telegram_chat_message"].sudo().search(
            [
                ("chat_type", "=", "private"),
                ("content_text", "!=", False),
            ],
            order="message_datetime desc, id desc",
            limit=100,
        )
        return messages.filtered(
            lambda message: self._normalize_telegram_employee_code(message.content_text) == normalized_code
        )[:1]

    @api.model
    def link_employee_from_telegram_chat_message(self, code):
        message = self._find_telegram_chat_message_by_employee_code(code)
        if not message:
            return {"handled": False}
        return self.bot_process_employee_telegram_link(
            telegram_user_id=message.telegram_user_id,
            telegram_chat_id=message.telegram_chat_id,
            text=message.content_text,
            username=message.username,
        )

    @api.model
    def _prepare_employee_telegram_message_data(self, message):
        message = message or {}
        chat = message.get("chat") or {}
        sender = message.get("from") or {}
        if sender.get("is_bot") or chat.get("type") != "private":
            return False
        text = (message.get("text") or "").strip()
        if not text:
            return False
        return {
            "telegram_user_id": str(sender.get("id") or chat.get("id") or "").strip(),
            "telegram_chat_id": str(chat.get("id") or "").strip(),
            "text": text,
            "username": (sender.get("username") or "").strip(),
        }

    @api.model
    def _get_message_from_telegram_update(self, update):
        update = update or {}
        return update.get("message") or update.get("edited_message") or {}

    @api.model
    def _get_employee_telegram_service(self):
        if TELEGRAM_SERVICE_MODEL not in self.env:
            return False
        return self.env[TELEGRAM_SERVICE_MODEL].sudo()

    @api.model
    def import_employee_telegram_updates(self, limit=100, acknowledge=True):
        """One-time Telegram import for HR employee chat IDs.

        Employees send their HR code to the bot. This method pulls pending
        Telegram updates, matches the message text to an employee code, and
        stores the Telegram identifiers on ab_hr_employee.
        """
        result = {
            "updates_seen": 0,
            "linked": 0,
            "ignored": 0,
            "not_employee_code": 0,
            "employee_not_found": 0,
            "employee_not_active": 0,
            "errors": [],
            "linked_employee_ids": [],
        }
        telegram_service = self._get_employee_telegram_service()
        if telegram_service is False:
            result["errors"].append(_("Telegram service is not installed."))
            return result

        updates = telegram_service.get_updates(limit=limit, timeout=0)
        result["updates_seen"] = len(updates)
        last_update_id = False
        for update in updates:
            if update.get("update_id") is not None:
                last_update_id = update["update_id"]
            message_data = self._prepare_employee_telegram_message_data(
                self._get_message_from_telegram_update(update)
            )
            if not message_data:
                result["ignored"] += 1
                continue
            code = self._extract_telegram_employee_code(message_data["text"])
            if not code:
                result["not_employee_code"] += 1
                continue
            employee = self._find_employee_by_telegram_code(code)
            if not employee:
                result["employee_not_found"] += 1
                result["errors"].append(_("No active employee was found for code: %s") % code)
                continue
            payload = self.bot_process_employee_telegram_link(**message_data)
            note = payload.get("note")
            if note == "employee_telegram_linked":
                result["linked"] += 1
                result["linked_employee_ids"].append(employee.id)
            elif note == "employee_not_active":
                result["employee_not_active"] += 1
                result["errors"].append(payload.get("text") or _("Employee is not active."))
            elif note == "employee_not_found":
                result["employee_not_found"] += 1
                result["errors"].append(payload.get("text") or _("Employee was not found."))
            else:
                result["ignored"] += 1

        if acknowledge and last_update_id is not False:
            telegram_service.get_updates(
                offset=last_update_id + 1,
                limit=1,
                timeout=0,
            )
            result["acknowledged_to"] = last_update_id + 1
        result["linked_employee_ids"] = list(dict.fromkeys(result["linked_employee_ids"]))
        return result

    @api.model
    def _cron_import_employee_telegram_updates(self):
        if self._get_employee_telegram_service() is False:
            return False
        result = self.sudo().import_employee_telegram_updates(limit=100, acknowledge=True)
        if result.get("updates_seen") or result.get("linked") or result.get("errors"):
            _logger.info(
                "ab_payroll: employee Telegram import updates_seen=%s linked=%s ignored=%s not_employee_code=%s "
                "employee_not_found=%s employee_not_active=%s errors=%s",
                result.get("updates_seen"),
                result.get("linked"),
                result.get("ignored"),
                result.get("not_employee_code"),
                result.get("employee_not_found"),
                result.get("employee_not_active"),
                result.get("errors"),
            )
        return result

    @api.model
    def bot_process_employee_telegram_link(
        self,
        telegram_user_id,
        telegram_chat_id,
        text,
        username="",
        **kwargs
    ):
        code = self._extract_telegram_employee_code(text)
        if not code:
            return {"handled": False}
        employee = self._find_employee_by_telegram_code(code)
        if not employee:
            return {
                "handled": True,
                "text": _("No active employee was found for code: %s") % code,
                "note": "employee_not_found",
            }
        if employee.job_status and employee.job_status != "active":
            return {
                "handled": True,
                "text": _("Employee code %s is not active.") % code,
                "note": "employee_not_active",
            }
        employee.sudo().write({
            "telegram_chat_id": str(telegram_chat_id or "").strip() or False,
            "telegram_user_id": str(telegram_user_id or "").strip() or False,
            "telegram_username": (username or "").strip() or False,
            "telegram_linked_at": fields.Datetime.now(),
        })
        if "ab_hr_bot" in self.env:
            self.env["ab_hr_bot"].sudo().try_register_employee_chat(
                employee.id,
                str(telegram_chat_id or "").strip(),
                telegram_username=(username or "").strip() or False,
            )
        return {
            "handled": True,
            "text": _("Telegram account linked to employee %s.") % employee.display_name,
            "note": "employee_telegram_linked",
        }
