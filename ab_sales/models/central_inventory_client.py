"""Native branch references remain separate from legacy E-Plus identifiers."""
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class NativeBranchSale(models.Model):
    _inherit = 'ab_sales_header'

    @api.depends('store_id', 'eplus_serial', 'branch_native_invoice_id')
    def _compute_has_returns(self):
        native = self.filtered('branch_native_invoice_id')
        legacy = self - native
        if legacy:
            super(NativeBranchSale, legacy)._compute_has_returns()
        groups = self.env['ab_sales_return_header']._read_group(
            fields.Domain('status', '=', 'saved') & fields.Domain('store_id', 'in', native.store_id.ids)
            & fields.Domain('branch_native_origin_id', 'in', native.mapped('branch_native_invoice_id')),
            ['store_id', 'branch_native_origin_id'], ['__count']) if native else []
        returned = {(store.id, invoice) for store, invoice, count in groups}
        for sale in native:
            sale.has_returns = (sale.store_id.id, sale.branch_native_invoice_id) in returned

    def action_open_sales_return(self):
        self.ensure_one()
        if not self.branch_native_invoice_id:
            return super().action_open_sales_return()
        self.check_access('read')
        if self.status != 'saved':
            raise UserError(_('Settle the original invoice before returning it.'))
        headers = self.env['ab_sales_return_header']
        header = headers.search(fields.Domain('store_id', '=', self.store_id.id)
            & fields.Domain('branch_native_origin_id', '=', self.branch_native_invoice_id)
            & fields.Domain('status', '=', 'prepending'), limit=1)
        if not header:
            header = headers._create_callcenter_order({'store_id': self.store_id.id,
                'branch_native_origin_id': self.branch_native_invoice_id,
                'return_employee_id': self.pos_hr_employee_id.id if self.env.user.has_group('base.group_system') else False})
        return header.with_context(curr_target='new').action_load_lines()


class NativeBranchReturn(models.Model):
    _inherit = 'ab_sales_return_header'

    @api.model_create_multi
    def create(self, vals_list):
        # Native references must identify a readable local callcenter bill at this store.
        for vals in vals_list:
            native_id = vals.get('branch_native_origin_id')
            if native_id:
                sale = self.env['ab_sales_header'].search(fields.Domain('branch_native_invoice_id', '=', native_id)
                    & fields.Domain('store_id', '=', vals.get('store_id')) & fields.Domain('status', '=', 'saved'), limit=1)
                if not sale or vals.get('origin_header_id'):
                    raise AccessError(_('The native original invoice must belong to this store.'))
        return super().create(vals_list)

    def write(self, vals):
        if 'store_id' in vals and any(rec.branch_native_origin_id and rec.store_id.id != vals['store_id'] for rec in self):
            raise AccessError(_('The native original invoice must belong to this store.'))
        if 'branch_native_origin_id' in vals and any(rec.branch_native_origin_id != vals['branch_native_origin_id'] for rec in self):
            raise AccessError(_('The native original invoice cannot be changed.'))
        if 'origin_header_id' in vals and any(rec.branch_native_origin_id and bool(vals['origin_header_id']) for rec in self):
            raise AccessError(_('The native original invoice cannot be changed.'))
        return super().write(vals)


class NativeBranchReturnUI(models.TransientModel):
    _inherit = 'ab_sales_return_ui_api'

    @api.model
    def open_from_sale_header(self, sale_header_id, **kwargs):
        sale = self._get_sale_header(sale_header_id)
        if not sale.branch_native_invoice_id:
            return super().open_from_sale_header(sale_header_id, **kwargs)
        action = sale.with_context(ab_return_session_token=kwargs.get('session_token') or self.env.context.get('ab_return_session_token')).action_open_sales_return()
        return self._action_payload(action['res_id'])

    @api.model
    def _serialize_header(self, header):
        result = super()._serialize_header(header)
        if header.branch_native_origin_id:
            result.update(origin_header_id=header.branch_native_origin_id,
                          native_invoice_id=header.branch_native_origin_id, inventory_backend='central')
        return result


class NativeBranchBills(models.TransientModel):
    _inherit = 'ab_sales_ui_api'

    @api.model
    def _bill_wizard_header_payload(self, header, record_type='sale'):
        result = super()._bill_wizard_header_payload(header, record_type=record_type)
        if record_type == 'sale' and header.branch_native_invoice_id:
            result.update(can_return=header.status == 'saved', native_invoice_id=header.branch_native_invoice_id)
        return result

    @api.model
    def _bill_wizard_header_serial_text(self, header, record_type='sale'):
        if record_type == 'sale' and header.branch_native_invoice_id:
            return 'N-%s' % header.branch_native_invoice_id
        return super()._bill_wizard_header_serial_text(header, record_type=record_type)

    @api.model
    def _bill_wizard_return_source_header(self, return_header):
        if return_header.branch_native_origin_id:
            return self.env['ab_sales_header'].search(fields.Domain('store_id', '=', return_header.store_id.id)
                & fields.Domain('branch_native_invoice_id', '=', return_header.branch_native_origin_id), limit=1)
        return super()._bill_wizard_return_source_header(return_header)

    @api.model
    def _bill_wizard_sale_return_headers(self, header):
        if header.branch_native_invoice_id:
            return self.env['ab_sales_return_header'].search(fields.Domain('store_id', '=', header.store_id.id)
                & fields.Domain('branch_native_origin_id', '=', header.branch_native_invoice_id)
                & fields.Domain('status', '=', 'saved'))
        return super()._bill_wizard_sale_return_headers(header).filtered(lambda rec: not rec.branch_native_origin_id)
