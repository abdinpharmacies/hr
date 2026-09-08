"""Callcenter adapters for the versioned ab_branch_api provider."""
import math
from uuid import uuid4
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError


class BranchClient(models.AbstractModel):
    _name = 'ab_sales_branch_client'
    _description = 'Sales Branch API Client'

    @api.model
    def _is_callcenter(self):
        return self.env.user.has_group('ab_sales.group_call_center')

    @api.model
    def _config(self, store):
        store = store.exists()
        if not store or not store.eplus_serial:
            raise UserError(_('A store with an E-Plus serial is required.'))
        allowed = self.env['ab_sales_header']._get_allowed_store_ids()
        if allowed and store.id not in allowed:
            raise AccessError(_('This store is not allowed.'))
        config = self.env['ab_sales_branch_rpc_config'].sudo().search(
            fields.Domain('store_id', '=', store.id) & fields.Domain('active', '=', True), limit=1)
        if not config:
            raise UserError(_('No active branch RPC configuration was found for the selected store.'))
        return config

    @api.model
    def _call(self, store, method, *args):
        return self._config(store)._execute_kw('ab_branch_api', method, [int(store.eplus_serial), *args])

    @api.model
    def _stock(self, store, serials):
        serials = sorted(set(serials))
        rows = []
        for offset in range(0, len(serials), 200):
            batch = serials[offset:offset + 200]
            response = self._call(store, 'get_stock_lines', batch)
            for row in response['data']:
                if (int(row['store_eplus_serial']) != int(store.eplus_serial)
                        or int(row['product_eplus_serial']) not in batch
                        or any(not math.isfinite(float(row[key])) for key in ('qty', 'qty_in_small_unit', 'price', 'cost'))):
                    raise UserError(_('The branch returned invalid stock data.'))
                rows.append(row)
        return rows

    @api.model
    def _reference(self, record):
        record = record.exists()
        if len(record) != 1:
            raise UserError(_('A valid record is required for branch submission.'))
        if record._name == 'ab_hr_employee' and record.costcenter_id.code:
            return {'costcenter_code': record.costcenter_id.code}
        for key in ('eplus_serial', 'code'):
            if key in record._fields and record[key]:
                return {key: record[key]}
        xmlid = record.get_external_id().get(record.id)
        if xmlid:
            return {'xmlid': xmlid}
        raise UserError(_('A stable branch reference is missing for %s.') % record.display_name)

    @api.model
    def _sale_payload(self, payload):
        ignored = {'store_id', 'pos_client_token', 'pos_hr_profile_id', 'pos_hr_role_id',
                   'pos_hr_shift_id', 'pos_hr_session_id', 'pos_hr_service_user_id',
                   # Contract POS display values; branch business logic computes totals.
                   'contract_name', 'company_pay', 'cust_pay'}
        def encode(model, values, omit):
            result = {}
            for key, value in values.items():
                if key in omit or key not in model._fields:
                    continue
                field = model._fields[key]
                if field.type == 'many2one':
                    if isinstance(value, (list, tuple)):
                        value = value[0] if value else False
                    result[key] = self._reference(self.env[field.comodel_name].browse(int(value))) if value else False
                elif field.type not in ('one2many', 'many2many'):
                    result[key] = value
            return result
        result = {'header': encode(self.env['ab_sales_header'], payload.get('header') or {}, ignored), 'lines': []}
        for source in payload.get('lines') or []:
            line = encode(self.env['ab_sales_line'], source, {'uom_id', 'header_id', 'inventory_json', 'balance', 'cost'})
            product = self.env['ab_product'].browse(int(source.get('product_id') or 0)).exists()
            uom = self.env['ab_product_uom'].browse(int(source.get('uom_id') or product.uom_id.id)).exists()
            if not product or not uom or uom.category_id != product.uom_category_id:
                raise UserError(_('Invalid product unit.'))
            line['uom_factor'] = float(uom.factor)
            result['lines'].append(line)
        promotion = payload.get('applied_program_id')
        if promotion:
            if isinstance(promotion, (list, tuple)):
                promotion = promotion[0]
            result['promotion'] = self._reference(self.env['ab_promo_program'].browse(int(promotion)))
        return result


