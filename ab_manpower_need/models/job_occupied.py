from odoo import api, fields, models


class JobOccupied(models.Model):
    _inherit = 'ab_hr_job_occupied'

    def _manpower_plan_scope(self):
        return {(record.workplace.id, record.job_id.id) for record in self}

    @api.model
    def _refresh_manpower_plans(self, scope):
        if not scope:
            return
        domain = fields.Domain.OR([
            fields.Domain('workplace', '=', workplace)
            & fields.Domain('job_title', 'in', [False, job])
            for workplace, job in scope
            if workplace
        ])
        # Assignment permissions are checked by super before this bounded refresh.
        self.env['ab_hr_manpower_hour_need'].sudo().search(domain)._auto_fetch_actual_capacity()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._refresh_manpower_plans(records._manpower_plan_scope())
        return records

    def write(self, vals):
        refresh = bool({'workplace', 'job_id', 'employee_id', 'issue_date', 'termination_date'} & vals.keys())
        old_scope = self._manpower_plan_scope() if refresh else set()
        result = super().write(vals)
        if refresh:
            self._refresh_manpower_plans(old_scope | self._manpower_plan_scope())
        return result

    def unlink(self):
        scope = self._manpower_plan_scope()
        result = super().unlink()
        self._refresh_manpower_plans(scope)
        return result
