from odoo import api, fields, models
from odoo.tools.translate import _
from odoo.exceptions import UserError


class AbInventoryHeader(models.Model):
    _name = 'ab_inventory_header'
    _description = 'ab_inventory_header'
    _inherit = 'ab_inventory_process'
    _rec_name = 'header_ref'
    _order = 'id desc'

    header_id = fields.Integer(index=True, readonly=True)
    model_ref = fields.Char(readonly=True, index=True)
    res_id = fields.Integer(readonly=True, index=True)
    header_ref = fields.Char(index=True, readonly=True)
    store_id = fields.Many2one('ab_store', readonly=True, index=True)
    to_store_id = fields.Many2one('ab_store', readonly=True, index=True)

    # transmitted_by = fields.Selection(
    #     selection=[('delivery', 'Delivery'),
    #                ('company_car', 'Company Car'),
    #                ('private_car', 'Private Car')],
    #     default='delivery')
    # delivery_id = fields.Many2one('ab_hr_employee')

    pending_main_count = fields.Integer(compute='_compute_pending')
    pending_store_count = fields.Integer(compute='_compute_pending')
    has_pending_main = fields.Boolean(compute='_compute_pending', search='_search_has_pending_main')
    has_pending_store = fields.Boolean(compute='_compute_pending', search='_search_has_pending_store')

    line_ids = fields.One2many('ab_inventory', 'header_id', string='Lines', readonly=True)
    pending_line_ids = fields.One2many('ab_inventory', 'header_id',
                                       domain=[('status', '!=', 'saved')],
                                       readonly=True,
                                       compute='_compute_pending_line_ids')
    action_id = fields.Many2one('ab_inventory_action', readonly=True)

    @api.depends('line_ids')
    def _compute_pending_line_ids(self):
        for rec in self:
            rec.pending_line_ids = rec.line_ids.filtered(lambda line: line.status != 'saved')

    def btn_open_header(self):
        if self.model_ref:
            return {
                "name": 'Source Header',
                "type": "ir.actions.act_window",
                "res_model": self.model_ref,
                "views": [[False, "form"]],
                "res_id": self.res_id,
                # "target": "main",
            }

    @api.depends('line_ids.status')
    def _compute_pending(self):
        inventory_mo = self.env['ab_inventory'].sudo()
        for rec in self:
            rec.pending_main_count = inventory_mo.search_count(
                [('header_id', '=', rec.id), ('status', '=', 'pending_main')])
            rec.has_pending_main = rec.pending_main_count > 0

            rec.pending_store_count = inventory_mo.search_count(
                [('header_id', '=', rec.id), ('status', '=', 'pending_store')])
            rec.has_pending_store = rec.pending_store_count > 0

    def _search_has_pending_main(self, operator, val):
        if operator not in ['=', '!='] or not isinstance(val, bool):
            raise UserError(_('Operation not supported'))
        if operator == '!=':
            val = not val

        headers = self._get_headers_with_status(status='pending_main')

        return [('id', 'in' if val else 'not in', headers)]

    def _search_has_pending_store(self, operator, val):
        if operator not in ['=', '!='] or not isinstance(val, bool):
            raise UserError(_('Operation not supported'))
        if operator == '!=':
            val = not val

        headers = self._get_headers_with_status(status='pending_store')
        return [('id', 'in' if val else 'not in', headers)]

    def _get_headers_with_status(self, status):
        inventory_mo = self.env['ab_inventory'].sudo()
        limit = 1000
        offset = 0
        headers = set()

        while len(headers) < 1000:
            lines = inventory_mo.search([('status', '=', status)], limit=limit, offset=offset)
            if not lines:
                break  # no more records to process

            for line in lines:
                # line.header_id RETURNS 'Integer', NOT 'Many2One'
                header_id = line.header_id.id
                headers.add(header_id)
                if len(headers) >= 1000:
                    break

            offset += limit  # move to next batch

        return list(headers)

    def btn_send_transfer(self):
        inventory = self.env['ab_inventory']
        lines = self.line_ids
        for line in lines:
            if self.to_store_id.id and line.status == 'pending_main':
                store_id = self.to_store_id.id
                line.store_id = store_id

    def btn_receive_transfer(self):
        lines = self.line_ids
        for line in lines:
            if self.to_store_id.id and line.status == 'pending_main':
                store_id = self.to_store_id.id
                line.status = 'saved'
