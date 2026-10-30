"""Callcenter adapters for the versioned ab_branch_api provider."""
import math
from datetime import timezone
from uuid import UUID, uuid4
from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.tools import config as odoo_config


FORCE_ID_SALE_MODELS = frozenset({
    'ab_product', 'ab_contract', 'ab_hr_employee', 'ab_doctor', 'ab_promo_program',
})


class BranchClient(models.AbstractModel):
    _name = 'ab_sales_branch_client'
    _description = 'Sales Branch API Client'


    @api.model
    def _config(self, store):
        store = store.exists()
        store.check_access('read')
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
        config = self._config(store)
        return config._execute_kw('ab_branch_api', method, [config.db_serial, *args])

    @api.model
    def _stock(self, store, serials):
        serials = sorted(set(serials))
        db_serial = self._config(store).db_serial
        rows = []
        for offset in range(0, len(serials), 200):
            batch = serials[offset:offset + 200]
            response = self._call(store, 'get_stock_lines', batch)
            for row in response['data']:
                if (type(row.get('db_serial')) is not int or row['db_serial'] != db_serial
                        or type(row.get('store_eplus_serial')) is not int
                        or row['store_eplus_serial'] != store.eplus_serial
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
        record.check_access('read')
        if 'active' in record._fields and not record.active:
            raise UserError(_('A valid record is required for branch submission.'))
        if record._name in FORCE_ID_SALE_MODELS:
            return {'id': record.id}
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
    def _sale_relation_ids(self, field, value, allow_inactive=False):
        """Normalize a new submission snapshot without executing ORM commands."""
        error = _('Invalid source relation for branch submission.')
        if field.type == 'many2one':
            if isinstance(value, (list, tuple)):
                value = value[0] if value else False
            ids = [value] if value else []
        elif not value:
            ids = []
        elif isinstance(value, (list, tuple)) and all(type(item) is int for item in value):
            ids = list(value)
        else:
            ids = []
            # Snapshot starts empty. Creation, updates and deletion are never allowed.
            for command in value if isinstance(value, (list, tuple)) else [None]:
                if not isinstance(command, (list, tuple)) or len(command) != 3:
                    raise UserError(error)
                op, record_id, data = command
                if type(op) is not int:
                    raise UserError(error)
                if op == 6 and record_id == 0 and isinstance(data, (list, tuple)):
                    ids = list(data)
                elif op == 5 and record_id == 0 and data == 0:
                    ids = []
                elif op in (3, 4) and type(record_id) is int and record_id > 0 and data == 0:
                    ids = [i for i in ids if i != record_id]
                    if op == 4:
                        ids.append(record_id)
                else:
                    raise UserError(error)
        if any(type(item) is not int or item <= 0 for item in ids):
            raise UserError(error)
        ids = list(dict.fromkeys(ids))
        records = self.env[field.comodel_name].browse(ids).exists()
        if len(records) != len(ids):
            raise UserError(error)
        records.check_access('read')
        if not allow_inactive and 'active' in records._fields and any(not record.active for record in records):
            raise UserError(error)
        return ids

    @api.model
    def _sale_customer_reference(self, customer):
        customer.check_access('read')
        if type(customer.eplus_serial) is not int or customer.eplus_serial <= 0:
            raise UserError(_('A valid customer E-Plus reference is required.'))
        return {'eplus_serial': customer.eplus_serial}

    @api.model
    def _sale_correction_payload(self, wire):
        """Extension point for a copied wire payload in a confirmed rejected revision."""
        return wire

    @api.model
    def _sale_source_identity(self, wire, capabilities):
        """Enrich only a new promotion attempt; never refresh a frozen origin."""
        if ('source_db_serial' in wire or not wire.get('promotion')
                or capabilities.get('submission_source_identity') != 1):
            return wire
        serial = odoo_config.get('db_serial')
        if isinstance(serial, str) and serial.strip().isascii() and serial.strip().isdigit():
            serial = int(serial.strip())
        if type(serial) is not int or serial <= 0:
            raise UserError(_('A positive callcenter DB serial is required to submit this promotion.'))
        return dict(wire, source_db_serial=serial)

    @api.model
    def _sale_payload(self, payload):
        pos_api = self.env['ab_sales_pos_api']
        values = pos_api._pos_submission_header_vals(payload)
        draft = self.env['ab_sales_header'].new(values)
        if values.get('contract_id') and hasattr(draft, '_ab_contract_validate_store_allowed'):
            draft._ab_contract_validate()
            draft._ab_contract_validate_store_allowed(check_status=False)
        ignored = {'branch_submission_payload', 'branch_submission_started', 'branch_request_revision',
                   'branch_header_id', 'push_state', 'push_message', 'eplus_serial', 'store_id', 'pos_client_token', 'status', 'pos_hr_profile_id', 'pos_hr_role_id',
                   'pos_hr_shift_id', 'pos_hr_session_id', 'pos_hr_service_user_id',
                   # Contract POS display values; branch business logic computes totals.
                   'contract_name', 'company_pay', 'cust_pay'}
        source_uuid = self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        try:
            UUID(source_uuid)
        except (ValueError, TypeError, AttributeError):
            raise UserError(_('A valid callcenter database UUID is required for branch submission.')) from None
        context = {'schema_version': 1, 'source': source_uuid, 'header': {}, 'lines': []}

        def encode(model, values, omit):
            result, descriptors = {}, {}
            for key, value in values.items():
                if key in omit or key not in model._fields:
                    continue
                field = model._fields[key]
                descriptor = {'type': field.type}
                if field.type in ('many2one', 'many2many'):
                    selected_customer = model._name == 'ab_sales_header' and key == 'customer_id'
                    ids = self._sale_relation_ids(field, value, allow_inactive=selected_customer)
                    descriptor.update(model=field.comodel_name, ids=ids)
                    reference = self._sale_customer_reference if selected_customer else self._reference
                    refs = [reference(self.env[field.comodel_name].browse(i)) for i in ids]
                    value = (refs[0] if refs else False) if field.type == 'many2one' else refs
                elif field.type in ('date', 'datetime'):
                    if not value:
                        value = None
                    elif field.type == 'date':
                        value = fields.Date.to_date(value).isoformat()
                    else:
                        stamp = fields.Datetime.to_datetime(value)
                        stamp = stamp.replace(tzinfo=timezone.utc) if stamp.tzinfo is None else stamp.astimezone(timezone.utc)
                        value = stamp.isoformat().replace('+00:00', 'Z')
                elif field.type in ('float', 'monetary', 'integer'):
                    if type(value) not in (int, float) or not math.isfinite(value):
                        raise UserError(_('Invalid scalar value for branch submission: %s') % key)
                    if field.type == 'integer' and type(value) is not int:
                        raise UserError(_('Invalid scalar value for branch submission: %s') % key)
                elif field.type == 'boolean':
                    if type(value) is not bool:
                        raise UserError(_('Invalid scalar value for branch submission: %s') % key)
                elif field.type in ('char', 'text', 'selection'):
                    if not (isinstance(value, str) or value is False or value is None):
                        raise UserError(_('Invalid scalar value for branch submission: %s') % key)
                else:
                    raise UserError(_('Unsupported source field type for branch submission: %s') % key)
                result[key] = value
                descriptors[key] = descriptor
            return result, descriptors
        header, context['header'] = encode(self.env['ab_sales_header'], values, ignored)
        result = {'header': header, 'lines': [], 'metadata_context': context}
        for source in payload.get('lines') or []:
            source = pos_api._pos_editable_line_vals(source)
            line, descriptors = encode(self.env['ab_sales_line'], source, {'uom_id', 'header_id', 'inventory_json', 'balance', 'cost'})
            context['lines'].append(descriptors)
            product = self.env['ab_product'].browse(int(source.get('product_id') or 0)).exists()
            uom = self.env['ab_product_uom'].browse(int(source.get('uom_id') or product.uom_id.id)).exists()
            if (not product or not uom or uom.category_id != product.uom_category_id
                    or not math.isfinite(uom.factor) or uom.factor <= 0
                    or (product.only_default_sales_uom and uom != product.uom_id)):
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
        balances = self.pos_refresh_pos_balances(store_id=store_id, product_ids=[product_id])
        response['pos_balance'] = balances.get(int(product_id), 0.0)
        response['balance'] = response['pos_balance']
        response.update(self.pos_cached_balance_totals([product_id], store_id, include_sync_metadata=True).get(int(product_id), {}))
        response['total_balance_unavailable'] = not response.get('total_refresh_success', False)
        product = self.env['ab_product'].browse(int(product_id))
        response['sell_price'] = self._store_default_price(int(store_id), product)
        response['default_price'] = response['sell_price']
        return response


class BranchReturn(models.Model):
    _inherit = 'ab_sales_return_header'

    branch_request_token = fields.Char(string='Branch Request Token', default=lambda self: str(uuid4()),
                                       copy=False, readonly=True, index=True)
    branch_return_id = fields.Integer(string='Branch Return ID', readonly=True, copy=False)
    return_employee_id = fields.Many2one(
        'ab_hr_employee', string='Return Employee', copy=False, ondelete='restrict',
        groups='base.group_system',
        domain="[('active', '=', True), ('costcenter_id.active', '=', True), ('costcenter_id.code', '!=', False)]",
        help='Employee responsible for a callcenter return submitted from the Administrator form. POS returns use the logged-in employee.',
    )

    def _branch_snapshot(self, response):
        self.ensure_one()
        config = self.env['ab_sales_branch_client']._config(self.store_id)
        config._validate_identity(response)
        db_serial = config.db_serial
        if (type(response.get('db_serial')) is not int or response['db_serial'] != db_serial
                or response.get('invoice') != int(self.origin_header_id)
                or any(int(row['sth_id']) != int(self.origin_header_id)
                       or int(row['sto_id']) != self.store_id.eplus_serial for row in response['lines'])):
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
            if current and current.itm_eplus_id != int(values['itm_eplus_id']):
                raise UserError(_('Return product does not match the original invoice line.'))
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

    def _branch_return_employee_reference(self):
        self.ensure_one()
        session_token = self.env.context.get('ab_return_session_token')
        if session_token:
            return_api = self.env['ab_sales_return_ui_api']
            if ('ab_employee_access_sales_pos_api' not in self.env
                    or not hasattr(return_api, '_validate_return_employee_session')):
                raise UserError(_('Employee POS sessions are not available. Contact support.'))
            session = self.env['ab_employee_access_sales_pos_api']._get_session(session_token, states=['active'])
            if session.service_user_id != self.env.user:
                raise AccessError(_('The employee POS session belongs to another user.'))
            session = return_api._validate_return_employee_session(self.id, session_token, states=['active'])
            employee = self.env['ab_hr_employee'].browse(session.employee_id.id)
        elif self.env.user.has_group('base.group_system'):
            employee = self.return_employee_id
            if not employee:
                raise UserError(_('Select a Return Employee before submitting this callcenter return.'))
        else:
            raise UserError(_('Log in to an active employee POS session before submitting this callcenter return.'))
        employee = employee.exists()
        employee.check_access('read')
        if not employee or not employee.active or not employee.costcenter_id.active:
            raise UserError(_('Select an active return employee with an active employee cost center.'))
        return self.env['ab_sales_branch_client']._reference(employee)

    def action_push_to_eplus_return(self):
        client = self.env['ab_sales_branch_client']
        self.ensure_one()
        self.check_access('write')
        employee_ref = self._branch_return_employee_reference()
        if not self.branch_request_token:
            self.branch_request_token = str(uuid4())
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
            self._branch_snapshot(response)
            self.env.cr.commit()
        except Exception as error:
            self.env.cr.rollback()
            log.write({'state': 'error', 'error_message': str(error)})
            self.env.cr.commit()
            raise
        if self.status == 'saved':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sales Return'),
                    'message': _('Return committed.'),
                    'type': 'success',
                    'sticky': False,
                    'next': {'type': 'ir.actions.client', 'tag': 'reload'},
                },
            }
        return True


    def _return_router_mode(self, source_header=False):
        return 'original', self.env['ab_sales_header']


class BranchReturnPreview(models.TransientModel):
    _inherit = 'ab_sales_return_ui_api'

    @api.model
    def get_state(self, return_header_id, **kwargs):
        result = super().get_state(return_header_id, **kwargs)
        client = self.env['ab_sales_branch_client']
        header = self._get_return_header(return_header_id)
        if header.status != 'saved' and header.line_ids:
            response = client._call(header.store_id, 'get_return_invoice', int(header.origin_header_id),
                                    header.branch_request_token, header._branch_selections())
            header._branch_snapshot(response)
            result = super().get_state(return_header_id, **kwargs)
        return result


class BranchStoreStatus(models.TransientModel):
    _inherit = 'ab_sales_ui_api'

    @api.model
    def pos_store_status(self, store_id=None):
        client = self.env['ab_sales_branch_client']
        if not store_id:
            return False
        store = self.env['ab_store'].browse(int(store_id)).exists()
        store.check_access('read')
        config = client._config(store)
        if config.enrollment_state != 'ready':
            raise UserError(_('Verify and activate the branch connection before using it.'))
        config._status()
        return True
