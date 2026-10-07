"""Durable callcenter bills and branch-isolated status refresh."""
from copy import deepcopy
from contextlib import contextmanager
import logging
from uuid import uuid4

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)
_CC_WORKFLOW = object()


class BillAccess(models.Model):
    _inherit = 'res.users'

    def _ab_sales_bill_domain(self, prefix=''):
        self.ensure_one()
        replica = self.env['ab_replica_db'].sudo().get_current_from_config()
        allowed = replica.allowed_sales_store_ids.ids if replica else []
        # Historical bills remain visible when a branch stops accepting new sales.
        domain = fields.Domain(prefix + 'store_id', 'in', allowed) if allowed else fields.Domain.TRUE
        if self.has_group('base.group_system') or self.has_group('ab_sales.group_ab_sales_manager'):
            return list(domain)
        departments = self.sudo().ab_department_ids
        stores = departments.store_id | self.sudo().ab_employee_ids.department_id.store_id
        if stores:
            domain &= fields.Domain(prefix + 'store_id', 'in', stores.ids)
        elif not self.has_group('ab_sales.group_call_center'):
            domain &= fields.Domain.FALSE
        return list(domain)


class LocalSales(models.Model):
    _inherit = 'ab_sales_header'

    status = fields.Selection(selection_add=[('unknown', 'Unknown'), ('rejected', 'Rejected')],
                              ondelete={'unknown': 'set default', 'rejected': 'set default'})
    branch_submission_payload = fields.Json(string='Branch Submission Payload', readonly=True, copy=False,
                                           groups='base.group_system')
    branch_header_id = fields.Integer(string='Branch Bill ID', readonly=True, copy=False)
    branch_request_revision = fields.Integer(string='Request Revision', default=1, readonly=True, copy=False)
    local_bill_storage = fields.Boolean(compute='_compute_local_bill_storage')
    branch_submission_started = fields.Boolean(string='Branch Submission Started', readonly=True, copy=False)

    def _compute_local_bill_storage(self):
        for record in self:
            record.local_bill_storage = True

    def _branch_records(self):
        return self.with_context(_ab_callcenter_workflow=_CC_WORKFLOW)

    def _branch_internal(self):
        return self.env.context.get('_ab_callcenter_workflow') is _CC_WORKFLOW

    def _write_branch_state(self, vals):
        return self._branch_records().write(vals)

    def _lock_branch_bill(self):
        if not self:
            return
        self.check_access('write')
        names = ['status', 'pos_client_token', 'store_id', 'branch_submission_started',
                 'branch_submission_payload', 'branch_request_revision', 'eplus_serial', 'branch_header_id']
        self.flush_recordset(names)
        try:
            with self.env.cr.savepoint():
                self.env.cr.execute('SELECT id FROM ab_sales_header WHERE id IN %s ORDER BY id FOR UPDATE NOWAIT',
                                    (tuple(sorted(self.ids)),))
        except Exception as error:
            raise UserError(_('This bill is being submitted. Retry shortly using the same bill.')) from error
        self.invalidate_recordset(names)

    @contextmanager
    def _branch_attempt(self):
        self.ensure_one()
        self.check_access('write')
        with self.env.registry.cursor() as lock_cr:
            lock_cr.execute('SELECT pg_try_advisory_lock(%s, %s)', (190810, self.id))
            if not lock_cr.fetchone()[0]:
                raise UserError(_('This bill is being submitted. Retry shortly using the same bill.'))
            try:
                self._lock_branch_bill()
                self.invalidate_recordset()
                self.line_ids.invalidate_recordset()
                yield
            finally:
                lock_cr.execute('SELECT pg_advisory_unlock(%s, %s)', (190810, self.id))

    @api.model_create_multi
    def create(self, vals_list):
        if not self._branch_internal():
            for vals in vals_list:
                if (vals.get('status', 'prepending') != 'prepending' or any(vals.get(name) for name in
                        ('eplus_serial', 'branch_header_id', 'branch_submission_started', 'branch_submission_payload'))
                        or vals.get('branch_request_revision', 1) != 1):
                    raise UserError(_('Callcenter bills must start in PrePending status.'))
        return super().create(vals_list)

    def write(self, vals):
        if not self._branch_internal():
            self._lock_branch_bill()
            protected = {'status', 'eplus_serial', 'branch_submission_payload', 'branch_submission_started',
                         'branch_header_id', 'branch_request_revision', 'push_state', 'push_message'}
            for record in self:
                if any(record[name] != value for name, value in vals.items() if name in protected):
                    raise AccessError(_('Branch submission metadata is read-only.'))
                if record.branch_submission_started:
                    for name in ('store_id', 'pos_client_token', 'active'):
                        if name in vals and vals[name] != (record[name].id if name == 'store_id' else record[name]):
                            raise UserError(_('The submitted bill identity cannot be changed.'))
                    if record.status != 'rejected' and any(record[name] != value for name, value in vals.items()):
                        raise UserError(_('This bill is locked until its branch submission is resolved. Use Retry.'))
        return super().write(vals)

    def copy(self, default=None):
        if any(self.mapped('pos_client_token')):
            raise UserError(_('The submitted bill identity cannot be changed.'))
        return super().copy(default=default)

    def unlink(self):
        raise UserError(_('Archive callcenter bills instead of deleting them.'))

    def _branch_result(self):
        self.ensure_one()
        accepted = self.status in ('pending', 'saved')
        return {'submission_guard_version': 1, 'callcenter_submission': True,
                # The existing employee-access wrapper logs success for this flag.
                # Unresolved outcomes use the guard contract and the RPC error log.
                'remote_callcenter': accepted, 'local_header_id': self.id,
                'branch_header_id': self.branch_header_id, 'remote_header_id': self.branch_header_id,
                'token': self.pos_client_token, 'request_revision': self.branch_request_revision,
                'status': self.status, 'eplus_serial': self.eplus_serial,
                'message': self.push_message or '', 'can_edit': self.status in ('prepending', 'rejected'),
                'can_retry': self.status in ('unknown', 'rejected'), 'duplicate_token': False}

    def _apply_branch_response(self, response, config):
        self.ensure_one()
        config._validate_identity(response)
        if (response.get('submission_guard_version') != 1 or response.get('token') != self.pos_client_token
                or type(response.get('request_revision')) is not int
                or response['request_revision'] != self.branch_request_revision
                or response.get('status') not in ('unknown', 'rejected', 'pending', 'saved')
                or type(response.get('branch_header_id')) is not int or response['branch_header_id'] < 0
                or type(response.get('eplus_serial')) is not int or response['eplus_serial'] < 0):
            raise UserError(_('The branch returned invalid invoice status.'))
        status, remote_id, serial = response['status'], response['branch_header_id'], response['eplus_serial']
        if ((status in ('pending', 'saved') and (remote_id <= 0 or serial <= 0))
                or (status in ('unknown', 'rejected') and serial != 0)
                or (self.branch_header_id and remote_id != self.branch_header_id)
                or (self.eplus_serial and serial != self.eplus_serial)
                or (self.status in ('pending', 'saved') and status in ('unknown', 'rejected'))
                or (self.status == 'saved' and status != 'saved')):
            raise UserError(_('The branch returned invalid invoice status.'))
        self.sudo()._write_branch_state({'branch_header_id': remote_id, 'eplus_serial': serial,
            'status': status, 'push_state': 'success' if status in ('pending', 'saved') else 'error',
            'push_message': str(response.get('message') or '')})

    def action_submit(self):
        return self.action_retry_branch_submission()

    def action_retry_branch_submission(self):
        self.ensure_one()
        self.check_access('write')
        if not self.sudo().branch_submission_payload:
            raise UserError(_('This bill has no stored branch submission request.'))
        payload = self.env['ab_sales_pos_api']._branch_current_payload(self) if self.status == 'rejected' else self.sudo().branch_submission_payload
        self.env['ab_sales_pos_api']._pos_submit_to_branch_rpc(dict(payload, submission_guard_version=1))
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    @api.model
    def refresh_bill_statuses(self, domain=None):
        domain = fields.Domain(domain or []).optimize(self).map_conditions(
            lambda c: fields.Domain.TRUE if c.field_expr == 'status' else c)
        records = self.search(domain & fields.Domain('status', 'in', ('prepending', 'unknown', 'rejected', 'pending'))
                              & fields.Domain('branch_submission_started', '=', True))
        return {'unavailable_branches': records._refresh_local_bill_statuses()}

    def _refresh_local_bill_statuses(self):
        self.check_access('read')
        errors = []
        client = self.env['ab_sales_branch_client']
        for store in self.store_id:
            bills = self.filtered(lambda h: h.store_id == store and h.branch_submission_started
                                  and h.status in ('prepending', 'unknown', 'rejected', 'pending'))
            if not bills:
                continue
            try:
                with self.env.cr.savepoint():
                    config = client._config(store)
                    for bill in bills.sudo():
                        target = {'_branch_db_serial': config.db_serial, '_branch_rpc_url': config.rpc_url,
                                  '_branch_rpc_db': config.rpc_db, '_branch_store_serial': int(config.store_id.eplus_serial)}
                        if any((bill.branch_submission_payload or {}).get(name) != value for name, value in target.items()):
                            raise UserError(_('The branch database changed. Reconcile the original request before retrying.'))
                    by_token = {bill.pos_client_token: bill for bill in bills}
                    tokens = sorted(by_token)
                    for offset in range(0, len(tokens), 200):
                        batch = tokens[offset:offset + 200]
                        response = client._call(store, 'get_sale_statuses', batch)
                        config._validate_identity(response)
                        if not isinstance(response.get('data'), list):
                            raise UserError(_('The branch returned invalid invoice status.'))
                        seen = set()
                        for row in response['data']:
                            if not isinstance(row, dict) or row.get('token') not in batch or row['token'] in seen:
                                raise UserError(_('The branch returned invalid invoice status.'))
                            seen.add(row['token'])
                            if row.get('state') == 'not_found':
                                continue
                            bill = by_token[row['token']]
                            bill.sudo()._lock_branch_bill()
                            if row.get('request_revision') != bill.branch_request_revision:
                                continue  # Older observations cannot unlock a corrected attempt.
                            bill._apply_branch_response(dict(row, db_serial=response['db_serial'],
                                store_eplus_serial=response['store_eplus_serial']), config)
            except Exception:
                _logger.warning('Bill status refresh failed for store %s; local bills retained.', store.id)
                errors.append(_('%s: status refresh unavailable; showing local bills.') % store.display_name)
        return errors

    def _compute_store_server_online(self):
        for record in self:
            record.store_server_online = False


