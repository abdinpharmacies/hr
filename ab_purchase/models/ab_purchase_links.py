from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PurchaseLinks(models.Model):
    _inherit = 'ab_purchase_header'

    notice_ids = fields.One2many('ab_purchase_notice_header', 'purchase_header_id', string='Returns')
    return_count = fields.Integer(compute='_compute_return_totals', string='Returns')
    returned_value = fields.Float(compute='_compute_return_totals', string='Returned Value', digits=(16, 3))
    retained_value = fields.Float(compute='_compute_return_totals', string='Retained Value', digits=(16, 3))

    @api.depends('total_cost', 'notice_ids.status', 'notice_ids.notice_type', 'notice_ids.total_cost')
    def _compute_return_totals(self):
        for invoice in self:
            returns = invoice.notice_ids.filtered(lambda notice: notice.notice_type == 'credit_notice')
            invoice.return_count = len(returns)
            invoice.returned_value = sum(returns.filtered(lambda notice: notice.status == 'saved').mapped('total_cost'))
            invoice.retained_value = invoice.total_cost - invoice.returned_value

    def action_create_return(self):
        self.ensure_one()
        self.check_access('read')
        if self.status != 'saved':
            raise ValidationError(_('Save the purchase receipt before creating a return.'))
        return {
            'type': 'ir.actions.act_window', 'name': _('Purchase Return'),
            'res_model': 'ab_purchase_notice_header', 'views': [(False, 'form')],
            'context': {'default_purchase_header_id': self.id, 'default_supplier_id': self.supplier_id.id},
        }

    def action_view_returns(self):
        self.ensure_one()
        self.check_access('read')
        return {
            'type': 'ir.actions.act_window', 'name': _('Returns'),
            'res_model': 'ab_purchase_notice_header', 'views': [(False, 'list'), (False, 'form')],
            'domain': list(fields.Domain('purchase_header_id', '=', self.id)),
        }

    def action_view_inventory(self):
        self.ensure_one()
        self.check_access('read')
        domain = (fields.Domain('model_ref', '=', 'ab_purchase_line')
                  & fields.Domain('res_id', 'in', self.line_ids.ids))
        return_lines = self.notice_ids.mapped('line_ids')
        domain |= (fields.Domain('model_ref', '=', 'ab_purchase_notice_line')
                   & fields.Domain('res_id', 'in', return_lines.ids))
        return {
            'type': 'ir.actions.act_window', 'name': _('Inventory Movements'),
            'res_model': 'ab_inventory', 'views': [(False, 'list'), (False, 'form')],
            'domain': list(domain & fields.Domain('store_id', '=', self.store_id.id)),
        }

    def write(self, vals):
        if {'store_id', 'supplier_id'}.intersection(vals) and any(invoice.status != 'prepending' for invoice in self):
            raise ValidationError(_('The purchase store and supplier cannot change after submission.'))
        if {'net_invoice', 'net_tax', 'total_extra_discount', 'eplus_total_disc_on_inv'}.intersection(vals) and any(
                invoice.status == 'saved' for invoice in self):
            raise ValidationError(_('Saved purchase invoice totals cannot be changed.'))
        return super().write(vals)


