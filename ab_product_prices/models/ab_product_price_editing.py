import datetime
import json

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AbProductPriceEditing(models.Model):
    _name = 'ab_product_price_editing'
    _description = 'ab_product_price_editing'
    _order = 'id DESC'
    _inherit = 'abdin_et.extra_tools'

    store_id = fields.Many2one('ab_store', default=lambda self: self._get_default_store_id())
    product_id = fields.Many2one('ab_product')
    request_date = fields.Datetime(readonly=True)
    code = fields.Char(related='product_id.code')
    actual_price = fields.Float(related='product_id.default_price')

    no_of_items = fields.Integer(required=True)
    attachment = fields.Binary()
    notes = fields.Text(
        readonly=lambda self: not self.user.has_group('ab_product_prices.group_ab_product_price_editing_editor')
    )
    status = fields.Selection([('entry', 'Entry'),
                               ('submitted', 'Submitted'),
                               ('done', 'Done'),
                               ('rejected', 'Rejected'),
                               ],
                              default='entry',
                              readonly=True)
    product_source_id = fields.Many2one('ab_product_source',
                                        string="Available Price",
                                        domain="[('product_id', '=', product_id)]", required=True)
    product_source_id_domain = fields.Char(compute='_compute_product_source_id_domain')
    new_price = fields.Float(compute='_compute_new_price', string='New Price', store=True, readonly=False)

    def action_show_selected_codes(self):
        codes = [c for c in self.mapped("code") if c]
        joined = ", ".join(codes) if codes else "No codes found."
        return self.ab_msg(message=joined, title=_("Codes separated by comma"))

    def _get_default_store_id(self):
        user_id = self.env.user.id
        department = self.env['ab_hr_department'].search([('user_id', '=', user_id)], limit=1)
        return department.store_id.id

    def btn_change_status(self, status=None):
        new_status = status or self.env.context.get('new_status')
        old_status = self.status

        if old_status == 'entry' and new_status == 'submitted':
            self.request_date = datetime.datetime.utcnow()

        if new_status:
            self.status = new_status

    def action_change_status_all(self, status):
        for rec in self:
            rec.btn_change_status(status)

    @api.depends('product_source_id')
    def _compute_new_price(self):
        for rec in self:
            rec.new_price = rec.product_source_id.price

    @api.depends('product_id')
    def _compute_product_source_id_domain(self):
        for rec in self:
            domain = [('product_id', '=', rec.product_id.id)]
            if rec.product_id:
                # Search all sources for this product
                sources = self.env['ab_product_source'].search(domain)

                # Track unique prices
                unique = set()
                unique_ids = []

                for source in sources:
                    if source.price not in unique:
                        unique.add(source.price)
                        unique_ids.append(source.id)

                # Apply filtered domain by ID
                rec.product_source_id_domain = json.dumps([('id', 'in', unique_ids)])
            else:
                rec.product_source_id_domain = "[]"

    def write(self, vals):

        is_editor = self.env.user.has_group('ab_product_prices.group_ab_product_price_editing_editor')

        if 'notes' in vals and not is_editor:
            raise UserError(_("You are not allowed to edit notes."))
        if is_editor and set(vals) & {'store_id', 'product_id', 'request_date',
                                      'no_of_items', 'product_source_id', 'new_price'}:
            raise UserError(_("Editor can edit 'Notes' field only!"))
        for rec in self:
            if is_editor and rec.status == 'entry':
                raise UserError(_("Editor can not change status for entry records!"))

        return super().write(vals)

    def name_get(self):
        res = []
        for rec in self:
            res.append((rec.id, f"{rec.store_id.name}"))
        return res

    @api.depends('store_id')
    def _compute_display_name(self):
        """Keep the existing label format on the Odoo 19 display-name API."""
        names = dict(self.name_get())
        for record in self:
            record.display_name = names.get(record.id, False)
