"""Return indicators from branch-confirmed callcenter return records."""
from odoo import api, fields, models


class BillReturnStatus(models.Model):
    _inherit = 'ab_sales_header'

    has_returns = fields.Boolean(
        string='Has Returns', compute='_compute_has_returns', compute_sudo=False,
        help='Whether this bill has a confirmed return recorded in the callcenter.',
    )

    @api.depends('store_id', 'eplus_serial')
    def _compute_has_returns(self):
        linked = self.filtered(lambda bill: bill.store_id and bill.eplus_serial)
        returned = set()
        if linked:
            domain = (fields.Domain('status', '=', 'saved')
                      & fields.Domain('store_id', 'in', linked.store_id.ids)
                      & fields.Domain('origin_header_id', 'in', linked.mapped('eplus_serial')))
            groups = self.env['ab_sales_return_header'].with_context(active_test=False)._read_group(
                domain, ['store_id', 'origin_header_id'], ['__count'],
            )
            returned = {(store.id, invoice) for store, invoice, _count in groups}
        for bill in self:
            bill.has_returns = (bill.store_id.id, bill.eplus_serial) in returned


class ReturnBillStatusInvalidation(models.Model):
    _inherit = 'ab_sales_return_header'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env['ab_sales_header'].invalidate_model(['has_returns'])
        return records

    def write(self, vals):
        result = super().write(vals)
        if {'status', 'store_id', 'origin_header_id'}.intersection(vals):
            self.env['ab_sales_header'].invalidate_model(['has_returns'])
        return result