class PurchaseLineLinks(models.Model):
    _inherit = 'ab_purchase_line'

    notice_line_ids = fields.One2many('ab_purchase_notice_line', 'purchase_line_id')
    returned_qty = fields.Float(compute='_compute_return_quantities', string='Returned Quantity')
    returned_bonus = fields.Integer(compute='_compute_return_quantities', string='Returned Bonus')
    returnable_qty = fields.Float(compute='_compute_return_quantities', string='Returnable Quantity')
    returnable_bonus = fields.Integer(compute='_compute_return_quantities', string='Returnable Bonus')

    def _get_returned_quantities(self):
        lines = self.filtered(lambda line: isinstance(line.id, int))
        if not lines:
            return {}
        domain = (fields.Domain('purchase_line_id', 'in', lines.ids)
                  & fields.Domain('header_id.status', '=', 'saved')
                  & fields.Domain('header_id.notice_type', '=', 'credit_notice'))
        return {line.id: (qty, bonus) for line, qty, bonus in
                self.env['ab_purchase_notice_line']._read_group(
                    domain, ['purchase_line_id'], ['qty:sum', 'bonus:sum'])}

    @api.depends('qty', 'bonus', 'notice_line_ids.qty', 'notice_line_ids.bonus',
                 'notice_line_ids.header_id.status', 'notice_line_ids.header_id.notice_type')
    def _compute_return_quantities(self):
        quantities = self._get_returned_quantities()
        for line in self:
            line.returned_qty, line.returned_bonus = quantities.get(line.id, (0, 0))
            line.returnable_qty = max(0, line.qty - line.returned_qty)
            line.returnable_bonus = max(0, line.bonus - line.returned_bonus)

    @api.depends('qty', 'bonus', 'returned_qty', 'returned_bonus')
    def _compute_qty(self):
        for line in self:
            line.notice_qty = str(line.returned_qty + line.returned_bonus)
            line.net_qty = line.qty + line.bonus - line.returned_qty - line.returned_bonus


class ReturnLinks(models.Model):
    _inherit = 'ab_purchase_notice_header'

    purchase_header_id = fields.Many2one('ab_purchase_header', string='Invoice', required=True, ondelete='restrict')
    store_id = fields.Many2one(related='purchase_header_id.store_id', store=True, index=True, string='Store')
    lines_count = fields.Integer(compute='compute_totals', store=True)
    total_cost = fields.Float(compute='compute_totals', store=True, digits=(16, 3))
    total_taxes_value = fields.Float(compute='compute_totals', store=True, digits=(16, 3))

    @api.depends('line_ids.line_cost', 'line_ids.line_taxes_value')
    def compute_totals(self):
        for notice in self:
            notice.total_cost = sum(notice.line_ids.mapped('line_cost'))
            notice.total_taxes_value = sum(notice.line_ids.mapped('line_taxes_value'))
            notice.lines_count = len(notice.line_ids)

    @api.constrains('purchase_header_id', 'supplier_id', 'notice_type')
    def _check_purchase_link(self):
        for notice in self:
            if notice.purchase_header_id.status != 'saved':
                raise ValidationError(_('Save the purchase receipt before creating a return.'))
            if notice.supplier_id != notice.purchase_header_id.supplier_id:
                raise ValidationError(_('The return supplier must match the purchase invoice.'))
            if notice.notice_type != 'credit_notice':
                raise ValidationError(_('Only purchase returns are supported by this workflow.'))

    def btn_get_all_line_ids(self):
        self.ensure_one()
        self.check_access('write')
        if self.status == 'saved':
            raise ValidationError(_('Saved notice lines cannot be changed.'))
        entered = self.line_ids.mapped('purchase_line_id')
        available = self.purchase_header_id.line_ids - entered
        self.write({'line_ids': [fields.Command.create({'purchase_line_id': line.id}) for line in available
                                 if line.returnable_qty or line.returnable_bonus]})
        return True

    def btn_submit_inventory(self):
        self.ensure_one()
        self.check_access('write')
        if self.status == 'saved':
            return super().btn_submit_inventory()
        with self.env.cr.savepoint():
            # Use the same store lock as inventory posting, before checking return caps.
            self.env['ab_inventory_process']._check_store(self.store_id.id)
            self.env.cr.execute('SELECT id FROM ab_store WHERE id = %s FOR UPDATE', (self.store_id.id,))
            quantities = self.line_ids.mapped('purchase_line_id')._get_returned_quantities()
            for line in self.line_ids:
                paid, bonus = quantities.get(line.purchase_line_id.id, (0, 0))
                if (line.qty > line.purchase_line_id.qty - paid + 0.000001
                        or line.bonus > line.purchase_line_id.bonus - bonus):
                    raise ValidationError(_('Return quantities cannot exceed the unreturned purchase quantities.'))
            return super().btn_submit_inventory()

    def write(self, vals):
        protected = {'purchase_header_id', 'supplier_id', 'notice_type', 'doc_code', 'doc_date', 'line_ids'}
        if protected.intersection(vals) and any(notice.status == 'saved' for notice in self):
            raise ValidationError(_('Saved returns cannot be changed.'))
        if {'purchase_header_id', 'supplier_id', 'notice_type'}.intersection(vals) and any(self.mapped('line_ids')):
            raise ValidationError(_('Remove draft return lines before changing its purchase invoice or supplier.'))
        return super().write(vals)

    def action_view_inventory(self):
        self.ensure_one()
        self.check_access('read')
        return {
            'type': 'ir.actions.act_window', 'name': _('Inventory Movements'),
            'res_model': 'ab_inventory', 'views': [(False, 'list'), (False, 'form')],
            'domain': list(fields.Domain('model_ref', '=', 'ab_purchase_notice_line')
                           & fields.Domain('res_id', 'in', self.line_ids.ids)
                           & fields.Domain('store_id', '=', self.store_id.id)),
        }