class LocalSaleLines(models.Model):
    _inherit = 'ab_sales_line'

    @api.depends('product_id', 'product_id.default_price')
    def _compute_sell_price(self):
        editable = self.filtered(lambda line: not line.header_id.branch_submission_started or line.header_id.status == 'rejected')
        return super(LocalSaleLines, editable)._compute_sell_price()

    @api.constrains('sell_price', 'product_id', 'inventory_json', 'uom_id')
    def _check_sell_price_in_available_prices(self):
        # Frozen prices were validated at creation; catalog changes cannot reprice history.
        editable = self.filtered(lambda line: not line.header_id.branch_submission_started or line.header_id.status == 'rejected')
        return super(LocalSaleLines, editable)._check_sell_price_in_available_prices()

    def _branch_records(self):
        return self.with_context(_ab_callcenter_workflow=_CC_WORKFLOW)

    def _check_branch_lines(self, targets):
        if self.env.context.get('_ab_callcenter_workflow') is _CC_WORKFLOW:
            return
        targets._lock_branch_bill()
        if any(h.branch_submission_started and h.status != 'rejected' for h in targets):
            raise UserError(_('This bill is locked until its branch submission is resolved. Use Retry.'))
        if targets:
            # A parent version detects line edits committed after an attempt's
            # repeatable-read snapshot, before the durable Unknown commit.
            targets._write_branch_state({'write_date': fields.Datetime.now()})

    def write(self, vals):
        self._check_branch_lines(self.header_id | self.env['ab_sales_header'].browse(vals.get('header_id') or []))
        if 'header_id' in vals and any(h.branch_submission_started for h in self.header_id):
            raise UserError(_('The submitted bill identity cannot be changed.'))
        return super().write(vals)

    def unlink(self):
        self._check_branch_lines(self.header_id)
        return super().unlink()

    @api.model_create_multi
    def create(self, vals_list):
        headers = self.env['ab_sales_header'].browse([v['header_id'] for v in vals_list if v.get('header_id')])
        self._check_branch_lines(headers)
        return super().create(vals_list)


