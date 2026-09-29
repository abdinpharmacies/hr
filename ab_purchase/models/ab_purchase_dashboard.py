from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AbPurchaseDashboard(models.Model):
    _inherit = 'ab_purchase_header'

    @api.model
    def get_purchase_dashboard_payload(self, filters=None, tab='purchases', offset=0):
        self.check_access('read')
        filters = filters or {}
        user = self.env.user
        manager = user.has_group('base.group_system') or user.has_group('ab_purchase.group_ab_purchase_manager')
        stores = self.env['ab_store'].search(fields.Domain.TRUE if manager else
                                            fields.Domain('id', 'in', user.inventory_store_ids.ids))
        store_id = int(filters.get('store_id') or 0)
        scope = fields.Domain('store_id', 'in', [store_id] if store_id in stores.ids else stores.ids)
        if store_id and store_id not in stores.ids:
            raise ValidationError(_('The selected store is not available to you.'))
        documents = scope
        movements = scope & fields.Domain('model_ref', 'in', ['ab_purchase_line', 'ab_purchase_notice_line'])
        for key, operator in [('date_from', '>='), ('date_to', '<=')]:
            if filters.get(key):
                date = fields.Date.to_date(filters[key])
                documents &= fields.Domain('doc_date', operator, date)
                movements &= fields.Domain('saved_at', '>=' if key == 'date_from' else '<',
                                            date if key == 'date_from' else date + timedelta(days=1))
        if filters.get('date_from') and filters.get('date_to') and filters['date_from'] > filters['date_to']:
            raise ValidationError(_('The start date must not be after the end date.'))
        search = (filters.get('search') or '').strip()[:100]
        purchases = documents
        returns = documents & fields.Domain('notice_type', '=', 'credit_notice')
        if search:
            purchases &= (fields.Domain('doc_code', 'ilike', search)
                          | fields.Domain('supplier_id.name', 'ilike', search))
            returns &= (fields.Domain('doc_code', 'ilike', search)
                        | fields.Domain('purchase_header_id.doc_code', 'ilike', search)
                        | fields.Domain('supplier_id.name', 'ilike', search))
        notice_model = self.env['ab_purchase_notice_header']
        invoice_stats = {status: (count, amount) for status, count, amount in
                         self._read_group(purchases, ['status'], ['__count', 'net_invoice:sum'])}
        return_stats = {status: (count, amount) for status, count, amount in
                        notice_model._read_group(returns, ['status'], ['__count', 'total_cost:sum'])}
        received = invoice_stats.get('saved', (0, 0))[1]
        returned = return_stats.get('saved', (0, 0))[1]
        status = filters.get('status')
        if status:
            purchases &= fields.Domain('status', '=', status)
            returns &= fields.Domain('status', '=', status)
        offset = max(0, int(offset))
        if tab == 'returns':
            records = notice_model.search(returns, order='doc_date desc, id desc', offset=offset, limit=50)
            count = notice_model.search_count(returns)
            rows = [{'id': rec.id, 'code': rec.doc_code, 'date': str(rec.doc_date or ''),
                     'invoice_id': rec.purchase_header_id.id, 'invoice': rec.purchase_header_id.doc_code,
                     'store': rec.store_id.display_name, 'supplier': rec.supplier_id.display_name,
                     'status': rec.status, 'amount': rec.total_cost} for rec in records]
        else:
            records = self.search(purchases, order='doc_date desc, id desc', offset=offset, limit=50)
            count = self.search_count(purchases)
            rows = [{'id': rec.id, 'code': rec.doc_code, 'date': str(rec.doc_date or ''),
                     'store': rec.store_id.display_name, 'supplier': rec.supplier_id.display_name,
                     'status': rec.status, 'amount': rec.total_cost,
                     'returned': rec.returned_value, 'returns': rec.return_count} for rec in records]
        pending = self.search(purchases & fields.Domain('status', '=', 'pending'), limit=8)
        observed = self.env['ab_purchase_line'].search(fields.Domain('header_id', 'in', pending.ids), limit=12)
        recent_returns = notice_model.search(returns, order='id desc', limit=6)
        return {
            'store_ids': stores.ids,
            'recent': [{'id': rec.id, 'code': rec.doc_code, 'supplier': rec.supplier_id.display_name,
                        'store': rec.store_id.display_name, 'status': rec.status}
                       for rec in self.search(purchases, order='id desc', limit=6)],
            'stores': [{'id': store.id, 'name': store.display_name} for store in stores],
            'can_create_purchase': manager and self.has_access('create'),
            'can_create_return': manager and notice_model.has_access('create'),
            'pending_count': invoice_stats.get('pending', (0, 0))[0],
            'saved_count': invoice_stats.get('saved', (0, 0))[0],
            'return_count': return_stats.get('saved', (0, 0))[0],
            'pending_returns': return_stats.get('pending', (0, 0))[0],
            'received_value': received, 'returned_value': returned, 'retained_value': received - returned,
            'posted_receipts': self.env['ab_inventory'].search_count(
                movements & fields.Domain('status', '=', 'saved') & fields.Domain('model_ref', '=', 'ab_purchase_line')),
            'posted_returns': self.env['ab_inventory'].search_count(
                movements & fields.Domain('status', '=', 'saved') & fields.Domain('model_ref', '=', 'ab_purchase_notice_line')),
            'rows': rows, 'count': count, 'offset': offset,
            'observed': [{'id': line.id, 'invoice_id': line.header_id.id, 'invoice': line.header_id.doc_code,
                          'product': line.product_id.display_name, 'qty': line.qty, 'bonus': line.bonus,
                          'store': line.header_id.store_id.display_name, 'unit': line.uom_id.display_name}
                         for line in observed],
            'recent_returns': [{'id': rec.id, 'code': rec.doc_code, 'invoice': rec.purchase_header_id.doc_code,
                                'store': rec.store_id.display_name, 'status': rec.status, 'amount': rec.total_cost}
                               for rec in recent_returns],
            'notice': _('Pending purchase quantities are observed inbound only. Stock becomes on-hand after an inventory movement is saved.'),
        }
