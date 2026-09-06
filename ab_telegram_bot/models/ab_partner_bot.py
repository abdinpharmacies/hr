import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class AbPartnerBot(models.Model):
    _name = "ab_partner_bot"
    _description = "Cost Center Telegram Account"
    _order = "costcenter_id, linked_at desc, id desc"
    _rec_name = "chat_id"

    _ab_partner_bot_chat_uniq = models.Constraint(
        "UNIQUE(chat_id)",
        "Each Telegram chat can only be linked once.",
    )

    costcenter_id = fields.Many2one(
        "ab_costcenter",
        string="Cost Center",
        required=True,
        index=True,
        ondelete="restrict",
    )
    employee_id = fields.Integer(
        string="Employee Record ID",
        index=True,
        help="Legacy technical employee record ID captured when the account was linked.",
    )
    employee_ref_id = fields.Char(
        string="Employee Reference",
        index=True,
        help="Optional external or business employee reference.",
    )
    telegram_user_id = fields.Char(string="Telegram User ID", index=True, copy=False)
    chat_id = fields.Char(string="Chat ID", required=True, index=True, copy=False)
    telegram_username = fields.Char(string="Telegram Username", index=True, copy=False)
    linked_at = fields.Datetime(string="Linked At", default=fields.Datetime.now, required=True)
    active = fields.Boolean(default=True)

    @api.model_create_multi
    def create(self, vals_list):
        prepared_vals_list = [self._prepare_vals(vals) for vals in vals_list]
        for vals in prepared_vals_list:
            self._check_duplicate_chat(vals.get("chat_id"))
        records = super().create(prepared_vals_list)
        for record in records:
            _logger.info(
                "ab_telegram_bot: created ab_partner_bot id=%s costcenter_id=%s chat_id=%s username=%s",
                record.id,
                record.costcenter_id.id,
                record.chat_id,
                record.telegram_username or "",
            )
        return records

    def write(self, vals):
        prepared_vals = self._prepare_vals(vals)
        if "chat_id" in prepared_vals:
            for record in self:
                record._check_duplicate_chat(prepared_vals.get("chat_id"), exclude_id=record.id)
        return super().write(prepared_vals)

    def unlink(self):
        self.write({"active": False})
        return True

    @api.model
    def _prepare_vals(self, vals):
        prepared_vals = dict(vals or {})
        if "chat_id" in prepared_vals:
            prepared_vals["chat_id"] = str(prepared_vals["chat_id"] or "").strip()
        if "telegram_username" in prepared_vals:
            prepared_vals["telegram_username"] = str(prepared_vals["telegram_username"] or "").strip().lstrip("@")
        if "telegram_user_id" in prepared_vals:
            prepared_vals["telegram_user_id"] = str(prepared_vals["telegram_user_id"] or "").strip()
        if "employee_id" in prepared_vals:
            prepared_vals["employee_id"] = int(prepared_vals["employee_id"] or 0)
        if "employee_ref_id" in prepared_vals:
            prepared_vals["employee_ref_id"] = str(prepared_vals["employee_ref_id"] or "").strip()
        return prepared_vals

    @api.model
    def _check_duplicate_chat(self, chat_id, exclude_id=False):
        chat_id = str(chat_id or "").strip()
        if not chat_id:
            return
        domain = [("chat_id", "=", chat_id)]
        if exclude_id:
            domain.append(("id", "!=", exclude_id))
        existing = self.with_context(active_test=False).sudo().search(domain, limit=1)
        if existing:
            raise ValidationError(_("This Telegram chat ID is already linked to another cost center."))

    @api.constrains("costcenter_id", "chat_id")
    def _check_required_values(self):
        for record in self:
            if not record.costcenter_id:
                raise ValidationError(_("Cost center is required."))
            if not record.chat_id:
                raise ValidationError(_("Telegram chat ID is required."))

    @api.model
    def register_employee_chat(
        self,
        employee_id,
        chat_id,
        telegram_username=False,
        employee_ref_id=False,
        telegram_user_id=False,
    ):
        try:
            Employee = self.env["ab_hr_employee"]
        except KeyError:
            raise ValidationError(_("HR module is not available."))
        employee = Employee.sudo().browse(int(employee_id or 0)).exists()
        if not employee:
            raise ValidationError(_("Employee not found."))
        if not employee.costcenter_id:
            raise ValidationError(_("Employee has no cost center."))
        return self.register_costcenter_chat(
            employee.costcenter_id.id,
            chat_id,
            telegram_username=telegram_username,
            employee_id=employee.id,
            employee_ref_id=employee_ref_id,
            telegram_user_id=telegram_user_id,
        )

    @api.model
    def register_costcenter_chat(
        self,
        costcenter_id,
        chat_id,
        telegram_username=False,
        employee_id=False,
        employee_ref_id=False,
        telegram_user_id=False,
        linked_at=False,
    ):
        costcenter = self.env["ab_costcenter"].sudo().browse(int(costcenter_id or 0)).exists()
        if not costcenter:
            raise ValidationError(_("Cost center is required."))
        normalized_chat_id = str(chat_id or "").strip()
        if not normalized_chat_id:
            raise ValidationError(_("Telegram chat ID is required."))
        existing = self.with_context(active_test=False).sudo().search([("chat_id", "=", normalized_chat_id)], limit=1)
        vals = {
            "costcenter_id": costcenter.id,
            "chat_id": normalized_chat_id,
            "telegram_username": str(telegram_username or "").strip().lstrip("@") or False,
            "employee_id": int(employee_id or 0),
            "employee_ref_id": str(employee_ref_id or "").strip() or False,
            "telegram_user_id": str(telegram_user_id or "").strip() or False,
            "linked_at": linked_at or fields.Datetime.now(),
            "active": True,
        }
        if existing:
            if existing.costcenter_id != costcenter:
                raise ValidationError(_("This Telegram chat ID is already linked to another cost center."))
            existing.write(vals)
            return existing
        return self.sudo().create(vals)

    @api.model
    def _normalize_costcenter_code(self, value):
        return re.sub(r"[^0-9A-Za-z]+", "", value or "").upper()

    @api.model
    def _extract_costcenter_code(self, text):
        cleaned = (text or "").strip()
        if not cleaned:
            return False
        normalized = " ".join(cleaned.replace("_", " ").replace("-", " ").split())
        parts = normalized.split()
        if (
            len(parts) == 1
            and self._normalize_costcenter_code(parts[0])
            and any(char.isdigit() for char in parts[0])
        ):
            return parts[0]
        command_words = {"employee", "emp", "code", "link", "hr", "costcenter", "cost", "center"}
        if not any(part.lower() in command_words for part in parts):
            return False
        candidates = [part for part in parts if part.lower() not in command_words]
        return candidates[-1] if candidates else False

    @api.model
    def _find_costcenter_by_code(self, code):
        normalized_code = self._normalize_costcenter_code(code)
        if not normalized_code:
            return self.env["ab_costcenter"]
        CostCenter = self.env["ab_costcenter"].sudo()
        costcenter = CostCenter.search([("code", "=", code), ("active", "=", True)], limit=2)
        if len(costcenter) == 1:
            return costcenter
        candidates = CostCenter.search([("active", "=", True)])
        matched = candidates.filtered(lambda rec: self._normalize_costcenter_code(rec.code) == normalized_code)
        if len(matched) == 1:
            return matched
        return self.env["ab_costcenter"]

    @api.model
    def bot_process_message(
        self,
        telegram_user_id,
        telegram_chat_id,
        text,
        username=False,
        first_name=False,
        last_name=False,
        phone=False,
        language_code=False,
        chat_type=False,
    ):
        code = self._extract_costcenter_code(text)
        if not code:
            return {"handled": False}
        costcenter = self._find_costcenter_by_code(code)
        if not costcenter:
            return {
                "handled": True,
                "text": _("No active cost center was found for code: %s") % code,
                "note": "costcenter_not_found",
            }
        self.register_costcenter_chat(
            costcenter.id,
            telegram_chat_id,
            telegram_username=username,
            telegram_user_id=telegram_user_id,
        )
        return {
            "handled": True,
            "text": _("Telegram account linked to cost center %s.") % costcenter.display_name,
            "note": "costcenter_telegram_linked",
            "costcenter_id": costcenter.id,
        }

    @api.model
    def _get_latest_active_account_for_costcenter(self, costcenter):
        costcenter = costcenter.sudo().exists() if costcenter else costcenter
        if not costcenter:
            return self.env["ab_partner_bot"]
        return self.sudo().search(
            [
                ("costcenter_id", "=", costcenter.id),
                ("active", "=", True),
                ("chat_id", "!=", False),
                ("chat_id", "!=", ""),
            ],
            order="linked_at desc, id desc",
            limit=1,
        )

    @api.model
    def get_account_for_record(self, recipient):
        recipient = recipient.sudo().exists() if recipient else recipient
        if not recipient:
            return self.env["ab_partner_bot"]
        if len(recipient) > 1:
            recipient = recipient[:1]
        if recipient._name == "ab_partner_bot":
            return recipient if recipient.active and recipient.chat_id else self.env["ab_partner_bot"]
        if "telegram_account_id" in recipient._fields and recipient.telegram_account_id:
            account = recipient.telegram_account_id.sudo()
            return account if account.active and account.chat_id else self.env["ab_partner_bot"]
        costcenter = self.env["ab_costcenter"]
        if "costcenter_id" in recipient._fields and recipient.costcenter_id:
            costcenter = recipient.costcenter_id
        elif "employee_id" in recipient._fields and recipient.employee_id and "costcenter_id" in recipient.employee_id._fields:
            costcenter = recipient.employee_id.costcenter_id
        return self._get_latest_active_account_for_costcenter(costcenter)

    @api.model
    def get_chat_id_for_record(self, recipient):
        account = self.get_account_for_record(recipient)
        return str(account.chat_id or "").strip() if account else False

    @api.model
    def get_account_for_employee(self, employee):
        return self.get_account_for_record(employee)

    @api.model
    def get_chat_id_for_employee(self, employee):
        return self.get_chat_id_for_record(employee)
