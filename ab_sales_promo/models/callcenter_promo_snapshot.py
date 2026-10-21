from odoo import fields, models
from odoo.exceptions import AccessError


class PromotionSnapshot(models.Model):
    _inherit = 'ab_sales_header'

    callcenter_promo_snapshot = fields.Json(string='Recorded Promotion', readonly=True, copy=False)

    def _write_branch_state(self, vals):
        if vals.get('branch_submission_started'):
            for header in self:
                if not header.branch_submission_started or vals.get('branch_request_revision', 0) > header.branch_request_revision:
                    header._branch_records().write({'callcenter_promo_snapshot': {
                        'program_ids': header.applied_program_ids.ids,
                        'discount': header.promo_discount_amount,
                        'net': header.amount_total_after_promo,
                    }})
        return super()._write_branch_state(vals)

    def write(self, vals):
        if 'callcenter_promo_snapshot' in vals and not self._branch_internal():
            raise AccessError(self.env._('Recorded promotions cannot be edited.'))
        return super().write(vals)
