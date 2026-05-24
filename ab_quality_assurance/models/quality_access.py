from odoo import models


QUALITY_DEPARTMENT_NAMES = (
    "ادارة الرقابة والجودة",
    "إدارة الرقابة والجودة",
    "Quality Assurance",
)


class AbQualityAssuranceAccess(models.AbstractModel):
    _name = "ab_quality_assurance.access"
    _description = "Quality Assurance Access Sync"

    def _sync_quality_manager_group(self):
        manager_group = self.env.ref("ab_quality_assurance.group_ab_quality_assurance_manager")
        departments = self.env["ab_hr_department"].sudo().search([])
        quality_departments = departments.filtered(
            lambda department: (department.name or "").strip() in QUALITY_DEPARTMENT_NAMES
        )
        manager_users = quality_departments.mapped("manager_id.user_id").filtered(lambda user: user)
        if manager_users:
            manager_users.sudo().write({"group_ids": [(4, manager_group.id)]})
        return True
