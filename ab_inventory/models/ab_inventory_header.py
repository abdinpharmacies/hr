from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AbInventoryHeader(models.Model):
    _name = 'ab_inventory_header'
    _description = 'ab_inventory_header'
    _inherit = 'ab_inventory_process'
    _rec_name = 'header_ref'

    header_id = fields.Integer(index=True, readonly=True)
    model_ref = fields.Char(readonly=True, index=True)
    res_id = fields.Integer(readonly=True, index=True)
    header_ref = fields.Char(index=True, readonly=True)
    store_id = fields.Many2one('ab_store', readonly=True, index=True)

    pending_main_count = fields.Integer(compute='_compute_pending')
    pending_store_count = fields.Integer(compute='_compute_pending')
    has_pending_main = fields.Boolean(compute='_compute_pending', search='_search_has_pending_main')
    has_pending_store = fields.Boolean(compute='_compute_pending', search='_search_has_pending_store')

    line_ids = fields.One2many('ab_inventory', 'header_id', string='Lines', readonly=True)

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
        inventory_mo = self.env['ab_inventory'].sudo()
        if operator not in ['=', '!='] or not isinstance(val, bool):
            raise UserError(_('Operation not supported'))

        ids = inventory_mo.search([('status', '=', 'pending_main')]).mapped('header_id')

        if operator != '=':  # that means it is '!='
            val = not val
        return [('id', 'in' if val else 'not in', ids)]

    def _search_has_pending_store(self, operator, val):
        inventory_mo = self.env['ab_inventory'].sudo()
        if operator not in ['=', '!='] or not isinstance(val, bool):
            raise UserError(_('Operation not supported'))

        ids = inventory_mo.search([('status', '=', 'pending_store')]).mapped('header_id')

        if operator != '=':  # that means it is '!='
            val = not val
        return [('id', 'in' if val else 'not in', ids)]
