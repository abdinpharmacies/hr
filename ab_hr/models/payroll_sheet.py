# -*- coding: utf-8 -*-
import base64
import hashlib
import logging
import os
import re
import unicodedata

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.translate import _

_logger = logging.getLogger(__name__)


class AbHrPayrollSheet(models.Model):
    _name = "ab.hr.payroll.sheet"
    _description = "Payroll Sheet Distribution"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "upload_date desc, id desc"
    _rec_name = "file_name"

    employee_id = fields.Many2one("ab_hr_employee", string="Employee", index=True, tracking=True)
    employee_code = fields.Char(index=True, copy=False, tracking=True)
    manager_id = fields.Many2one("ab_hr_employee", string="Direct Manager", index=True, tracking=True)
    department_id = fields.Many2one("ab_hr_department", string="Department", index=True, tracking=True, copy=False)
    payroll_period = fields.Char(
        string="Payroll Period",
        required=True,
        default=lambda self: fields.Date.today().strftime("%Y-%m"),
        index=True,
        tracking=True,
        help="Monthly payroll period in YYYY-MM format.",
    )
    payroll_type = fields.Selection(
        [("preliminary", "Preliminary"), ("final", "Final")],
        required=True,
        default="preliminary",
        index=True,
        tracking=True,
    )
    distribution_scope = fields.Selection(
        [
            ("manager_only", "Managers Only"),
            ("manager_and_employee", "Managers and Employees"),
        ],
        string="Send To",
        required=True,
        default="manager_only",
        tracking=True,
    )
    attachment_id = fields.Many2one("ir.attachment", string="Payroll File", ondelete="restrict", copy=False)
    payroll_file = fields.Binary(string="Payroll File", copy=False)
    payroll_file_name = fields.Char(string="Payroll Filename", copy=False)
    file_name = fields.Char(required=True, index=True, copy=False)
    file_extension = fields.Char(readonly=True, copy=False)
    file_checksum = fields.Char(index=True, readonly=True, copy=False)
    upload_date = fields.Datetime(default=fields.Datetime.now, readonly=True, index=True, copy=False)
    uploaded_by = fields.Many2one(
        "res.users",
        default=lambda self: self.env.user,
        readonly=True,
        index=True,
        copy=False,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("validated", "Validated"),
            ("queued", "Queued"),
            ("sent", "Sent"),
            ("delivered", "Delivered"),
            ("failed", "Failed"),
            ("archived", "Archived"),
        ],
        default="draft",
        required=True,
        index=True,
        tracking=True,
        copy=False,
    )
    telegram_chat_id = fields.Char(readonly=True, copy=False)
    telegram_message_id = fields.Char(readonly=True, copy=False)
    telegram_message_body = fields.Text(
        string="Telegram Message",
        copy=False,
        help="Message sent with the payroll file. It is initialized automatically and can be edited before sending.",
    )
    sent_date = fields.Datetime(readonly=True, copy=False)
    delivered_date = fields.Datetime(readonly=True, copy=False)
    retry_count = fields.Integer(default=0, readonly=True, copy=False)
    sheet_count = fields.Integer(default=1, readonly=True)
    last_error = fields.Text(readonly=True, copy=False)
    notes = fields.Text()
    audit_log = fields.Text(readonly=True, copy=False)
    active = fields.Boolean(default=True)

    @api.model_create_multi
    def create(self, vals_list):
        prepared_vals = []
        for vals in vals_list:
            vals = self._prepare_uploaded_file_values(dict(vals or {}))
            attachment = self.env["ir.attachment"].browse(vals.get("attachment_id")).exists()
            if attachment:
                vals.setdefault("file_name", attachment.name)
                vals.update(self._prepare_file_values(attachment, vals.get("file_name")))
            vals.setdefault("payroll_period", fields.Date.today().strftime("%Y-%m"))
            prepared_vals.append(vals)
        records = super().create(prepared_vals)
        for record in records:
            if record.attachment_id:
                record.attachment_id.sudo().write({"res_model": record._name, "res_id": record.id})
            record._append_audit(_("Uploaded by %s") % record.uploaded_by.display_name)
            record.action_validate()
        return records

    def write(self, vals):
        vals = dict(vals or {})
        if "payroll_file" not in vals:
            return super().write(vals)

        result = True
        for record in self:
            record_vals = record._prepare_uploaded_file_values(dict(vals), existing_record=record)
            attachment = self.env["ir.attachment"].browse(record_vals.get("attachment_id")).exists()
            if attachment:
                record_vals.setdefault("file_name", attachment.name)
                record_vals.update(record._prepare_file_values(attachment, record_vals.get("file_name")))
            result = super(AbHrPayrollSheet, record).write(record_vals) and result
            if record.attachment_id:
                record.attachment_id.sudo().write({"res_model": record._name, "res_id": record.id})
        return result

    def unlink(self):
        for record in self:
            record.action_archive()
        return True

    @api.constrains("attachment_id")
    def _check_attachment_required(self):
        for record in self:
            if not record.attachment_id:
                raise ValidationError(_("Payroll file is required."))

    @api.constrains("attachment_id", "file_name")
    def _check_file_type(self):
        for record in self:
            extension = record._get_file_extension(record.file_name)
            if extension not in record._allowed_extensions():
                raise ValidationError(_("Only PDF and XLSX payroll files are allowed."))

    @api.constrains("payroll_period")
    def _check_payroll_period(self):
        for record in self:
            if not re.match(r"^\d{4}-\d{2}$", record.payroll_period or ""):
                raise ValidationError(_("Payroll period must use YYYY-MM format, for example 2026-06."))

    @api.model
    def _duplicate_blocking_states(self):
        return ["validated", "queued", "sent", "delivered"]

    def _find_blocking_duplicate(self):
        self.ensure_one()
        if self.payroll_type == "preliminary":
            return self.browse()
        if not self.employee_id or not self.payroll_type or not self.payroll_period or not self.file_checksum:
            return self.browse()
        return self.with_context(active_test=False).search(
            [
                ("id", "!=", self.id),
                ("active", "=", True),
                ("employee_id", "=", self.employee_id.id),
                ("department_id", "=", self.department_id.id if self.department_id else False),
                ("payroll_type", "=", self.payroll_type),
                ("payroll_period", "=", self.payroll_period),
                ("file_checksum", "=", self.file_checksum),
                ("state", "in", self._duplicate_blocking_states()),
            ],
            limit=1,
        )

    @api.constrains("active", "employee_id", "department_id", "payroll_type", "payroll_period", "file_checksum", "state")
    def _check_duplicate_upload(self):
        for record in self.filtered(
            lambda rec: rec.employee_id
            and rec.payroll_type
            and rec.payroll_type != "preliminary"
            and rec.file_checksum
        ):
            duplicate = record._find_blocking_duplicate()
            if duplicate:
                raise ValidationError(
                    _(
                        "This payroll file already exists for employee %(employee)s, period %(period)s, and type %(type)s."
                    )
                    % {
                        "employee": record.employee_id.display_name,
                        "period": record.payroll_period,
                        "type": record.payroll_type,
                    }
                )

    @api.model
    def _allowed_extensions(self):
        return {"pdf", "xlsx"}

    @api.model
    def _get_file_extension(self, file_name):
        return os.path.splitext(file_name or "")[1].lstrip(".").lower()

    @api.model
    def _prepare_file_values(self, attachment, file_name=None):
        name = file_name or attachment.name or ""
        datas = attachment.datas or b""
        if isinstance(datas, str):
            datas = datas.encode()
        return {
            "file_extension": self._get_file_extension(name),
            "file_checksum": hashlib.sha256(datas).hexdigest() if datas else False,
        }

    @api.model
    def _prepare_uploaded_file_values(self, vals, existing_record=False):
        uploaded_file = vals.pop("payroll_file", False)
        uploaded_name = vals.get("payroll_file_name") or vals.get("file_name")
        if not uploaded_file:
            return vals

        if vals.get("attachment_id"):
            vals.setdefault("file_name", uploaded_name)
            return vals

        if existing_record and not uploaded_name:
            uploaded_name = existing_record.file_name
        uploaded_name = uploaded_name or _("Payroll File")
        attachment = self.env["ir.attachment"].sudo().create(
            {
                "name": uploaded_name,
                "type": "binary",
                "datas": uploaded_file,
                "res_model": self._name,
            }
        )
        vals["attachment_id"] = attachment.id
        vals["file_name"] = uploaded_name
        return vals

    @api.model
    def _parse_filename(self, file_name):
        base_name = os.path.basename(file_name or "")
        stem, extension = os.path.splitext(base_name)
        extension = extension.lstrip(".").lower()
        parts = [part.strip() for part in stem.split("_") if part.strip()]
        if len(parts) < 3:
            return {
                "valid": False,
                "reason": _("Filename must follow Employee_Full_Name_1234_Department.pdf format."),
                "extension": extension,
            }
        code_index = False
        for index, part in enumerate(parts):
            if any(char.isdigit() for char in part):
                code_index = index
                break
        if code_index is False:
            return {
                "valid": False,
                "reason": _("Filename must include the employee HR code."),
                "name_parts": parts,
                "extension": extension,
            }
        employee_code = parts[code_index]
        if code_index == 0:
            employee_name = " ".join(parts[1:-1])
            work_entity = parts[-1]
        else:
            employee_name = " ".join(parts[:code_index])
            work_entity = " ".join(parts[code_index + 1:])
        return {
            "valid": True,
            "name_parts": parts,
            "employee_code": employee_code,
            "employee_code_index": code_index,
            "employee_name": employee_name,
            "work_entity": work_entity,
            "extension": extension,
        }

    @api.model
    def _normalize_identifier(self, value):
        return re.sub(r"[^0-9A-Za-z]+", "", value or "").upper()

    @api.model
    def _normalize_payroll_text(self, value):
        value = unicodedata.normalize("NFKC", value or "")
        value = "".join(char for char in value if unicodedata.category(char) != "Mn")
        replacements = {
            "أ": "ا",
            "إ": "ا",
            "آ": "ا",
            "ٱ": "ا",
            "ة": "ه",
            "ى": "ي",
            "ؤ": "و",
            "ئ": "ي",
            "ـ": "",
        }
        for source, target in replacements.items():
            value = value.replace(source, target)
        return "".join(char for char in value.casefold() if char.isalnum())

    @api.model
    def _payroll_self_manager_job_names(self):
        return {"تسجيل مدير", "تسجيل صاحب"}

    @api.model
    def _is_payroll_self_manager_job(self, job):
        if not job or not job.job_id:
            return False
        job_name = self._normalize_payroll_text(job.job_id.name)
        return job_name in {self._normalize_payroll_text(name) for name in self._payroll_self_manager_job_names()}

    @api.model
    def _active_payroll_jobs(self, employee):
        jobs = employee.sudo().job_occupied_ids
        return jobs.filtered(lambda job: job.job_status == "active")

    @api.model
    def _job_matches_file_work_entity(self, job, work_entity):
        if not job.workplace or not work_entity:
            return False
        department_key = self._normalize_payroll_text(job.workplace.name)
        work_entity_key = self._normalize_payroll_text(work_entity)
        if not department_key or not work_entity_key:
            return False
        return department_key in work_entity_key or work_entity_key in department_key

    @api.model
    def _resolve_payroll_job_context(self, employee, parsed):
        active_jobs = self._active_payroll_jobs(employee)
        work_entity = parsed.get("work_entity")
        matched_jobs = active_jobs.filtered(lambda job: self._job_matches_file_work_entity(job, work_entity))

        parsed["active_role_count"] = len(active_jobs)
        if matched_jobs:
            parsed["matched_role_count"] = len(matched_jobs)

        if len(active_jobs) > 1:
            if len(matched_jobs) == 1:
                job = matched_jobs[0]
                parsed["role_match_method"] = "filename_department"
                return job, job.workplace, False
            if len(matched_jobs) > 1:
                return (
                    self.env["ab_hr_job_occupied"],
                    self.env["ab_hr_department"],
                    _("Filename department matches more than one active employee role."),
                )
            return (
                self.env["ab_hr_job_occupied"],
                self.env["ab_hr_department"],
                _("Employee has multiple active roles. The filename department must match one active role."),
            )

        if len(active_jobs) == 1:
            job = active_jobs[0]
            parsed["role_match_method"] = "single_active_role"
            return job, job.workplace or employee.department_id, False

        parsed["role_match_method"] = "employee_department"
        return self.env["ab_hr_job_occupied"], employee.department_id, False

    @api.model
    def _find_employee_for_file(self, file_name):
        parsed = self._parse_filename(file_name)
        if not parsed.get("valid"):
            return self.env["ab_hr_employee"], parsed

        Employee = self.env["ab_hr_employee"].sudo()
        code = parsed.get("employee_code")
        normalized_code = self._normalize_identifier(code)
        code_fields = [field for field in ("barcode", "identification_id", "accid") if field in Employee._fields]

        employee = Employee.search([("costcenter_id.code", "=", code)], limit=2)
        if len(employee) == 1:
            parsed["match_method"] = "costcenter_id.code"
            return employee, parsed

        for field_name in code_fields:
            employee = Employee.search([(field_name, "=", code)], limit=2)
            if len(employee) == 1:
                parsed["match_method"] = field_name
                return employee, parsed

        if normalized_code:
            candidates = Employee.search([]) if code_fields else Employee
            exact = candidates.filtered(
                lambda emp: (
                    self._normalize_identifier(emp.costcenter_id.code) == normalized_code
                    or any(self._normalize_identifier(emp[field_name]) == normalized_code for field_name in code_fields)
                )
            )
            if len(exact) == 1:
                parsed["match_method"] = "normalized_code"
                return exact, parsed

        parsed_employee_name = parsed.get("employee_name")
        if parsed_employee_name:
            employee = Employee.search([("name", "=", parsed_employee_name)], limit=2)
            if len(employee) == 1:
                parsed["match_method"] = "name"
                return employee, parsed

        name_parts = parsed.get("name_parts") or []
        code_index = parsed.get("employee_code_index")
        if code_index and code_index > 0:
            name_candidates = [" ".join(name_parts[:index]) for index in range(code_index, 0, -1)]
        else:
            name_candidates = [" ".join(name_parts[1:split_index]) for split_index in range(len(name_parts), 2, -1)]
        for employee_name in name_candidates:
            employee = Employee.search([("name", "=", employee_name)], limit=2)
            if len(employee) == 1:
                parsed["match_method"] = "name"
                parsed["employee_name"] = employee_name
                return employee, parsed

        parsed["reason"] = _("Employee could not be identified from filename.")
        return self.env["ab_hr_employee"], parsed

    def _resolve_manager(self, employee=False, department=False, job=False):
        self.ensure_one()
        employee = employee or self.employee_id
        department = department or self.department_id or employee.department_id
        if not employee:
            return self.env["ab_hr_employee"]
        if department and department.manager_id:
            return department.manager_id
        if job and job.job_manager_id:
            return job.job_manager_id
        if employee.parent_id:
            return employee.parent_id
        if self._is_payroll_self_manager_job(job):
            return employee
        return self.env["ab_hr_employee"]

    def _resolve_manager_chat_id(self):
        self.ensure_one()
        manager = self.manager_id
        if not manager:
            return False
        if manager.telegram_chat_id:
            return manager.telegram_chat_id
        if not manager.user_id:
            return False
        if "ab_user_telegram_link" not in self.env:
            return False
        link = self.env["ab_user_telegram_link"].sudo().search(
            [
                ("user_id", "=", manager.user_id.id),
                ("status", "in", ["linked", "stale"]),
                ("telegram_chat_id", "!=", False),
            ],
            limit=1,
        )
        return link.telegram_chat_id if link else False

    def _resolve_employee_chat_id(self):
        self.ensure_one()
        employee = self.employee_id
        if not employee:
            return False
        if employee.telegram_chat_id:
            return employee.telegram_chat_id
        if not employee.user_id:
            return False
        if "ab_user_telegram_link" not in self.env:
            return False
        link = self.env["ab_user_telegram_link"].sudo().search(
            [
                ("user_id", "=", employee.user_id.id),
                ("status", "in", ["linked", "stale"]),
                ("telegram_chat_id", "!=", False),
            ],
            limit=1,
        )
        return link.telegram_chat_id if link else False

    def _ensure_telegram_sender_token(self):
        icp = self.env["ir.config_parameter"].sudo()
        legacy_token = (icp.get_param("telebot_api_key") or "").strip()
        bot_token = (icp.get_param("telegram.bot.token") or "").strip()
        if not legacy_token and bot_token:
            icp.set_param("telebot_api_key", bot_token)
            legacy_token = bot_token
        if not legacy_token:
            raise UserError(_("Telegram bot token is missing. Configure system parameter telegram.bot.token."))
        return True

    def _get_telegram_recipients(self):
        self.ensure_one()
        recipients = []
        manager_chat_id = self._resolve_manager_chat_id()
        recipients.append(
            {
                "role": "manager",
                "label": _("Manager"),
                "employee": self.manager_id,
                "chat_id": manager_chat_id,
                "missing_message": _("Manager Telegram chat ID is missing for %s.") % (self.manager_id.display_name or "-"),
            }
        )
        if self.distribution_scope == "manager_and_employee":
            if self.employee_id != self.manager_id:
                employee_chat_id = self._resolve_employee_chat_id()
                recipients.append(
                    {
                        "role": "employee",
                        "label": _("Employee"),
                        "employee": self.employee_id,
                        "chat_id": employee_chat_id,
                        "missing_message": _("Employee Telegram chat ID is missing for %s.")
                        % (self.employee_id.display_name or "-"),
                    }
                )
        return recipients

    def _validate_telegram_recipients(self):
        self.ensure_one()
        self._ensure_telegram_sender_token()
        missing = []
        recipients = self._get_telegram_recipients()
        for recipient in recipients:
            if not recipient["employee"]:
                missing.append(_("%s record is missing.") % recipient["label"])
            elif not recipient["chat_id"]:
                missing.append(recipient["missing_message"])
        if missing:
            raise UserError("\n".join(missing))
        return recipients

    def _append_audit(self, message):
        now = fields.Datetime.to_string(fields.Datetime.now())
        for record in self:
            line = "[%s] %s" % (now, message)
            record.audit_log = "%s\n%s" % (record.audit_log or "", line)

    def _set_failed(self, reason):
        for record in self:
            record.write({"state": "failed", "last_error": reason})
            record._append_audit(_("Failed: %s") % reason)

    def action_validate(self):
        for record in self:
            parsed = record._parse_filename(record.file_name)
            if not parsed.get("valid"):
                record.write({"employee_code": parsed.get("employee_code") or False})
                record._set_failed(parsed.get("reason"))
                continue
            if parsed.get("extension") not in record._allowed_extensions():
                record._set_failed(_("Invalid file type: %s") % (parsed.get("extension") or "-"))
                continue

            employee, parsed = record._find_employee_for_file(record.file_name)
            if not employee:
                record.write({"employee_code": parsed.get("employee_code") or False})
                record._set_failed(parsed.get("reason") or _("Employee could not be identified."))
                continue
            job, department, role_error = record._resolve_payroll_job_context(employee, parsed)
            if role_error:
                record.write({"employee_id": employee.id, "employee_code": parsed.get("employee_code")})
                record._set_failed(role_error)
                continue

            if job and job.job_status and job.job_status != "active":
                record.write(
                    {
                        "employee_id": employee.id,
                        "employee_code": parsed.get("employee_code"),
                        "department_id": department.id if department else False,
                    }
                )
                record._set_failed(_("Employee role is not active."))
                continue
            if not job and employee.job_status and employee.job_status != "active":
                record.write(
                    {
                        "employee_id": employee.id,
                        "employee_code": parsed.get("employee_code"),
                        "department_id": department.id if department else False,
                    }
                )
                record._set_failed(_("Employee is not active."))
                continue

            manager = record._resolve_manager(employee=employee, department=department, job=job)
            duplicate = record.browse()
            if record.payroll_type != "preliminary":
                duplicate = record.search(
                    [
                        ("id", "!=", record.id),
                        ("active", "=", True),
                        ("employee_id", "=", employee.id),
                        ("department_id", "=", department.id if department else False),
                        ("payroll_type", "=", record.payroll_type),
                        ("payroll_period", "=", record.payroll_period),
                        ("file_checksum", "=", record.file_checksum),
                        ("state", "in", record._duplicate_blocking_states()),
                    ],
                    limit=1,
                )
            if duplicate:
                raise ValidationError(
                    _(
                        "This payroll file already exists for employee %(employee)s, period %(period)s, and type %(type)s."
                    )
                    % {
                        "employee": employee.display_name,
                        "period": record.payroll_period,
                        "type": record.payroll_type,
                    }
                )
            vals = {
                "employee_id": employee.id,
                "employee_code": parsed.get("employee_code"),
                "department_id": department.id if department else False,
                "manager_id": manager.id if manager else False,
                "state": "validated" if manager else "failed",
                "last_error": False if manager else _("Direct manager is missing."),
            }
            if not record.telegram_message_body:
                vals["telegram_message_body"] = record._default_telegram_message_text(employee, parsed.get("employee_code"))
            record.write(vals)
            record._append_audit(
                _("Validation result: employee=%s manager=%s match=%s role=%s department=%s")
                % (
                    employee.display_name,
                    manager.display_name if manager else "-",
                    parsed.get("match_method") or "-",
                    parsed.get("role_match_method") or "-",
                    department.display_name if department else "-",
                )
            )
            if not manager:
                record._append_audit(_("Failed: Direct manager is missing."))
        return True

    def action_queue_distribution(self):
        for record in self:
            if record.state == "sent":
                raise UserError(_("Payroll sheet has already been sent."))
            if record.state != "validated":
                record.action_validate()
            if record.state != "validated":
                continue
            try:
                record._validate_telegram_recipients()
            except Exception as exc:
                record._set_failed(str(exc))
                continue
            identity_key = "ab_hr_payroll_sheet_send_%s_%s" % (record.id, record.file_checksum or "")
            record.write({"state": "queued"})
            record._append_audit(_("Queued for Telegram distribution."))
            if "queue.job" in self.env:
                record.with_delay(identity_key=identity_key).send_payroll_sheet_telegram()
        return True

    @api.model
    def _cron_process_queued_payroll_sheets(self, limit=50):
        queued = self.sudo().search([("state", "=", "queued")], limit=limit)
        queued.send_payroll_sheet_telegram()
        return True

    def action_mark_delivered(self):
        now = fields.Datetime.now()
        for record in self:
            record.write({"state": "delivered", "delivered_date": now})
            record._append_audit(_("Marked delivered."))
        return True

    def action_archive(self):
        for record in self:
            record.write({"active": False, "state": "archived"})
            record._append_audit(_("Archived."))
        return True

    def _default_telegram_message_text(self, employee=False, employee_code=False):
        employee = employee or self.employee_id
        employee_code = employee_code or self.employee_code or "-"
        payroll_type = dict(self._fields["payroll_type"].selection).get(self.payroll_type, self.payroll_type)
        return _(
            "A new payroll sheet has been uploaded\n"
            "Employee: %(employee)s\n"
            "Employee Code: %(code)s\n"
            "Payroll Type: %(payroll_type)s"
        ) % {
            "employee": employee.display_name if employee else "-",
            "code": employee_code,
            "payroll_type": payroll_type,
        }

    def _telegram_message_text(self, recipient_role="manager"):
        self.ensure_one()
        if self.telegram_message_body:
            return self.telegram_message_body
        return _(
            "A copy of your payroll sheet has been sent\n"
            "Employee Code: %(code)s\n"
            "Payroll Type: %(payroll_type)s"
        ) % {
            "code": self.employee_code or "-",
            "payroll_type": dict(self._fields["payroll_type"].selection).get(self.payroll_type, self.payroll_type),
        } if recipient_role == "employee" else self._default_telegram_message_text()

    def _send_telegram_document(self, chat_id, recipient_role="manager"):
        self.ensure_one()
        if "abdin_telegram" not in self.env:
            raise UserError(_("Telegram sender module is not installed."))
        result = self.env["abdin_telegram"].sudo().send_by_bot(
            chat_id,
            msg=self._telegram_message_text(recipient_role=recipient_role),
            after="",
            name_ext=self.file_name,
            attachment=self.attachment_id.datas,
        )
        if result:
            raise UserError(_("%s Telegram send failed: %s") % (recipient_role, result))
        return "sent_by_abdin_telegram"

    def send_payroll_sheet_telegram(self):
        for record in self:
            try:
                if record.state == "sent":
                    record._append_audit(_("Skipped duplicate send attempt; already sent."))
                    continue
                if not record.employee_id or not record.manager_id:
                    record.action_validate()
                if not record.manager_id:
                    raise UserError(_("Direct manager is missing."))
                recipients = record._validate_telegram_recipients()
                send_results = []
                for recipient in recipients:
                    telegram_message_id = record._send_telegram_document(
                        recipient["chat_id"],
                        recipient_role=recipient["role"],
                    )
                    send_results.append("%s:%s" % (recipient["role"], telegram_message_id))
                record.write(
                    {
                        "state": "sent",
                        "telegram_chat_id": ",".join(recipient["chat_id"] for recipient in recipients),
                        "telegram_message_id": ",".join(send_results),
                        "sent_date": fields.Datetime.now(),
                        "last_error": False,
                    }
                )
                record._append_audit(
                    _("Telegram send result: sent to %s.")
                    % ", ".join("%s:%s" % (recipient["role"], recipient["chat_id"]) for recipient in recipients)
                )
            except Exception as exc:
                _logger.exception("Payroll sheet Telegram distribution failed for record %s", record.id)
                record.write({"retry_count": record.retry_count + 1})
                record._set_failed(str(exc))
        return True
