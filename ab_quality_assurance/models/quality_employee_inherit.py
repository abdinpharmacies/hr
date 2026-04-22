from odoo import api, models


class AbHrEmployee(models.Model):
    _inherit = "ab_hr_employee"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if any("user_id" in vals for vals in vals_list):
            records.env["ab_quality_assurance.access"].sudo()._sync_quality_manager_group()
        return records

    def write(self, vals):
        result = super().write(vals)
        if "user_id" in vals:
            self.env["ab_quality_assurance.access"].sudo()._sync_quality_manager_group()
        return result

    def unlink(self):
        result = super().unlink()
        self.env["ab_quality_assurance.access"].sudo()._sync_quality_manager_group()
        return result
