from odoo import _, api, models
from odoo.exceptions import AccessError

QUALITY_DEPARTMENT_NAME = "ادارة الرقابة والجودة"


class AbQualityAssuranceAccess(models.AbstractModel):
    _name = "ab_quality_assurance.access"
    _description = "Quality Assurance Access Helpers"

    @api.model
    def _get_quality_departments(self):
        return self.env["ab_hr_department"].sudo().search([("name", "=", QUALITY_DEPARTMENT_NAME)])

    @api.model
    def _get_quality_manager_users(self):
        return self._get_quality_departments().mapped("manager_id.user_id").filtered(lambda user: user)

    @api.model
    def _is_quality_manager(self, user=None):
        current_user = user or self.env.user
        return current_user in self._get_quality_manager_users()

    @api.model
    def _is_quality_admin(self, user=None):
        current_user = user or self.env.user
        return current_user.has_group("ab_quality_assurance.group_ab_quality_assurance_admin")

    @api.model
    def _check_standard_management_access(self):
        if self._is_quality_admin() or self._is_quality_manager():
            return True
        raise AccessError(
            _("Only quality assurance administrators or the manager of %(department)s can manage standards.")
            % {"department": QUALITY_DEPARTMENT_NAME}
        )

    @api.model
    def _sync_quality_manager_group(self):
        group = self.env.ref("ab_quality_assurance.group_ab_quality_assurance_manager", raise_if_not_found=False)
        if not group:
            return

        target_users = self._get_quality_manager_users()
        current_users = self.env["res.users"].sudo().search([("group_ids", "in", group.id)])

        users_to_add = target_users - current_users
        users_to_remove = current_users - target_users

        if users_to_add:
            users_to_add.write({"group_ids": [(4, group.id)]})
        if users_to_remove:
            users_to_remove.write({"group_ids": [(3, group.id)]})