class ReturnLineLinks(models.Model):
    _inherit = 'ab_purchase_notice_line'

    purchase_line_id = fields.Many2one('ab_purchase_line', required=True, ondelete='restrict',
                                       index=True, string='Purchase Line')
    source_id = fields.Many2one(related='purchase_line_id.source_id', store=True, readonly=True)
    line_cost = fields.Float(compute='_compute_line_calc', store=True, digits=(16, 3))
    line_price = fields.Float(compute='_compute_line_calc', store=True, digits=(16, 3))
    line_taxes_value = fields.Float(compute='_compute_line_taxes_value', store=True, digits=(16, 3))

    _unique_purchase_line = models.Constraint('UNIQUE(header_id, purchase_line_id)',
                                              'A purchase line can appear only once in a return.')

    def write(self, vals):
        if 'header_id' in vals and self.env['ab_purchase_notice_header'].browse(vals['header_id']).status == 'saved':
            raise ValidationError(_('Saved notice lines cannot be changed.'))
        return super().write(vals)

    @api.constrains('purchase_line_id', 'header_id', 'qty', 'bonus')
    def _check_return_line(self):
        for line in self:
            if line.purchase_line_id.header_id != line.header_id.purchase_header_id:
                raise ValidationError(_('The return line must belong to the selected purchase invoice.'))
            if line.qty < 0 or line.bonus < 0:
                raise ValidationError(_('Purchase quantities and bonuses cannot be negative.'))

    @api.depends('purchase_line_id', 'header_id.purchase_header_id')
    def _compute_purchase_header_id(self):
        for line in self:
            line.purchase_header_num = line.purchase_line_id.header_id.id or 0

    @api.depends('purchase_line_id.returnable_qty')
    def _compute_invoice_available_qty(self):
        for line in self:
            line.available_qty = line.purchase_line_id.returnable_qty

    @api.depends('purchase_line_id.returnable_bonus')
    def _compute_invoice_available_bonus(self):
        for line in self:
            line.available_bonus = line.purchase_line_id.returnable_bonus

    @api.depends('qty', 'bonus', 'unit_taxes_value')
    def _compute_line_taxes_value(self):
        for line in self:
            line.line_taxes_value = (line.qty + line.bonus) * line.unit_taxes_value

    @api.depends('qty', 'bonus', 'unit_taxes_value', 'price', 'purchase_line_id.purchase_price',
                 'purchase_line_id.extra_discount_percentage',
                 'purchase_line_id.header_id.total_extra_discount', 'purchase_line_id.header_id.line_ids.line_cost')
    def _compute_line_calc(self):
        for line in self:
            invoice = line.purchase_line_id.header_id
            gross = sum(invoice.line_ids.mapped('line_cost'))
            discount_factor = 1 - invoice.total_extra_discount / gross if gross else 1
            unit_purchase = line.purchase_line_id.purchase_price * (1 - line.purchase_line_id.extra_discount_percentage / 100)
            line.line_cost = (line.qty * unit_purchase + (line.qty + line.bonus) * line.unit_taxes_value) * discount_factor
            line.line_price = (line.qty + line.bonus) * line.price