class BranchStockLine(models.Model):
    _inherit = 'ab_sales_line'

    def _recompute_inventory_json(self, crx=None):
        client = self.env['ab_sales_branch_client']
        if not client._is_callcenter():
            return super()._recompute_inventory_json(crx=crx)
        for store in self.header_id.store_id:
            lines = self.filtered(lambda line: line.header_id.store_id == store)
            serials = list({int(p.eplus_serial) for p in lines.product_id if p.eplus_serial})
            rows = client._stock(store, serials)
            for line in lines:
                line.inventory_json = {'data': [dict(row, store_id=store.id, product_id=line.product_id.id)
                    for row in rows if row['product_eplus_serial'] == line.product_id.eplus_serial]}


class BranchPos(models.TransientModel):
    _inherit = 'ab_sales_pos_api'

    @api.model
    def pos_refresh_pos_balances(self, store_id=None, product_ids=None):
        client = self.env['ab_sales_branch_client']
        if not client._is_callcenter():
            return super().pos_refresh_pos_balances(store_id=store_id, product_ids=product_ids)
        store = self.env['ab_store'].browse(int(store_id or 0))
        products = self.env['ab_product'].browse([int(pid) for pid in product_ids or []]).exists()
        rows = client._stock(store, [int(p.eplus_serial) for p in products if p.eplus_serial])
        totals = {}
        for row in rows:
            serial = row['product_eplus_serial']
            totals[serial] = totals.get(serial, 0.0) + row['qty']
        return {p.id: totals.get(p.eplus_serial, 0.0) for p in products}

    @api.model
    def pos_product_details(self, store_id, product_id):
        response = super().pos_product_details(store_id, product_id)
        if self.env['ab_sales_branch_client']._is_callcenter():
            balances = self.pos_refresh_pos_balances(store_id=store_id, product_ids=[product_id])
            response['pos_balance'] = balances.get(int(product_id), 0.0)
            response['balance'] = response['pos_balance']
        return response


