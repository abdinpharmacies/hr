# -*- coding: utf-8 -*-
import base64
import io
import os
import zipfile

from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _


class AbHrPayrollSheetUploadWizard(models.TransientModel):
    _name = "ab.hr.payroll.sheet.upload.wizard"
    _description = "Upload Payroll Sheets"

    payroll_type = fields.Selection(
        [("preliminary", "Preliminary"), ("final", "Final")],
        required=True,
        default="preliminary",
    )
    payroll_period = fields.Char(
        string="Payroll Period",
        required=True,
        default=lambda self: fields.Date.today().strftime("%Y-%m"),
        help="Monthly payroll period in YYYY-MM format.",
    )
    attachment_ids = fields.Many2many("ir.attachment", string="Files", required=True)
    distribution_scope = fields.Selection(
        [
            ("manager_only", "Managers Only"),
            ("manager_and_employee", "Managers and Employees"),
        ],
        string="Send To",
        required=True,
        default="manager_only",
    )
    queue_after_upload = fields.Boolean(string="Queue Distribution After Upload", default=False)

    def action_upload(self):
        self.ensure_one()
        Sheet = self.env["ab.hr.payroll.sheet"].sudo()
        created = self.env["ab.hr.payroll.sheet"]
        for attachment in self.attachment_ids:
            file_name = attachment.name or ""
            extension = os.path.splitext(file_name)[1].lstrip(".").lower()
            if extension == "zip":
                created |= self._create_from_zip(attachment)
            else:
                created |= Sheet.create(
                    {
                        "payroll_period": self.payroll_period,
                        "payroll_type": self.payroll_type,
                        "distribution_scope": self.distribution_scope,
                        "attachment_id": attachment.id,
                        "file_name": file_name,
                    }
                )
        if self.queue_after_upload and created:
            created.filtered(lambda rec: rec.state == "validated").action_queue_distribution()
        return {
            "type": "ir.actions.act_window",
            "name": _("Payroll Sheets"),
            "res_model": "ab.hr.payroll.sheet",
            "view_mode": "list,form",
            "domain": [("id", "in", created.ids)],
        }

    def _create_from_zip(self, attachment):
        self.ensure_one()
        Sheet = self.env["ab.hr.payroll.sheet"].sudo()
        created = self.env["ab.hr.payroll.sheet"]
        try:
            zip_bytes = base64.b64decode(attachment.datas or b"")
            archive = zipfile.ZipFile(io.BytesIO(zip_bytes))
        except (zipfile.BadZipFile, ValueError) as exc:
            raise UserError(_("Invalid ZIP file: %s") % attachment.name) from exc

        for entry in archive.infolist():
            if entry.is_dir():
                continue
            inner_name = os.path.basename(entry.filename)
            extension = os.path.splitext(inner_name)[1].lstrip(".").lower()
            if extension not in Sheet._allowed_extensions():
                continue
            file_datas = base64.b64encode(archive.read(entry.filename))
            inner_attachment = self.env["ir.attachment"].sudo().create(
                {
                    "name": inner_name,
                    "type": "binary",
                    "datas": file_datas,
                    "res_model": "ab.hr.payroll.sheet",
                }
            )
            sheet = Sheet.create(
                {
                    "payroll_period": self.payroll_period,
                    "payroll_type": self.payroll_type,
                    "distribution_scope": self.distribution_scope,
                    "attachment_id": inner_attachment.id,
                    "file_name": inner_name,
                }
            )
            inner_attachment.write({"res_id": sheet.id})
            created |= sheet
        return created
