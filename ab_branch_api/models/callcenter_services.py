"""Authenticated services for clients which never connect to SQL Server."""
from datetime import datetime, time, timedelta
import math
from uuid import uuid4

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.addons.ab_sales.models.ab_sales_per_day import SALES_PER_DAY_SQL
from .routing import api_request, request_store, selected_server, STORE_UNSET


class BranchSnapshot(models.TransientModel):
    _name = 'ab_branch_api_snapshot'
    _description = 'Branch API Snapshot'
    _transient_max_hours = 2

    token = fields.Char(required=True, default=lambda self: str(uuid4()), index=True)
    owner_id = fields.Many2one('res.users', required=True)
    store_id = fields.Many2one('ab_store', required=True)
    kind = fields.Char(required=True)
    payload = fields.Json()


class BranchOperation(models.Model):
    _inherit = 'ab_branch_api_operation'
    kind = fields.Selection(selection_add=[('customer', 'Customer')], ondelete={'customer': 'cascade'})


class CallcenterServices(models.AbstractModel):
    _inherit = 'ab_branch_api'

    @api.model
    def get_capabilities(self, db_serial, *, store_eplus_serial=STORE_UNSET):
        result = super().get_capabilities(db_serial, store_eplus_serial=store_eplus_serial)
        result['bill_scope'] = 'callcenter_only'
        result['methods'] += ['get_product_balances', 'lookup_customer', 'create_customer',
            'get_inventory_snapshot', 'get_sales_day', 'get_invoice_statuses', 'get_sale_statuses',
            'search_bills', 'get_bill_details', 'update_bill_notes', 'render_bill_print']
        return result

    def _snapshot_page(self, store, db_serial, kind, token, offset, loader, size=200):
        if type(offset) is not int or offset < 0:
            raise UserError(_('Invalid page offset.'))
        Snapshot = self.env['ab_branch_api_snapshot'].sudo()
        if token:
            snapshot = Snapshot.search([('token', '=', token), ('owner_id', '=', self.env.uid),
                ('store_id', '=', store.id), ('kind', '=', kind),
                ('create_date', '>=', fields.Datetime.now() - timedelta(hours=1))], limit=1)
            if not snapshot:
                raise AccessError(_('The snapshot expired or belongs to another request.'))
        else:
            if offset:
                raise UserError(_('Start the snapshot at the first page.'))
            snapshot = Snapshot.create({'owner_id': self.env.uid, 'store_id': store.id,
                'kind': kind, 'payload': loader()})
        rows = snapshot.payload or []
        end = min(offset + size, len(rows))
        return {**self._identity(store, db_serial), 'token': snapshot.token, 'data': rows[offset:end],
                'next_offset': end if end < len(rows) else False, 'total_count': len(rows),
                'fetched_at': fields.Datetime.to_string(snapshot.create_date)}

    def _balance_rows(self, store, serials=None):
        self._business_permissions('sale')
        params = [int(store.eplus_serial)]
        restriction = ''
        if serials is not None:
            serials = sorted({int(s) for s in serials if int(s) > 0})
            if len(serials) > 200:
                raise UserError(_('At most 200 products may be requested.'))
            if not serials:
                return []
            restriction = ' AND ic.itm_id IN (%s)' % ','.join('?' for s in serials)
            params.extend(serials)
        with self.connect_eplus(server=selected_server(self, store), param_str='?', autocommit=False) as conn:
            with conn.cursor() as cur:
                # One committed statement; inactive/missing items do not masquerade as zero stock.
                cur.execute('''SELECT ic.itm_id, ic.itm_def_sell_price,
                    COALESCE(SUM(CAST(ics.itm_qty AS decimal(28,8)) / NULLIF(ic.itm_unit1_unit3,0)),0),
                    ic.itm_unit1_unit3
                    FROM item_catalog ic
                    LEFT JOIN Item_Class_Store ics ON ics.itm_id=ic.itm_id AND ics.sto_id=?
                    WHERE ic.itm_active=1''' + restriction + '''
                    GROUP BY ic.itm_id,ic.itm_def_sell_price,ic.itm_unit1_unit3 ORDER BY ic.itm_id''', tuple(params))
                rows = cur.fetchall()
        result = []
        for serial, price, qty, factor in rows:
            if not factor or float(factor) <= 0 or not all(math.isfinite(float(v or 0)) for v in (price, qty, factor)):
                raise UserError(_('Invalid product unit conversion in E-Plus.'))
            result.append({'product_eplus_serial': int(serial), 'store_eplus_serial': int(store.eplus_serial),
                           'balance': max(0.0, float(qty)), 'default_price': float(price or 0)})
        return result

    @api.model
    @api_request
    def get_product_balances(self, db_serial, product_serials, *, store_eplus_serial=STORE_UNSET):
        store = request_store(self)
        products = self.env['ab_product'].search(fields.Domain('eplus_serial', 'in', product_serials))
        if set(products.mapped('eplus_serial')) != set(product_serials):
            raise AccessError(_('Requested products are not accessible.'))
        return {**self._identity(store, db_serial), 'data': self._balance_rows(store, product_serials),
                'fetched_at': fields.Datetime.to_string(fields.Datetime.now())}

    @api.model
    @api_request
    def get_inventory_snapshot(self, db_serial, token=False, offset=0, *, store_eplus_serial=STORE_UNSET):
        store = request_store(self)
        self._business_permissions('sale')
        self.env['ab_sales_inventory'].check_access('read')
        return self._snapshot_page(store, db_serial, 'inventory', token, offset, lambda: self._balance_rows(store))

    @api.model
    @api_request
    def get_sales_day(self, db_serial, sale_date, token=False, offset=0, *, store_eplus_serial=STORE_UNSET):
        store = request_store(self)
        self._business_permissions('sale')
        self.env['ab_sales_per_day'].check_access('read')
        day = fields.Date.to_date(sale_date)
        if not day or day >= fields.Date.today():
            raise UserError(_('Only completed sales days can be requested.'))
        def load():
            start = datetime.combine(day, time.min)
            with self.connect_eplus(server=selected_server(self, store), param_str='?', autocommit=False) as conn:
                with conn.cursor() as cur:
                    sql = SALES_PER_DAY_SQL.format(store_placeholders='?').replace(' WITH (NOLOCK)', '')
                    cur.execute(sql, (start, start + timedelta(days=1), int(store.eplus_serial)))
                    rows = cur.fetchall()
            result = []
            for branch, product, qty in rows:
                if int(branch) != store.eplus_serial or qty is None or not math.isfinite(float(qty)):
                    raise UserError(_('The branch returned invalid sales data.'))
                result.append({'store_eplus_serial': int(branch), 'product_eplus_serial': int(product),
                               'sales_qty': float(qty), 'sale_date': str(day)})
            return result
        return self._snapshot_page(store, db_serial, 'sales:' + str(day), token, offset, load)

    @api.model
    @api_request
    def get_invoice_statuses(self, db_serial, invoices, *, store_eplus_serial=STORE_UNSET):
        store = request_store(self)
        self._business_permissions('sale')
        serials = sorted({int(s) for s in invoices if int(s) > 0})
        if len(serials) > 200:
            raise UserError(_('At most 200 invoices may be requested.'))
        data = []
        if serials:
            with self.connect_eplus(server=selected_server(self, store), param_str='?', autocommit=False) as conn:
                with conn.cursor() as cur:
                    cur.execute('SELECT sth_id,sth_flag FROM sales_trans_h WHERE sto_id=? AND sth_id IN ('
                                + ','.join('?' for s in serials) + ')', (store.eplus_serial, *serials))
                    data = [{'invoice': int(s), 'status': 'saved' if flag == 'C' else 'pending'} for s, flag in cur.fetchall()]
        return {**self._identity(store, db_serial), 'data': data}

    @api.model
    @api_request
    def get_sale_statuses(self, db_serial, tokens, *, store_eplus_serial=STORE_UNSET):
        """Refresh only sales submitted by this integration user, never all bills."""
        store = request_store(self)
        self._business_permissions('sale')
        if (not isinstance(tokens, list) or len(tokens) > 200
                or any(not isinstance(token, str) or not 16 <= len(token) <= 128 for token in tokens)):
            raise UserError(_('Provide at most 200 valid sale request tokens.'))
        operations = self.env['ab_branch_api_operation'].sudo().search(
            fields.Domain('token', 'in', tokens) & fields.Domain('user_id', '=', self.env.uid)
            & fields.Domain('store_id', '=', store.id) & fields.Domain('kind', '=', 'sale')
            & fields.Domain('state', '=', 'done'))
        # Normal business record rules still apply after the scoped operation lookup.
        headers = self.env['ab_sales_header'].search(
            fields.Domain('id', 'in', operations.mapped('record_id')) & fields.Domain('store_id', '=', store.id))
        by_id = {header.id: header for header in headers}
        owned = [(op.token, by_id[op.record_id]) for op in operations
                 if op.record_id in by_id and by_id[op.record_id].pos_client_token == op.token]
        invoices = sorted({int(header.eplus_serial) for _token, header in owned
                           if header.status == 'pending' and header.eplus_serial > 0})
        statuses = {}
        if invoices:
            response = self.get_invoice_statuses(db_serial, invoices, store_eplus_serial=store.eplus_serial)
            statuses = {row['invoice']: row['status'] for row in response['data']}
        rows = []
        for token, header in owned:
            status = header.status
            if status == 'pending':
                # An absent E-Plus row is not a cancellation or a completed sale.
                status = statuses.get(int(header.eplus_serial or 0))
            if status not in ('prepending', 'pending', 'saved'):
                continue
            rows.append({'token': token, 'branch_header_id': header.id,
                         'eplus_serial': int(header.eplus_serial or 0), 'status': status})
        return {**self._identity(store, db_serial), 'data': rows}

    def _customer_result(self, result, store, db_serial):
        result = dict(result)
        if result.get('customer'):
            result['customer'] = dict(result['customer'])
            result['customer'].pop('id', None)
        return {**result, **self._identity(store, db_serial)}

    @api.model
    @api_request
    def lookup_customer(self, db_serial, phone, *, store_eplus_serial=STORE_UNSET):
        store = request_store(self)
        self._business_permissions('sale')
        self.env['ab_customer'].check_access('read')
        result = self.env['ab_sales_pos_api'].pos_customer_lookup(phone=phone, store_id=store.id)
        return self._customer_result(result, store, db_serial)

    @api.model
    @api_request
    def create_customer(self, db_serial, token, phone, name, address, *, store_eplus_serial=STORE_UNSET):
        store = request_store(self)
        self._business_permissions('sale', post=True)
        self.env['ab_customer'].check_access('create')
        operation = self._operation(store, token, 'customer')
        payload = {'phone': phone, 'name': name, 'address': address}
        return self._run_post(operation, payload, lambda: self._customer_result(
            self.env['ab_sales_pos_api'].pos_customer_create(store_id=store.id, **payload), store, db_serial))

    def _bill_record(self, reference, store, db_serial):
        if (not isinstance(reference, dict) or reference.get('db_serial') != db_serial
                or reference.get('store_eplus_serial') != store.eplus_serial
                or reference.get('record_type') not in ('sale', 'return')):
            raise AccessError(_('Invalid branch bill reference.'))
        kind = reference['record_type']
        self._business_permissions(kind)
        model = 'ab_sales_header' if kind == 'sale' else 'ab_sales_return_header'
        record = self.env[model].browse(int(reference.get('record_id') or 0)).exists()
        record.check_access('read')
        if not record or record.store_id != store or not record.is_callcenter_order:
            raise AccessError(_('The bill does not belong to the selected branch.'))
        return kind, record

    def _bill_payload(self, kind, record, store, db_serial, details=False):
        ui = self.env['ab_sales_ui_api']
        signed_id = record.id if kind == 'sale' else -record.id
        payload = (ui.bill_wizard_details(signed_id) if details else
                   ui._bill_wizard_header_payload(record, record_type=kind))
        ref = {**self._identity(store, db_serial), 'record_type': kind, 'record_id': record.id}
        payload.update({'reference': ref, 'id': '%s:%s:%s:%s' % (db_serial, store.eplus_serial, kind, record.id),
                        'can_edit_notes': record.has_access('write')})
        return payload

    @api.model
    @api_request
    def search_bills(self, db_serial, filters=None, token=False, offset=0, *, store_eplus_serial=STORE_UNSET):
        store = request_store(self)
        self._business_permissions('return')
        filters = filters or {}
        def load():
            ui = self.env['ab_sales_ui_api']
            args = {k: filters[k] for k in ('product_query', 'customer_query', 'date_start', 'date_end', 'eplus_serial') if k in filters}
            if filters.get('product_serials'):
                args['product_ids'] = self.env['ab_product'].search([
                    ('eplus_serial', 'in', filters['product_serials'])]).ids or [-1]
            entries = []
            for kind, model, builder in [('sale', 'ab_sales_header', ui._bill_wizard_domain),
                                         ('return', 'ab_sales_return_header', ui._bill_wizard_return_domain)]:
                if filters.get('document_type') and filters['document_type'] != kind:
                    continue
                kind_args = dict(args)
                if kind == 'return':
                    kind_args['customer_query'] = ''
                domain, _search = builder(**kind_args)
                if kind == 'return' and args.get('customer_query'):
                    source_domain, _ = ui._bill_wizard_domain(customer_query=args['customer_query'])
                    sources = self.env['ab_sales_header'].search(fields.Domain(source_domain)
                        & fields.Domain('store_id', '=', store.id))
                    domain = list(fields.Domain(domain) & fields.Domain('origin_header_id', 'in', sources.mapped('eplus_serial')))
                statuses = [filters['status']] if filters.get('status') in ('prepending', 'pending', 'saved') else ['prepending', 'pending', 'saved']
                domain = [('status', 'in', statuses) if isinstance(term, (tuple, list)) and term[0] == 'status' else term for term in domain]
                records = self.env[model].search(fields.Domain(domain) & fields.Domain('store_id', '=', store.id)
                                                & fields.Domain('is_callcenter_order', '=', True)
                                                & fields.Domain('status', 'in', statuses), order='create_date desc,id desc')
                entries.extend({'kind': kind, 'id': r.id, 'date': fields.Datetime.to_string(r.create_date)} for r in records)
            return sorted(entries, key=lambda x: (x['date'], x['kind'], x['id']), reverse=True)
        page = self._snapshot_page(store, db_serial, 'bills:callcenter_only:v1', token, offset, load, size=20)
        items = []
        for entry in page.pop('data'):
            ref = {**self._identity(store, db_serial), 'record_type': entry['kind'], 'record_id': entry['id']}
            kind, record = self._bill_record(ref, store, db_serial)
            items.append(self._bill_payload(kind, record, store, db_serial))
        return {**page, 'items': items}

    @api.model
    @api_request
    def get_bill_details(self, db_serial, reference, *, store_eplus_serial=STORE_UNSET):
        store = request_store(self)
        kind, record = self._bill_record(reference, store, db_serial)
        return {**self._identity(store, db_serial), 'bill': self._bill_payload(kind, record, store, db_serial, True)}

    @api.model
    @api_request
    def update_bill_notes(self, db_serial, reference, notes, *, store_eplus_serial=STORE_UNSET):
        store = request_store(self)
        kind, record = self._bill_record(reference, store, db_serial)
        record.check_access('write')
        record.write({'description' if kind == 'sale' else 'notes': str(notes or '').strip()})
        return {**self._identity(store, db_serial), 'bill': self._bill_payload(kind, record, store, db_serial)}

    @api.model
    @api_request
    def render_bill_print(self, db_serial, reference, print_format='a4', *, store_eplus_serial=STORE_UNSET):
        store = request_store(self)
        kind, record = self._bill_record(reference, store, db_serial)
        if print_format not in ('a4', 'pos_80mm'):
            raise UserError(_('Invalid print format.'))
        result = self.env['ab_sales_ui_api'].bill_wizard_render_print_html(
            record.id if kind == 'sale' else -record.id, print_format=print_format)
        return {**result, **self._identity(store, db_serial)}
