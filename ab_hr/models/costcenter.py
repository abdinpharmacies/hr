from odoo import _, api, models
from odoo.exceptions import AccessError


HR_IDENTITY_FIELDS = frozenset({'identification_id', 'birthday'})


class CostCenter(models.Model):
    _inherit = 'ab_costcenter'

    @api.model
    def _is_basic_hr_only(self):
        basic = self.env.ref('ab_hr.group_ab_hr_basic_data', raise_if_not_found=False)
        if not basic:
            return False
        roles = self.env.user.all_group_ids & basic.sudo().privilege_id.group_ids
        return roles == basic

    @api.model
    def _check_hr_identity_export(self, names):
        if HR_IDENTITY_FIELDS.intersection(names) and self._is_basic_hr_only():
            raise AccessError(_("HR Basic Data users cannot export ID numbers or birth dates."))

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        result = super().fields_get(allfields, attributes)
        if attributes is None or 'exportable' in attributes:
            protected = HR_IDENTITY_FIELDS.intersection(result)
            if protected and self._is_basic_hr_only():
                for name in protected:
                    result[name]['exportable'] = False
        return result

    def _export_rows(self, fields, *, _is_toplevel_call=True):
        # Odoo calls this for direct exports and for related cost-center columns.
        self._check_hr_identity_export(path[0] for path in fields if path)
        return super()._export_rows(fields, _is_toplevel_call=_is_toplevel_call)
