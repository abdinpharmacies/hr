import logging
import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class AbHrBot(models.Model):
    _name = "ab_hr_bot"
    _description = "Employee Telegram Chat Mapping"
    _order = "employee_id"
    _rec_name = "employee_id"

    _ab_hr_bot_employee_uniq = models.Constraint(
        "UNIQUE(employee_id)",
        "Each employee can only be linked to one Telegram chat.",
    )
    _ab_hr_bot_chat_uniq = models.Constraint(
        "UNIQUE(chat_id)",
        "Each Telegram chat can only be linked to one employee.",
    )

    employee_id = fields.Many2one(
        "ab_hr_employee",
        required=True,
        ondelete="restrict",
        index=True,
    )
    employee_ref_id = fields.Integer(
        string="Employee ID",
        compute="_compute_employee_ref_id",
        store=True,
    )
    chat_id = fields.Char(required=True, index=True, copy=False)
    telegram_username = fields.Char(index=True, copy=False)

    @api.depends("employee_id")
    def _compute_employee_ref_id(self):
        for record in self:
            record.employee_ref_id = record.employee_id.id or 0

    @api.model_create_multi
    def create(self, vals_list):
        prepared_vals_list = [self._prepare_vals(vals) for vals in vals_list]
        final_records = self.env["ab_hr_bot"]
        to_create_vals = []

        for vals in prepared_vals_list:
            chat_id = vals.get("chat_id")
            employee_id = vals.get("employee_id")

            if not chat_id or not employee_id:
                to_create_vals.append(vals)
                continue

            # Case C: Exact (chat_id + employee_id) exists
            existing_exact = self.search([("chat_id", "=", chat_id), ("employee_id", "=", employee_id)], limit=1)
            if existing_exact:
                final_records |= existing_exact
                continue

            # Case A: chat_id exists but linked to another employee_id
            existing_chat = self.search([("chat_id", "=", chat_id)], limit=1)
            if existing_chat:
                employee = self.env["ab_hr_employee"].browse(employee_id)
                self._notify_chat_employee_conflict(existing_chat, employee)
                final_records |= existing_chat
                continue

            # Case B: employee_id exists with different chat_id
            existing_employee = self.search([("employee_id", "=", employee_id)], limit=1)
            if existing_employee:
                employee = self.env["ab_hr_employee"].browse(employee_id)
                self._notify_employee_chat_conflict(employee, existing_employee, chat_id)
                final_records |= existing_employee
                continue

            # Case D: New (chat_id + employee_id)
            to_create_vals.append(vals)

        if to_create_vals:
            new_records = super().create(to_create_vals)
            for record in new_records:
                _logger.info(
                    "ab_request_telegram: created ab_hr_bot id=%s employee_id=%s chat_id=%s username=%s",
                    record.id,
                    record.employee_id.id,
                    record.chat_id,
                    record.telegram_username or "",
                )
            final_records |= new_records

        return final_records

    def write(self, vals):
        prepared_vals = self._prepare_vals(vals)
        if not {"chat_id", "employee_id"} & set(prepared_vals):
            return super().write(prepared_vals)

        # Apply updates record by record to handle conflicts silently
        result = True
        for record in self:
            safe_vals = prepared_vals.copy()
            new_chat_id = safe_vals.get("chat_id", record.chat_id)
            new_employee_id = safe_vals.get("employee_id", record.employee_id.id)

            if new_chat_id == record.chat_id and new_employee_id == record.employee_id.id:
                # No change to bindings
                result &= super(AbHrBot, record).write(safe_vals)
                continue

            # Check Case C: exact (chat_id + employee_id) exists elsewhere
            existing_exact = self.search(
                [("chat_id", "=", new_chat_id), ("employee_id", "=", new_employee_id), ("id", "!=", record.id)],
                limit=1,
            )
            if existing_exact:
                # Silently skip binding update
                safe_vals.pop("chat_id", None)
                safe_vals.pop("employee_id", None)
                if safe_vals:
                    result &= super(AbHrBot, record).write(safe_vals)
                continue

            # Check Case A: chat_id conflict
            if "chat_id" in safe_vals and safe_vals["chat_id"] != record.chat_id:
                existing_chat = self.search([("chat_id", "=", safe_vals["chat_id"]), ("id", "!=", record.id)], limit=1)
                if existing_chat:
                    employee = self.env["ab_hr_employee"].browse(new_employee_id)
                    self._notify_chat_employee_conflict(existing_chat, employee)
                    safe_vals.pop("chat_id", None)

            # Check Case B: employee_id conflict
            if "employee_id" in safe_vals and safe_vals["employee_id"] != record.employee_id.id:
                existing_employee = self.search(
                    [("employee_id", "=", safe_vals["employee_id"]), ("id", "!=", record.id)],
                    limit=1,
                )
                if existing_employee:
                    employee = self.env["ab_hr_employee"].browse(safe_vals["employee_id"])
                    self._notify_employee_chat_conflict(employee, existing_employee, new_chat_id)
                    safe_vals.pop("employee_id", None)

            if safe_vals:
                result &= super(AbHrBot, record).write(safe_vals)
                _logger.info(
                    "ab_request_telegram: updated ab_hr_bot id=%s employee_id=%s chat_id=%s username=%s",
                    record.id,
                    record.employee_id.id,
                    record.chat_id,
                    record.telegram_username or "",
                )
        return result

    @api.model
    def _prepare_vals(self, vals):
        prepared_vals = dict(vals or {})
        if "chat_id" in prepared_vals:
            prepared_vals["chat_id"] = str(prepared_vals["chat_id"] or "").strip()
        if "telegram_username" in prepared_vals:
            prepared_vals["telegram_username"] = (
                str(prepared_vals["telegram_username"] or "").strip().lstrip("@")
            )
        return prepared_vals

    @api.constrains("chat_id")
    def _check_chat_id(self):
        for record in self:
            if not record.chat_id:
                raise ValidationError("Telegram chat ID is required.")

    @api.model
    def register_employee_chat(self, employee_id, chat_id, telegram_username=False):
        employee = self.env["ab_hr_employee"].search([("id", "=", int(employee_id))], limit=1)
        normalized_chat_id = str(chat_id or "").strip()
        normalized_username = str(telegram_username or "").strip().lstrip("@")
        if not employee:
            raise ValidationError("Invalid employee ID.")
        if not normalized_chat_id:
            raise ValidationError("Telegram chat ID is required.")

        result = self.try_register_employee_chat(
            employee.id, normalized_chat_id, telegram_username=normalized_username
        )
        return result["link"]

    @api.model
    def try_register_employee_chat(self, employee_id, chat_id, telegram_username=False):
        employee = self.env["ab_hr_employee"].search([("id", "=", int(employee_id))], limit=1)
        normalized_chat_id = str(chat_id or "").strip()
        normalized_username = str(telegram_username or "").strip().lstrip("@")
        if not employee:
            return {"status": "invalid_employee_id", "link": self.browse()}
        if not normalized_chat_id:
            return {"status": "missing_chat_id", "link": self.browse()}

        existing_chat_link = self.search([("chat_id", "=", normalized_chat_id)], limit=1)
        if existing_chat_link:
            if existing_chat_link.employee_id and existing_chat_link.employee_id != employee:
                self._notify_chat_employee_conflict(existing_chat_link, employee)
                return {"status": "chat_conflict", "link": existing_chat_link}
            return {"status": "existing", "link": existing_chat_link}

        existing_employee_link = self.search([("employee_id", "=", employee.id)], limit=1)
        if existing_employee_link:
            if existing_employee_link.chat_id != normalized_chat_id:
                self._notify_employee_chat_conflict(employee, existing_employee_link, normalized_chat_id)
                return {"status": "employee_conflict", "link": existing_employee_link}
            return {"status": "existing", "link": existing_employee_link}

        try:
            link = self.create(
                {
                    "employee_id": employee.id,
                    "chat_id": normalized_chat_id,
                    "telegram_username": normalized_username or False,
                }
            )
        except ValidationError as exc:
            _logger.warning(
                "ab_request_telegram: safe registration failed chat_id=%s employee_id=%s reason=%s",
                normalized_chat_id,
                employee.id,
                str(exc),
            )
            return {"status": "binding_conflict", "link": self.browse()}
        return {"status": "created", "link": link}

    @api.model
    def find_or_register_employee_chat(self, employee):
        employee = employee.sudo().exists()
        if not employee:
            return self.browse()

        existing_link = self.search([("employee_id", "=", employee.id)], limit=1)
        if existing_link:
            return existing_link
        return self._auto_register_employee_chat(employee)

    @api.model
    def _auto_register_employee_chat(self, employee):
        employee = employee.sudo().exists()
        if not employee:
            return self.browse()

        updates = self.env["ab.telegram.service"].get_updates(limit=100)
        if not updates:
            _logger.info(
                "ab_request_telegram: no Telegram updates available for employee_id=%s auto-registration.",
                employee.id,
            )
            return self.browse()

        match = self._find_employee_update_match(employee, updates)
        if not match:
            _logger.info(
                "ab_request_telegram: no Telegram update matched employee_id=%s identifiers=%s",
                employee.id,
                sorted(self._get_employee_telegram_identifiers(employee)),
            )
            return self.browse()

        result = self.try_register_employee_chat(
            employee.id,
            match["chat_id"],
            telegram_username=match.get("telegram_username"),
        )
        return result["link"] if result["status"] in {"created", "existing"} else self.browse()

    @api.model
    def _notify_chat_employee_conflict(self, existing_chat_link, attempted_employee):
        manager_message = (
            "Validation Warning: This chat_id is already linked to another employee. "
            "Possible identity conflict detected."
        )
        employee_message = (
            "Validation Error: This Telegram chat is already linked to another employee. "
            "Identity reassignment is blocked."
        )
        _logger.warning(
            "ab_request_telegram: chat conflict detected chat_id=%s existing_employee_id=%s attempted_employee_id=%s",
            existing_chat_link.chat_id,
            existing_chat_link.employee_id.id,
            attempted_employee.id,
        )

        # Collect all chat_ids to notify
        notifications = {existing_chat_link.chat_id: employee_message}

        # Add managers to notifications, but don't overwrite the employee_message if it's the same chat
        for employee in [existing_chat_link.employee_id, attempted_employee]:
            manager_chat_id = self._get_manager_chat_id(employee)
            if manager_chat_id and manager_chat_id not in notifications:
                notifications[manager_chat_id] = manager_message

        # Send unique messages
        for chat_id, message in notifications.items():
            self.env["ab.telegram.service"].send_telegram_message(chat_id, message)

    @api.model
    def _notify_employee_chat_conflict(self, employee, existing_employee_link, attempted_chat_id):
        manager_message = "Validation Warning: This employee is already linked to a different Telegram chat_id."
        _logger.warning(
            "ab_request_telegram: employee conflict detected employee_id=%s existing_chat_id=%s attempted_chat_id=%s",
            employee.id,
            existing_employee_link.chat_id,
            attempted_chat_id,
        )

        notifications = {attempted_chat_id: manager_message}
        manager_chat_id = self._get_manager_chat_id(employee)
        if manager_chat_id:
            notifications[manager_chat_id] = manager_message

        for chat_id, message in notifications.items():
            self.env["ab.telegram.service"].send_telegram_message(chat_id, message)

    @api.model
    def _get_manager_chat_id(self, employee):
        employee = employee.sudo().exists()
        if not employee or not employee.department_id.manager_id:
            return False
        manager = employee.department_id.manager_id
        manager_link = self.search([("employee_id", "=", manager.id)], limit=1)
        return manager_link.chat_id if manager_link else False

    @api.model
    def _notify_manager_links(self, employees, message):
        # This method is now legacy but kept for compatibility if needed elsewhere
        sent_chat_ids = set()
        for employee in employees:
            chat_id = self._get_manager_chat_id(employee)
            if chat_id and chat_id not in sent_chat_ids:
                self.env["ab.telegram.service"].send_telegram_message(chat_id, message)
                sent_chat_ids.add(chat_id)

    @api.model
    def _get_employee_telegram_identifiers(self, employee):
        employee = employee.sudo()
        values = {
            str(employee.id),
            employee.name or "",
            employee.english_name or "",
            employee.barcode or "",
            employee.identification_id or "",
            employee.work_email or "",
        }
        if employee.user_id:
            values.update(
                {
                    employee.user_id.login or "",
                    employee.user_id.name or "",
                    employee.user_id.email or "",
                }
            )

        normalized_values = set()
        for value in values:
            normalized_value = self._normalize_telegram_identifier(value)
            if normalized_value:
                normalized_values.add(normalized_value)
                if "@" in normalized_value:
                    normalized_values.add(normalized_value.split("@", 1)[0])
        return normalized_values

    @api.model
    def _normalize_telegram_identifier(self, value):
        normalized_value = str(value or "").strip().lower().lstrip("@")
        if not normalized_value:
            return ""
        normalized_value = re.sub(r"\s+", " ", normalized_value)
        return normalized_value

    @api.model
    def _find_employee_update_match(self, employee, updates):
        identifiers = self._get_employee_telegram_identifiers(employee)
        if not identifiers:
            return False

        exact_username_match = False
        exact_text_match = False
        for update in reversed(updates):
            for payload_key in ("message", "edited_message"):
                message = update.get(payload_key) or {}
                chat = message.get("chat") or {}
                sender = message.get("from") or {}
                if chat.get("type") != "private" or sender.get("is_bot"):
                    continue

                username = self._normalize_telegram_identifier(sender.get("username"))
                text = self._normalize_telegram_identifier(message.get("text"))
                if username and username in identifiers:
                    if exact_username_match:
                        _logger.warning(
                            "ab_request_telegram: multiple Telegram username matches detected for employee_id=%s; using latest chat_id=%s",
                            employee.id,
                            chat.get("id"),
                        )
                    exact_username_match = {
                        "chat_id": chat.get("id"),
                        "telegram_username": sender.get("username") or False,
                    }
                    break

                if text and text in identifiers:
                    if exact_text_match:
                        _logger.warning(
                            "ab_request_telegram: multiple Telegram identifier-text matches detected for employee_id=%s; using latest chat_id=%s",
                            employee.id,
                            chat.get("id"),
                        )
                    exact_text_match = {
                        "chat_id": chat.get("id"),
                        "telegram_username": sender.get("username") or False,
                    }
            if exact_username_match:
                return exact_username_match
            if exact_text_match:
                return exact_text_match
        return exact_text_match or False

    @api.model
    def process_telegram_update(self, payload):
        _logger.info("ab_request_telegram: received raw webhook payload keys=%s", sorted((payload or {}).keys()))
        message = payload.get("message") or {}
        if not message:
            return {"ok": True, "message": "ignored"}

        chat = message.get("chat") or {}
        sender = message.get("from") or {}
        return self._process_private_message(
            chat_id=chat.get("id"),
            chat_type=chat.get("type") or "",
            text=(message.get("text") or "").strip(),
            telegram_username=(sender.get("username") or "").strip(),
            is_bot=bool(sender.get("is_bot")),
            send_feedback=True,
        )

    @api.model
    def _process_private_message(self, chat_id, chat_type, text, telegram_username=False, is_bot=False, send_feedback=True):
        if is_bot or not chat_id or chat_type != "private":
            return {"ok": True, "message": "ignored"}

        if text.lower().startswith("/start"):
            if send_feedback:
                self.env["ab.telegram.service"].send_telegram_message(
                    chat_id,
                    "Send your employee ID to link this Telegram chat with your employee record.",
                )
            return {"ok": True, "message": "start_acknowledged"}

        if not text.isdigit():
            _logger.warning(
                "ab_request_telegram: invalid employee identifier from chat_id=%s text=%s",
                chat_id,
                text,
            )
            if send_feedback:
                self.env["ab.telegram.service"].send_telegram_message(
                    chat_id,
                    "Invalid employee ID. Please send the numeric employee ID from Odoo.",
                )
            return {"ok": False, "message": "invalid_employee_id"}

        result = self.try_register_employee_chat(int(text), chat_id, telegram_username=telegram_username)
        if result["status"] == "invalid_employee_id":
            _logger.warning(
                "ab_request_telegram: employee link failed for chat_id=%s employee_id=%s reason=invalid_employee_id",
                chat_id,
                text,
            )
            if send_feedback:
                self.env["ab.telegram.service"].send_telegram_message(
                    chat_id,
                    "Employee ID not found. Please verify the ID and try again.",
                )
            return {"ok": False, "message": "employee_not_found"}
        if result["status"] in {"chat_conflict", "employee_conflict", "binding_conflict"}:
            return {"ok": True, "message": "binding_conflict"}
        if result["status"] == "missing_chat_id":
            return {"ok": True, "message": "ignored"}
        if result["status"] == "existing":
            return {"ok": True, "message": "existing"}
        link = result["link"]

        if send_feedback and result["status"] == "created":
            self.env["ab.telegram.service"].send_telegram_message(
                chat_id,
                f"Telegram chat linked successfully to employee: {link.employee_id.name}",
            )
        return {"ok": True, "message": "linked"}

    @api.model
    def bot_process_message(
        self,
        telegram_chat_id,
        text,
        username=False,
        chat_type="private",
        telegram_user_id=False,
        first_name=False,
        last_name=False,
        phone=False,
        language_code=False,
    ):
        _logger.info(
            "ab_request_telegram: bot_process_message chat_id=%s chat_type=%s text=%s username=%s",
            telegram_chat_id,
            chat_type,
            text,
            username or "",
        )
        if chat_type != "private":
            return {}

        result = self._process_private_message(
            chat_id=telegram_chat_id,
            chat_type=chat_type,
            text=(text or "").strip(),
            telegram_username=username,
            is_bot=False,
            send_feedback=False,
        )
        if not result.get("message") in {
            "start_acknowledged",
            "linked",
            "existing",
            "invalid_employee_id",
            "employee_not_found",
            "binding_conflict",
        }:
            return {}
        text_map = {
            "start_acknowledged": "Send your employee ID to link this Telegram chat with your employee record.",
            "linked": "Employee link saved successfully.",
            "existing": "Your message was received.",
            "invalid_employee_id": "Invalid employee ID. Please send the numeric employee ID from Odoo.",
            "employee_not_found": "Employee ID not found. Please verify the ID and try again.",
            "binding_conflict": "Your message was received.",
        }
        return {
            "handled": True,
            "text": text_map.get(result.get("message"), "Done."),
            "keyboard_rows": [["/start"]],
        }
