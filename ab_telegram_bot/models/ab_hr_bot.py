import logging

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class AbHrBot(models.Model):
    _name = "ab_hr_bot"
    _description = "Employee Telegram Chat Mapping"
    _order = "employee_id"
    _rec_name = "telegram_username"

    _ab_hr_bot_employee_uniq = models.Constraint(
        "UNIQUE(employee_id)",
        "Each employee can only be linked to one Telegram chat.",
    )
    _ab_hr_bot_chat_uniq = models.Constraint(
        "UNIQUE(chat_id)",
        "Each Telegram chat can only be linked to one employee.",
    )

    employee_id = fields.Integer(
        string="Employee Record ID",
        required=True,
        index=True,
        help="Technical record ID of the employee in the HR module.",
    )
    employee_ref_id = fields.Integer(
        string="Employee Reference",
        index=True,
        help="Optional external or business employee reference.",
    )
    chat_id = fields.Char(required=True, index=True, copy=False)
    telegram_username = fields.Char(index=True, copy=False)

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

            existing_exact = self.search([("chat_id", "=", chat_id), ("employee_id", "=", employee_id)], limit=1)
            if existing_exact:
                final_records |= existing_exact
                continue

            existing_chat = self.search([("chat_id", "=", chat_id)], limit=1)
            if existing_chat:
                self._notify_chat_employee_conflict(existing_chat, employee_id)
                final_records |= existing_chat
                continue

            existing_employee = self.search([("employee_id", "=", employee_id)], limit=1)
            if existing_employee:
                self._notify_employee_chat_conflict(employee_id, existing_employee, chat_id)
                final_records |= existing_employee
                continue

            to_create_vals.append(vals)

        if to_create_vals:
            new_records = super().create(to_create_vals)
            for record in new_records:
                _logger.info(
                    "ab_telegram_bot: created ab_hr_bot id=%s employee_id=%s chat_id=%s username=%s",
                    record.id,
                    record.employee_id,
                    record.chat_id,
                    record.telegram_username or "",
                )
            final_records |= new_records

        return final_records

    def write(self, vals):
        prepared_vals = self._prepare_vals(vals)
        if not {"chat_id", "employee_id"} & set(prepared_vals):
            return super().write(prepared_vals)

        result = True
        for record in self:
            safe_vals = prepared_vals.copy()
            new_chat_id = safe_vals.get("chat_id", record.chat_id)
            new_employee_id = safe_vals.get("employee_id", record.employee_id)

            if new_chat_id == record.chat_id and new_employee_id == record.employee_id:
                result &= super(AbHrBot, record).write(safe_vals)
                continue

            existing_exact = self.search(
                [("chat_id", "=", new_chat_id), ("employee_id", "=", new_employee_id), ("id", "!=", record.id)],
                limit=1,
            )
            if existing_exact:
                safe_vals.pop("chat_id", None)
                safe_vals.pop("employee_id", None)
                if safe_vals:
                    result &= super(AbHrBot, record).write(safe_vals)
                continue

            if "chat_id" in safe_vals and safe_vals["chat_id"] != record.chat_id:
                existing_chat = self.search([("chat_id", "=", safe_vals["chat_id"]), ("id", "!=", record.id)], limit=1)
                if existing_chat:
                    self._notify_chat_employee_conflict(existing_chat, new_employee_id)
                    safe_vals.pop("chat_id", None)

            if "employee_id" in safe_vals and safe_vals["employee_id"] != record.employee_id:
                existing_employee = self.search(
                    [("employee_id", "=", safe_vals["employee_id"]), ("id", "!=", record.id)],
                    limit=1,
                )
                if existing_employee:
                    self._notify_employee_chat_conflict(safe_vals["employee_id"], existing_employee, new_chat_id)
                    safe_vals.pop("employee_id", None)

            if safe_vals:
                result &= super(AbHrBot, record).write(safe_vals)
                _logger.info(
                    "ab_telegram_bot: updated ab_hr_bot id=%s employee_id=%s chat_id=%s username=%s",
                    record.id,
                    record.employee_id,
                    record.chat_id,
                    record.telegram_username or "",
                )
        return result

    @api.model
    def _prepare_vals(self, vals):
        prepared_vals = dict(vals or {})
        if "employee_id" in prepared_vals:
            prepared_vals["employee_id"] = int(prepared_vals["employee_id"] or 0)
        if "employee_ref_id" in prepared_vals:
            prepared_vals["employee_ref_id"] = int(prepared_vals["employee_ref_id"] or 0)
        if "chat_id" in prepared_vals:
            prepared_vals["chat_id"] = str(prepared_vals["chat_id"] or "").strip()
        if "telegram_username" in prepared_vals:
            prepared_vals["telegram_username"] = str(prepared_vals["telegram_username"] or "").strip().lstrip("@")
        return prepared_vals

    @api.constrains("employee_id", "chat_id")
    def _check_required_values(self):
        for record in self:
            if not record.employee_id:
                raise ValidationError("Employee record ID is required.")
            if not record.chat_id:
                raise ValidationError("Telegram chat ID is required.")

    @api.model
    def register_employee_chat(self, employee_id, chat_id, telegram_username=False, employee_ref_id=False):
        normalized_chat_id = str(chat_id or "").strip()
        normalized_username = str(telegram_username or "").strip().lstrip("@")
        employee_id = int(employee_id or 0)
        if not employee_id:
            raise ValidationError("Employee record ID is required.")
        if not normalized_chat_id:
            raise ValidationError("Telegram chat ID is required.")
        return self.create(
            {
                "employee_id": employee_id,
                "employee_ref_id": int(employee_ref_id or 0),
                "chat_id": normalized_chat_id,
                "telegram_username": normalized_username or False,
            }
        )

    @api.model
    def get_chat_id_for_employee(self, employee):
        employee = employee.sudo().exists() if employee else employee
        if not employee:
            return False
        link = self.sudo().search([("employee_id", "=", employee.id)], limit=1)
        return link.chat_id if link else False

    @api.model
    def _notify_chat_employee_conflict(self, existing_chat_link, attempted_employee_id):
        _logger.warning(
            "ab_telegram_bot: chat conflict detected chat_id=%s existing_employee_id=%s attempted_employee_id=%s",
            existing_chat_link.chat_id,
            existing_chat_link.employee_id,
            attempted_employee_id,
        )
        self.env["ab_telegram_bot"].sudo().send_message(
            existing_chat_link.chat_id,
            "Validation Error: This Telegram chat is already linked to another employee. "
            "Identity reassignment is blocked.",
        )

    @api.model
    def _notify_employee_chat_conflict(self, employee_id, existing_employee_link, attempted_chat_id):
        _logger.warning(
            "ab_telegram_bot: employee conflict detected employee_id=%s existing_chat_id=%s attempted_chat_id=%s",
            employee_id,
            existing_employee_link.chat_id,
            attempted_chat_id,
        )
        self.env["ab_telegram_bot"].sudo().send_message(
            attempted_chat_id,
            "Validation Warning: This employee is already linked to a different Telegram chat_id.",
        )
