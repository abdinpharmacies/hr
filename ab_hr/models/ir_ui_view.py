from odoo import api, models


class PayrollViewOwnership(models.Model):
    _inherit = 'ir.ui.view'

    @api.model
    def _get_filter_xmlid_query(self):
        """Do not load payroll views early through their legacy ab_hr aliases.

        Odoo filters upgrade-time inheritance by XML-ID module. The preserved
        ab_hr aliases otherwise make payroll's inherited views appear loaded
        before ab_hr_payroll has registered its fields. No view is changed:
        once its owning module is loaded the normal inheritance applies.
        """
        query = super()._get_filter_xmlid_query()
        return """
            SELECT candidate.res_id FROM (""" + query + """) AS candidate
            WHERE NOT EXISTS (
                SELECT 1 FROM ir_model_data AS owner
                WHERE owner.model = 'ir.ui.view'
                  AND owner.res_id = candidate.res_id
                  AND owner.module = 'ab_hr_payroll'
                  AND owner.module NOT IN %(modules)s
            )
        """