class BranchReturn(models.Model):
    _inherit = 'ab_sales_return_header'

    branch_request_token = fields.Char(string='Branch Request Token', default=lambda self: str(uuid4()),
                                       copy=False, readonly=True, index=True)
    branch_return_id = fields.Integer(string='Branch Return ID', readonly=True, copy=False)

    def _branch_snapshot(self, response):
        self.ensure_one()
        if any(int(row['sto_id']) != int(self.store_id.eplus_serial)
               or int(row['sth_id']) != int(self.origin_header_id) for row in response['lines']):
            raise UserError(_('The branch returned lines from another invoice or store.'))
        self.write({'branch_return_id': response['branch_return_id'], 'total_sales_net': response['total_sales_net'],
                    'sales_return_id': response['sales_return_id'], 'f_transaction_id': response['f_transaction_id']})
        existing = {int(line.std_id): line for line in self.line_ids}
        products = self.env['ab_product'].search(fields.Domain('eplus_serial', 'in',
            list({int(row['itm_eplus_id']) for row in response['lines']})))
        products_by_serial = {}
        for product in products:
            products_by_serial.setdefault(int(product.eplus_serial), self.env['ab_product'])
            products_by_serial[int(product.eplus_serial)] |= product
        for source in response['lines']:
            values = dict(source)
            factor = values.pop('uom_factor')
            selected_qty = values.pop('selected_qty_source', 0.0)
            product = products_by_serial.get(int(values['itm_eplus_id']), self.env['ab_product'])
            if len(product) != 1:
                raise UserError(_('Return product is missing or ambiguous in callcenter.'))
            current = existing.get(int(values['std_id']))
            uom = self._find_uom_by_factor(product, factor)
            if not uom or not math.isclose(float(uom.factor), factor, rel_tol=1e-6):
                raise UserError(_('Return product unit is missing in callcenter.'))
            if current and current.uom_id:
                source_factor = float(values['source_uom_factor'] or 1)
                target = float(current.uom_id.factor or 1)
                values['qty_sold'] = values['qty_sold_source'] * source_factor / target
                values['max_returnable_qty'] = values['max_returnable_source'] * source_factor / target
                values['sell_price'] *= target / factor
                values['cost'] *= target / factor
                uom = current.uom_id
            values.update({'product_id': product.id, 'uom_id': uom.id})
            if response['status'] == 'saved':
                values['qty_str'] = str(selected_qty * float(values['source_uom_factor'] or 1) / float(uom.factor))
            if current:
                current.write(values)
            else:
                self.env['ab_sales_return_line'].create(dict(values, header_id=self.id))
        self._compute_totals()
        self.status = response['status']
        self.total_return_value = response['total_return_value']

    def _branch_selections(self):
        self.ensure_one()
        return [{'std_id': int(line.std_id), 'product_serial': int(line.itm_eplus_id),
                 'qty_source': float(line._qty_to_source_unit())} for line in self.line_ids]

    def action_load_lines(self):
        client = self.env['ab_sales_branch_client']
        if not client._is_callcenter():
            return super().action_load_lines()
        self.ensure_one()
        self.check_access('write')
        if not self.origin_header_id:
            raise UserError(_('Please enter sth_id (Original Invoice) first.'))
        if self.line_ids and self.line_ids[0].sth_id != self.origin_header_id:
            raise UserError(_('Clear the return lines before changing the invoice.'))
        if not self.branch_request_token:
            self.branch_request_token = str(uuid4())
        response = client._call(self.store_id, 'get_return_invoice', int(self.origin_header_id),
                                self.branch_request_token, self._branch_selections() if self.line_ids else False)
        self._branch_snapshot(response)
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
                'view_mode': 'form', 'target': self.env.context.get('curr_target', 'current')}

    def action_push_to_eplus_return(self):
        client = self.env['ab_sales_branch_client']
        if not client._is_callcenter():
            return super().action_push_to_eplus_return()
        self.ensure_one()
        self.check_access('write')
        if not self.branch_request_token:
            self.branch_request_token = str(uuid4())
        employee_ref = False
        session_token = self.env.context.get('ab_return_session_token')
        if session_token and 'ab_employee_access_sales_pos_api' in self.env:
            session = self.env['ab_employee_access_sales_pos_api']._get_session(session_token, states=['active'])
            employee_ref = client._reference(session.employee_id)
        config = client._config(self.store_id)
        log = self.env['ab_sales_callcenter_rpc_log'].sudo().create({
            'name': _('Callcenter Return Submit'), 'rpc_config_id': config.id, 'store_id': self.store_id.id,
            'payload_token': self.branch_request_token, 'push_to_eplus_requested': True,
            'state': 'started', 'submitted_by_id': self.env.uid, 'submitted_at': fields.Datetime.now()})
        self.env.cr.commit()
        try:
            response = client._call(self.store_id, 'submit_return', int(self.origin_header_id), self.branch_request_token,
                                   self._branch_selections(), self.notes or '', employee_ref)
            log.write({'state': 'success', 'remote_header_id': response['branch_return_id'],
                       'remote_status': response['status'], 'remote_eplus_serial': response['sales_return_id']})
            self.env.cr.commit()
            self._branch_snapshot(response)
        except Exception as error:
            self.env.cr.rollback()
            log.write({'state': 'error', 'error_message': str(error)})
            self.env.cr.commit()
            raise
        return True

    def get_connection(self):
        if self.env['ab_sales_branch_client']._is_callcenter():
            raise AccessError(_('Callcenter returns must use the branch API.'))
        return super().get_connection()

    def _return_router_mode(self, source_header=False):
        if self.env['ab_sales_branch_client']._is_callcenter():
            return 'original', self.env['ab_sales_header']
        return super()._return_router_mode(source_header=source_header)


class BranchReturnPreview(models.TransientModel):
    _inherit = 'ab_sales_return_ui_api'

    @api.model
    def get_state(self, return_header_id, **kwargs):
        result = super().get_state(return_header_id, **kwargs)
        client = self.env['ab_sales_branch_client']
        if client._is_callcenter():
            header = self._get_return_header(return_header_id)
            if header.status != 'saved' and header.line_ids:
                response = client._call(header.store_id, 'get_return_invoice', int(header.origin_header_id),
                                        header.branch_request_token, header._branch_selections())
                header.total_return_value = response['total_return_value']
                result = super().get_state(return_header_id, **kwargs)
        return result


class BranchSaleHeader(models.Model):
    _inherit = 'ab_sales_header'

    def action_push_to_eplus(self):
        if self.env['ab_sales_branch_client']._is_callcenter():
            raise AccessError(_('Callcenter sales must be submitted through POS using the branch API.'))
        return super().action_push_to_eplus()
