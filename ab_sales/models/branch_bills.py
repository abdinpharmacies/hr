"""Browse branch-owned bills without local sale replicas or direct SQL."""
from datetime import timedelta
from uuid import uuid4
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class BranchBillSearch(models.TransientModel):
    _name = 'ab_sales_branch_bill_search'
    _description = 'Branch Bill Search'
    _transient_max_hours = 2

    token = fields.Char(default=lambda self: str(uuid4()), required=True, index=True)
    state = fields.Json(required=True)


class BranchBills(models.TransientModel):
    _inherit = 'ab_sales_ui_api'

    def _branch_bill_ref(self, reference):
        client = self.env['ab_sales_branch_client']
        if isinstance(reference, str):
            try:
                db, store, kind, record = reference.split(':')
                reference = {'db_serial': int(db), 'store_eplus_serial': int(store),
                             'record_type': kind, 'record_id': int(record)}
            except (ValueError, TypeError):
                raise AccessError(_('Invalid branch bill reference.')) from None
        if not isinstance(reference, dict) or reference.get('record_type') not in ('sale', 'return'):
            raise AccessError(_('Invalid branch bill reference.'))
        store = client._stores().filtered(lambda s: s.eplus_serial == reference.get('store_eplus_serial'))
        if len(store) != 1:
            raise AccessError(_('The bill does not belong to an authorized branch.'))
        config = client._config(store)
        config._validate_identity(reference)
        return client, store, reference

    def _branch_bill_page(self, client, store, branch, filters):
        response = client._call(store, 'search_bills', filters, branch['token'], branch['offset'])
        if branch['token'] and branch['token'] != response['token']:
            raise UserError(_('The branch returned an invalid snapshot.'))
        for bill in response['items']:
            client._config(store)._validate_identity(bill['reference'])
            if bill.get('id') != '%s:%s:%s:%s' % (bill['reference']['db_serial'], store.eplus_serial,
                                                  bill['reference']['record_type'], bill['reference']['record_id']):
                raise UserError(_('Invalid branch bill reference.'))
        branch.update(token=response['token'], offset=response['next_offset'], buffer=response['items'],
                      count=response['total_count'])

    @api.model
    def bill_wizard_search(self, query='', product_query='', product_ids=None, customer_query='',
                           date_start=False, date_end=False, eplus_serial='', page=1, per_page=20,
                           store_id=False, document_type='', status='', search_token=False, **kwargs):
        client = self.env['ab_sales_branch_client']
        if not client._is_callcenter():
            return super().bill_wizard_search(query=query, product_query=product_query, product_ids=product_ids,
                customer_query=customer_query, date_start=date_start, date_end=date_end,
                eplus_serial=eplus_serial, page=page, per_page=per_page, **kwargs)
        stores = client._stores()
        options = [{'id': s.id, 'name': s.display_name} for s in stores]
        if store_id:
            stores = stores.filtered(lambda s: s.id == int(store_id))
        if not stores:
            raise UserError(_('No authorized branches are configured.'))
        products = self.env['ab_product'].browse(product_ids or []).exists()
        products.check_access('read')
        filters = {'product_query': product_query, 'product_serials': products.mapped('eplus_serial') or ([-1] if product_ids else []),
                   'customer_query': customer_query, 'date_start': date_start, 'date_end': date_end,
                   'eplus_serial': eplus_serial or query, 'document_type': document_type, 'status': status}
        Session = self.env['ab_sales_branch_bill_search']
        page = max(1, int(page))
        if search_token and page != 1:
            session = Session.search([('token', '=', search_token), ('create_uid', '=', self.env.uid),
                ('create_date', '>=', fields.Datetime.now() - timedelta(hours=1))], limit=1)
            if not session or session.state['filters'] != filters or session.state['stores'] != stores.ids:
                raise UserError(_('The bill search expired. Refresh the results.'))
            state = dict(session.state)
            if page > len(state['pages']) + 1:
                raise UserError(_('Open the next page in order.'))
        else:
            state = {'filters': filters, 'stores': stores.ids, 'branches': {}, 'pages': [], 'errors': []}
            for store in stores:
                branch = {'token': False, 'offset': 0, 'buffer': [], 'count': 0}
                try:
                    self._branch_bill_page(client, store, branch, filters)
                except (UserError, AccessError):
                    state['errors'].append(store.display_name)
                    branch['offset'] = False
                state['branches'][str(store.id)] = branch
            session = Session.create({'state': state})
            page = 1
        if page > len(state['pages']):
            items = []
            while len(items) < 20:
                candidates = []
                for store in stores:
                    branch = state['branches'][str(store.id)]
                    if not branch['buffer'] and branch['offset'] is not False:
                        # Later failures must not skip unseen newer bills and reorder pagination.
                        self._branch_bill_page(client, store, branch, filters)
                    if branch['buffer']:
                        candidates.append((branch['buffer'][0], branch))
                if not candidates:
                    break
                bill, branch = max(candidates, key=lambda pair: (pair[0]['create_date'] or '', pair[0]['reference']['db_serial'],
                    pair[0]['reference']['store_eplus_serial'], pair[0]['reference']['record_type'], pair[0]['reference']['record_id']))
                items.append(bill)
                branch['buffer'].pop(0)
            state['pages'].append(items)
            session.state = state
        count = sum(b['count'] for b in state['branches'].values())
        return {'items': state['pages'][page-1], 'is_search': True, 'branches': options,
                'unavailable_branches': state['errors'], 'search_token': session.token, 'remote_bills': True,
                'pagination': {'page': page, 'per_page': 20, 'page_count': max(1, (count + 19)//20), 'total_count': count}}

    @api.model
    def bill_wizard_details(self, header_id):
        if not self.env['ab_sales_branch_client']._is_callcenter():
            return super().bill_wizard_details(header_id)
        client, store, ref = self._branch_bill_ref(header_id)
        return client._call(store, 'get_bill_details', ref)['bill']

    @api.model
    def bill_wizard_update_notes(self, header_id, notes=''):
        if not self.env['ab_sales_branch_client']._is_callcenter():
            return super().bill_wizard_update_notes(header_id, notes)
        client, store, ref = self._branch_bill_ref(header_id)
        return client._call(store, 'update_bill_notes', ref, notes)['bill']

    @api.model
    def bill_wizard_open_return_action(self, header_id):
        if not self.env['ab_sales_branch_client']._is_callcenter():
            return super().bill_wizard_open_return_action(header_id)
        client, store, ref = self._branch_bill_ref(header_id)
        bill = client._call(store, 'get_bill_details', ref)['bill']
        if ref['record_type'] != 'sale' or not bill.get('can_return'):
            raise UserError(_('Return action is available for submitted sales bills only.'))
        Header = self.env['ab_sales_return_header']
        header = Header.search([('store_id', '=', store.id), ('origin_header_id', '=', bill['eplus_serial']),
                               ('status', '=', 'prepending'), ('create_uid', '=', self.env.uid)], limit=1)
        if not header:
            header = Header.create({'store_id': store.id, 'origin_header_id': bill['eplus_serial']})
        header.action_load_lines()
        return self.env['ab_sales_return_ui_api']._action_payload(header.id)

    @api.model
    def bill_wizard_render_print_html(self, header_id, print_format='a4'):
        if not self.env['ab_sales_branch_client']._is_callcenter():
            return super().bill_wizard_render_print_html(header_id, print_format)
        client, store, ref = self._branch_bill_ref(header_id)
        return client._call(store, 'render_bill_print', ref, print_format)

    @api.model
    def bill_wizard_direct_print(self, header_id, print_format='a4', printer_name='', printer_id=0, selected_printer=None):
        if not self.env['ab_sales_branch_client']._is_callcenter():
            return super().bill_wizard_direct_print(header_id, print_format, printer_name, printer_id, selected_printer)
        printer = self._bill_wizard_resolve_selected_printer(printer_id=printer_id,
                        printer_name=printer_name, print_format=print_format)
        fmt = printer.paper_size if printer else print_format
        result = self.bill_wizard_render_print_html(header_id, fmt)
        if printer:
            printer.dispatch_print_html(result['content'], print_format=fmt)
        else:
            self._direct_print_html(result['content'], printer_name=printer_name, print_format=fmt)
        return {'ok': True, 'printer_id': printer.id if printer else 0,
                'printer_name': printer.build_display_label() if printer else printer_name, 'print_format': fmt}
