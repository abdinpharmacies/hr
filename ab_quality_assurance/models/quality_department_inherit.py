from odoo import api, models


class AbHrDepartment(models.Model):
    _inherit = "ab_hr_department"

    @staticmethod
    def _qa_should_sync_department(vals):
        return not vals or any(key in vals for key in ("name", "manager_id"))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if any(self._qa_should_sync_department(vals) for vals in vals_list):
            records.env["ab_quality_assurance.access"].sudo()._sync_quality_manager_group()
        return records

    def write(self, vals):
        result = super().write(vals)
        if self._qa_should_sync_department(vals):
            self.env["ab_quality_assurance.access"].sudo()._sync_quality_manager_group()
        return result

    def unlink(self):
        result = super().unlink()
        self.env["ab_quality_assurance.access"].sudo()._sync_quality_manager_group()
        return result