class LocalSubmission(models.TransientModel):
    _inherit = 'ab_sales_pos_api'

    def _branch_current_payload(self, header):
        payload = deepcopy(header.sudo().branch_submission_payload or {})
        values = payload.setdefault('header', {})
        for name in list(values):
            if name in header._fields and header._fields[name].type not in ('one2many', 'many2many'):
                field = header._fields[name]
                values[name] = header[name].id if field.type == 'many2one' else header[name]
        values.update(store_id=header.store_id.id, pos_client_token=header.pos_client_token)
        if 'applied_program_ids' in header._fields:
            payload['applied_program_id'] = header.applied_program_ids[:1].id or False
        payload['lines'] = [{name: line[name].id if line._fields[name].type == 'many2one' else line[name]
                            for name in ('product_id', 'uom_id', 'qty_str', 'sell_price', 'target_sell_price',
                                         'unavailable_reason', 'unavailable_reason_other')}
                           for line in header.line_ids]
        return {key: value for key, value in payload.items() if not key.startswith('_branch_')}

    def _replace_branch_bill(self, header, payload):
        values = self._filter_vals('ab_sales_header', payload.get('header') or {})
        for name in ('status', 'eplus_serial', 'pos_client_token', 'store_id', 'branch_submission_payload',
                     'branch_submission_started', 'branch_request_revision', 'branch_header_id', 'push_state', 'push_message'):
            values.pop(name, None)
        header._branch_records().write(values)
        header.line_ids._branch_records().unlink()
        if 'applied_program_ids' in header._fields:
            header._branch_records().write({'applied_program_ids': [fields.Command.clear()]})
        line_values = []
        for source in payload.get('lines') or []:
            vals = self._filter_vals('ab_sales_line', source)
            product = self.env['ab_product'].browse(int(vals.get('product_id') or 0)).exists()
            vals.update(header_id=header.id, uom_id=self._pos_line_uom_id(product, vals.get('uom_id')),
                        qty_str=vals.get('qty_str') or '1')
            line_values.append(vals)
        self.env['ab_sales_line'].with_context(_ab_callcenter_workflow=_CC_WORKFLOW).create(line_values)
        self._pos_apply_payload_promotion(header._branch_records(), payload)

    @api.model
    def _pos_submit_to_branch_rpc(self, payload):
        if payload.get('submission_guard_version') != 1:
            raise UserError(_('Reload the POS to use protected branch submission.'))
        payload = {k: deepcopy(v) for k, v in payload.items() if not k.startswith('_branch_')}
        values = payload.setdefault('header', {})
        token = str(values.get('pos_client_token') or uuid4()).strip()
        values['pos_client_token'] = token
        for key in ('branch_submission_payload', 'branch_submission_started', 'branch_request_revision',
                    'branch_header_id', 'eplus_serial', 'push_state', 'push_message'):
            values.pop(key, None)
        values['status'] = 'prepending'
        header, duplicate, _policy = self._pos_create_prepending_header_from_payload(payload)
        if header.store_id.id != int(values.get('store_id') or 0):
            raise AccessError(_('This store is not allowed.'))
        if header.status in ('pending', 'saved'):
            header.check_access('read')
            return header._branch_result()
        with header._branch_attempt():
            if header.status in ('pending', 'saved'):
                return header._branch_result()
            stored = header.sudo().branch_submission_payload or {}
            client = self.env['ab_sales_branch_client']
            config = client._config(header.store_id)
            target = {'_branch_db_serial': config.db_serial, '_branch_rpc_url': config.rpc_url,
                      '_branch_rpc_db': config.rpc_db, '_branch_store_serial': int(config.store_id.eplus_serial)}
            if stored and any(stored.get(name) != value for name, value in target.items()):
                raise UserError(_('The branch database changed. Reconcile the original request before retrying.'))
            if header.status == 'unknown':
                payload = stored
                wire = payload['_branch_wire_payload']
            else:
                capabilities = client._call(header.store_id, 'get_capabilities')
                config._validate_identity(capabilities)
                if capabilities.get('sales_submission_guard') != 1:
                    raise UserError(_('Upgrade the branch API before submitting this bill.'))
                wire = client._sale_payload(payload)
                if header.status == 'rejected' or (duplicate and not stored):
                    with self.env.cr.savepoint():
                        self._replace_branch_bill(header, payload)
                changed = bool(stored and stored.get('_branch_wire_payload') != wire)
                revision = header.branch_request_revision + (1 if changed else 0)
                payload = dict(payload, _branch_wire_payload=wire, **target)
                header.sudo()._write_branch_state({'branch_submission_payload': payload,
                    'branch_request_revision': revision, 'branch_submission_started': True})
            log = self.env['ab_sales_callcenter_rpc_log'].sudo().create({'rpc_config_id': config.id,
                'store_id': header.store_id.id, 'payload_token': token, 'request_revision': header.branch_request_revision,
                'push_to_eplus_requested': True, 'state': 'started', 'submitted_by_id': self.env.uid,
                'submitted_at': fields.Datetime.now()})
            header.sudo()._write_branch_state({'status': 'unknown', 'push_state': 'none', 'push_message': ''})
            self.env.cr.commit()
            header._lock_branch_bill()
            try:
                response = config._execute_kw('ab_branch_api', 'submit_sale', [config.db_serial, token, wire],
                                              {'request_revision': header.branch_request_revision})
                header._apply_branch_response(response, config)
            except Exception as error:
                self.env.cr.rollback()
                header.invalidate_recordset()
                header.sudo()._write_branch_state({'status': 'unknown', 'push_state': 'error', 'push_message': str(error)})
            result = header._branch_result()
            log.write({'state': 'success' if result['status'] in ('pending', 'saved') else 'error',
                'remote_header_id': result['branch_header_id'], 'remote_status': result['status'],
                'remote_eplus_serial': result['eplus_serial'], 'response_message': result['message'],
                'error_message': result['message'] if result['status'] in ('unknown', 'rejected') else ''})
            self.env.cr.commit()
            return result

    @api.model
    def pos_submission_states(self, tokens=None, pos_hr_session_token=None):
        if not isinstance(tokens, list) or len(tokens) > 200 or any(not isinstance(t, str) for t in tokens):
            raise UserError(_('Provide at most 200 request tokens.'))
        if 'ab_employee_access_sales_pos_api' in self.env.registry:
            session = self.env['ab_employee_access_sales_pos_api']._get_session(pos_hr_session_token, states=['active'])
            profile = session._get_pos_profile()
            if not profile or not profile._effective_pos_permissions().get('allow_sale'):
                raise AccessError(_('Employee role does not allow sales.'))
        headers = self.env['ab_sales_header'].search(fields.Domain('pos_client_token', 'in', tokens))
        headers._refresh_local_bill_statuses()
        return [header._branch_result() for header in headers]


class BillDepartmentAccess(models.Model):
    _inherit = 'ab_hr_department'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env.registry.clear_cache()
        return records

    def write(self, vals):
        result = super().write(vals)
        if {'user_id', 'store_id', 'active'}.intersection(vals):
            self.env.registry.clear_cache()
        return result

    def unlink(self):
        result = super().unlink()
        self.env.registry.clear_cache()
        return result


class BillEmployeeAccess(models.Model):
    _inherit = 'ab_hr_employee'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self.env.registry.clear_cache()
        return records

    def write(self, vals):
        result = super().write(vals)
        if {'user_id', 'department_id', 'active'}.intersection(vals):
            self.env.registry.clear_cache()
        return result

    def unlink(self):
        result = super().unlink()
        self.env.registry.clear_cache()
        return result


class BillReplicaAccess(models.Model):
    _inherit = 'ab_replica_db'

    def write(self, vals):
        result = super().write(vals)
        if 'allowed_sales_store_ids' in vals:
            self.env.registry.clear_cache()
        return result


class LocalReturns(models.Model):
    _inherit = 'ab_sales_return_header'

    active = fields.Boolean(default=True)

    def unlink(self):
        raise UserError(_('Archive callcenter bills instead of deleting them.'))
