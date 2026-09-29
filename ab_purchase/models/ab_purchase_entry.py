import math

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class PurchaseEntry(models.Model):
    _inherit = 'ab_purchase_header'

    def _entry_model(self, kind):
        if kind not in ('purchase', 'return'):
            raise ValidationError(_('Select a purchase or return.'))
        model = self.env['ab_purchase_header' if kind == 'purchase' else 'ab_purchase_notice_header']
        model.check_access('create')
        return model

    @api.model
    def entry_bootstrap(self):
        self._entry_model('purchase')
        user = self.env.user
        manager = user.has_group('base.group_system') or user.has_group('ab_purchase.group_ab_purchase_manager')
        stores = self.env['ab_store'].search(fields.Domain('allow_purchase', '=', True)
                 & (fields.Domain.TRUE if manager else fields.Domain('id', 'in', user.inventory_store_ids.ids)))
        drafts = []
        for kind, model_name, status in [('purchase', 'ab_purchase_header', 'prepending'),
                                         ('return', 'ab_purchase_notice_header', 'pending')]:
            records = self.env[model_name].search(fields.Domain('status', '=', status)
                       & fields.Domain('store_id', 'in', stores.ids), order='write_date desc', limit=20)
            drafts.extend({'id': rec.id, 'kind': kind, 'code': rec.doc_code,
                           'supplier': rec.supplier_id.display_name, 'store': rec.store_id.display_name} for rec in records)
        return {'stores': [{'id': rec.id, 'name': rec.display_name, 'code': rec.code or ''} for rec in stores],
                'expiry': str(self.env['ab_product_source'].default_get(['exp_date']).get('exp_date') or ''),
                'taxes': self.env['ab_taxes'].search_read([('status', 'in', ['purchase', 'all'])],
                    ['name', 'percentage', 'apply_on_total']), 'drafts': drafts, 'date': str(fields.Date.context_today(self))}

    @api.model
    def entry_lookup(self, kind, query='', store_id=False):
        self._entry_model('purchase')
        query = str(query or '')[:100]
        if kind == 'product':
            domain = fields.Domain('allow_purchase', '=', True)
            if query:
                domain &= fields.Domain('name', 'ilike', query) | fields.Domain('code', 'ilike', query)
            return [{'id': rec.id, 'name': rec.display_name, 'code': rec.code,
                     'price': rec.default_price, 'purchase_price': rec.default_cost,
                     'uom_id': rec.unit_l_id.id,
                     'units': [{'id': unit.id, 'name': unit.display_name} for unit in rec.uom_ids]}
                    for rec in self.env['ab_product'].search(domain, limit=15)]
        if kind == 'supplier':
            Supplier = self.env['ab_supplier']
            if query:
                records = Supplier.search(fields.Domain('code', '=ilike', query), limit=15)
                if records:
                    return [{'id': rec.id, 'name': rec.display_name, 'code': rec.code} for rec in records]
            domain = fields.Domain('name', 'ilike', query) | fields.Domain('code', 'ilike', query)
            return [{'id': rec.id, 'name': rec.display_name, 'code': rec.code} for rec in Supplier.search(domain, limit=15)]
        if kind == 'invoice':
            domain = fields.Domain('status', '=', 'saved') & fields.Domain('store_id', '=', int(store_id or 0))
            if query:
                domain &= fields.Domain('doc_code', 'ilike', query) | fields.Domain('supplier_id.name', 'ilike', query)
            return [{'id': rec.id, 'name': rec.doc_code, 'supplier': rec.supplier_id.display_name} for rec in self.search(domain, limit=15)]
        raise ValidationError(_('Invalid lookup.'))

    @api.model
    def entry_invoice(self, invoice_id):
        self._entry_model('return')
        invoice = self.browse(int(invoice_id)).exists()
        invoice.check_access('read')
        if not invoice or invoice.status != 'saved':
            raise ValidationError(_('Save the purchase receipt before creating a return.'))
        gross = sum(invoice.line_ids.mapped('line_cost'))
        factor = 1 - invoice.total_extra_discount / gross if gross else 1
        return {'id': invoice.id, 'code': invoice.doc_code, 'store_id': invoice.store_id.id,
                'supplier_id': invoice.supplier_id.id, 'supplier': invoice.supplier_id.display_name,
                'lines': [{'purchase_line_id': line.id, 'name': line.product_id.display_name,
                    'code': line.product_id.code, 'unit': line.uom_id.display_name,
                    'available_qty': line.returnable_qty, 'available_bonus': line.returnable_bonus,
                    'unit_purchase': line.purchase_price * (1 - line.extra_discount_percentage / 100),
                    'unit_tax': line.unit_taxes_value, 'factor': factor, 'qty': 0, 'bonus': 0}
                    for line in invoice.line_ids if line.returnable_qty or line.returnable_bonus]}

    @api.model
    def entry_load(self, kind, record_id):
        model = self._entry_model(kind)
        rec = model.browse(int(record_id)).exists()
        rec.check_access('read')
        if not rec or rec.status != ('prepending' if kind == 'purchase' else 'pending'):
            raise ValidationError(_('Only drafts can be opened in Data Entry.'))
        result = {'id': rec.id, 'version': str(rec.write_date), 'store_id': rec.store_id.id, 'supplier_id': rec.supplier_id.id,
                  'supplier': rec.supplier_id.display_name, 'doc_code': rec.doc_code,
                  'doc_date': str(rec.doc_date), 'description': rec.description or '', 'lines': []}
        if kind == 'purchase':
            result.update({'invoice_type': rec.invoice_type, 'net_invoice': rec.net_invoice,
                           'net_tax': rec.net_tax, 'total_extra_discount': rec.total_extra_discount})
            for line in rec.line_ids:
                result['lines'].append({'id': line.id, 'name': line.product_id.display_name,
                    'code': line.product_id.code, 'product_id': line.product_id.id, 'uom_id': line.uom_id.id,
                    'units': [{'id': unit.id, 'name': unit.display_name} for unit in line.product_id.uom_ids],
                    'qty': line.qty, 'bonus': line.bonus, 'price': line.price, 'purchase_price': line.purchase_price,
                    'extra_discount_percentage': line.extra_discount_percentage, 'taxes_ids': line.taxes_ids.ids,
                    'exp_date': str(line.exp_date or '')})
        else:
            original = self.entry_invoice(rec.purchase_header_id.id)
            result.update({'purchase_header_id': original['id'], 'invoice': original['code']})
            # Include exhausted lines already entered in a draft; posting rechecks availability.
            by_id = {line['purchase_line_id']: line for line in original['lines']}
            for line in rec.line_ids:
                values = by_id.get(line.purchase_line_id.id)
                if not values:
                    purchase = line.purchase_line_id
                    gross = sum(purchase.header_id.line_ids.mapped('line_cost'))
                    values = {'purchase_line_id': purchase.id, 'name': purchase.product_id.display_name,
                        'code': purchase.product_id.code, 'unit': purchase.uom_id.display_name,
                        'available_qty': purchase.returnable_qty, 'available_bonus': purchase.returnable_bonus,
                        'unit_purchase': purchase.purchase_price * (1 - purchase.extra_discount_percentage / 100),
                        'unit_tax': purchase.unit_taxes_value,
                        'factor': 1 - purchase.header_id.total_extra_discount / gross if gross else 1}
                result['lines'].append({**values, 'id': line.id, 'qty': line.qty, 'bonus': line.bonus})
        return result

    @api.model
    def entry_save(self, kind, payload):
        model = self._entry_model(kind)
        rec = model.browse(int(payload.get('id') or 0)).exists()
        if payload.get('id') and not rec:
            raise ValidationError(_('This draft no longer exists.'))
        if rec:
            rec.check_access('write')
            if rec.status != ('prepending' if kind == 'purchase' else 'pending'):
                raise ValidationError(_('Only drafts can be opened in Data Entry.'))
            if payload.get('version') != str(rec.write_date):
                raise ValidationError(_('This draft changed in another window. Reload it before saving.'))
        lines = payload.get('lines') or []
        if not lines or len(lines) > 500:
            raise ValidationError(_('Enter between 1 and 500 product lines.'))
        vals = {key: payload.get(key) for key in ('doc_code', 'doc_date', 'description')}
        if not vals['doc_code'] or not vals['doc_date']:
            raise ValidationError(_('Enter the document number and date.'))
        if kind == 'purchase':
            vals.update({key: payload.get(key) for key in ('store_id', 'supplier_id', 'invoice_type', 'net_invoice', 'net_tax', 'total_extra_discount')})
            for key in ('net_invoice', 'net_tax', 'total_extra_discount'):
                vals[key] = float(vals[key] or 0)
                if not math.isfinite(vals[key]) or vals[key] < 0:
                    raise ValidationError(_('Enter valid non-negative quantities and prices.'))
        else:
            invoice = self.browse(int(payload.get('purchase_header_id') or 0)).exists()
            invoice.check_access('read')
            if not invoice or invoice.status != 'saved':
                raise ValidationError(_('Save the purchase receipt before creating a return.'))
            if rec and rec.purchase_header_id != invoice:
                raise ValidationError(_('Start a new return to select another invoice.'))
            if not rec:
                vals.update({'purchase_header_id': invoice.id, 'supplier_id': invoice.supplier_id.id})
        commands, entered = [], set()
        for row in lines:
            keys = ('qty', 'bonus', 'product_id', 'uom_id', 'price', 'purchase_price', 'extra_discount_percentage', 'exp_date') if kind == 'purchase' else ('qty', 'bonus', 'purchase_line_id')
            values = {key: row.get(key) for key in keys}
            for key in ('qty', 'bonus', 'price', 'purchase_price', 'extra_discount_percentage'):
                if key in values:
                    number = float(values[key] or 0)
                    if not math.isfinite(number) or number < 0 or (key == 'bonus' and number != int(number)):
                        raise ValidationError(_('Enter valid non-negative quantities and prices.'))
                    values[key] = number
            if kind == 'purchase':
                product = self.env['ab_product'].browse(int(values['product_id'] or 0)).exists()
                product.check_access('read')
                if not product or not product.allow_purchase or int(values['uom_id'] or 0) not in product.uom_ids.ids:
                    raise ValidationError(_('Select a purchasable product and one of its units.'))
                if values['extra_discount_percentage'] > 100:
                    raise ValidationError(_('Line discount must be between 0 and 100 percent.'))
                taxes = self.env['ab_taxes'].browse(row.get('taxes_ids') or []).exists()
                taxes.check_access('read')
                if any(not tax.active or tax.status not in ('purchase', 'all') for tax in taxes):
                    raise ValidationError(_('Select valid purchase taxes.'))
                values['taxes_ids'] = [fields.Command.set(taxes.ids)]
                values['exp_date'] = values['exp_date'] or False
            else:
                purchase = invoice.line_ids.filtered(lambda line: line.id == int(values['purchase_line_id'] or 0))
                if not purchase or values['qty'] > purchase.returnable_qty or values['bonus'] > purchase.returnable_bonus:
                    raise ValidationError(_('Return quantities cannot exceed the unreturned purchase quantities.'))
            line_id = int(row.get('id') or 0)
            if line_id:
                if not rec or line_id not in rec.line_ids.ids or line_id in entered:
                    raise AccessError(_('The entry line does not belong to this draft.'))
                entered.add(line_id)
                commands.append(fields.Command.update(line_id, values))
            else:
                commands.append(fields.Command.create(values))
        if rec:
            commands.extend(fields.Command.delete(line.id) for line in rec.line_ids if line.id not in entered)
        vals['line_ids'] = commands
        with self.env.cr.savepoint():
            if rec:
                rec.write(vals)
            else:
                rec = model.create(vals)
            rec.flush_recordset()
            result = self.entry_load(kind, rec.id)
            result['version'] = str(rec.write_date)
            return result
