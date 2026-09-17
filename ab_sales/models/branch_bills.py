"""Callcenter browsing uses durable local bills, independent of branch availability."""
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class LocalBills(models.TransientModel):
    _inherit = 'ab_sales_ui_api'

    @api.model
    def bill_wizard_search(self, query='', product_query='', product_ids=None, customer_query='',
                           date_start=False, date_end=False, eplus_serial='', page=1, per_page=20,
                           store_id=False, document_type='', status='', search_token=False,
                           refresh_status=False, **kwargs):
        if not self.env['ab_sales_branch_client']._is_callcenter():
            return super().bill_wizard_search(query=query, product_query=product_query, product_ids=product_ids,
                customer_query=customer_query, date_start=date_start, date_end=date_end,
                eplus_serial=eplus_serial, page=page, per_page=per_page, **kwargs)
        if document_type not in ('', 'sale', 'return') or status not in ('', 'prepending', 'pending', 'saved'):
            raise UserError(_('Invalid bill filter.'))
        if query and not any((product_query, product_ids, customer_query, eplus_serial)):
            if str(query).isdigit():
                eplus_serial = query
            else:
                product_query = query
        filters = dict(product_query=product_query, product_ids=product_ids, customer_query=customer_query,
                       date_start=date_start, date_end=date_end, eplus_serial=eplus_serial)
        sale_domain = fields.Domain(self._bill_wizard_domain(**filters)[0])
        return_domain = fields.Domain(self._bill_wizard_return_domain(**filters)[0])
        # The base helpers exclude drafts for branch installations only.
        sale_domain = sale_domain.map_conditions(lambda c: fields.Domain.TRUE if c.field_expr == 'status' else c)
        return_domain = return_domain.map_conditions(lambda c: fields.Domain.TRUE if c.field_expr == 'status' else c)
        if store_id:
            sale_domain &= fields.Domain('store_id', '=', int(store_id))
            return_domain &= fields.Domain('store_id', '=', int(store_id))
        Header, Return = self.env['ab_sales_header'], self.env['ab_sales_return_header']
        errors = []
        if refresh_status and document_type != 'return':
            errors = Header.refresh_bill_statuses(list(sale_domain))['unavailable_branches']
        if status:
            sale_domain &= fields.Domain('status', '=', status)
            return_domain &= fields.Domain('status', '=', status)
        if document_type == 'return':
            sale_domain &= fields.Domain.FALSE
        if document_type == 'sale':
            return_domain &= fields.Domain.FALSE
        count = Header.search_count(sale_domain) + Return.search_count(return_domain)
        per_page = 20
        pages = max(1, (count + per_page - 1) // per_page)
        page = min(max(1, int(page)), pages)
        offset = (page - 1) * per_page
        sales = Header.search(sale_domain, order='create_date desc, id desc', limit=offset + per_page)
        returns = Return.search(return_domain, order='create_date desc, id desc', limit=offset + per_page)
        rows = [('sale', r) for r in sales] + [('return', r) for r in returns]
        rows.sort(key=lambda pair: (pair[1].create_date, pair[1].id, pair[0]), reverse=True)
        domain = self.env.user._ab_sales_bill_domain()
        grouped = Header._read_group(domain, ['store_id']) + Return._read_group(domain, ['store_id'])
        store_ids = self.env['ab_store'].browse(sorted({row[0].id for row in grouped if row[0]}))
        return {'items': [self._bill_wizard_header_payload(r, record_type=kind)
                          for kind, r in rows[offset:offset + per_page]],
                'is_search': True, 'local_bills': True,
                'branches': [{'id': s.id, 'name': s.display_name} for s in store_ids.sorted('name')],
                'unavailable_branches': errors,
                'pagination': {'page': page, 'per_page': per_page, 'page_count': pages, 'total_count': count}}
