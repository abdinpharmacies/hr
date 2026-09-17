"""Durable callcenter bills and branch-isolated status refresh."""
from copy import deepcopy
import logging
from uuid import uuid4

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)


class BillAccess(models.Model):
    _inherit = 'res.users'

    def _ab_sales_bill_domain(self, prefix=''):
        self.ensure_one()
        if not self.env['ab_sales_branch_client']._is_callcenter():
            return []
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

    branch_submission_payload = fields.Json(string='Branch Submission Payload', readonly=True, copy=False,
                                           groups='base.group_system')
    branch_header_id = fields.Integer(string='Branch Bill ID', readonly=True, copy=False)
    local_bill_storage = fields.Boolean(compute='_compute_local_bill_storage')

    def _compute_local_bill_storage(self):
        value = self.env['ab_sales_branch_client']._is_callcenter()
        for record in self:
            record.local_bill_storage = value

    branch_submission_started = fields.Boolean(string='Branch Submission Started', readonly=True, copy=False)

    def write(self, vals):
        if not self.env.su and {'branch_submission_payload', 'branch_header_id', 'branch_submission_started'}.intersection(vals):
            raise AccessError(_('Branch submission metadata is read-only.'))
        if not self.env.su and {'status', 'eplus_serial'}.intersection(vals) and any(self.sudo().mapped('branch_submission_payload')):
            raise AccessError(_('Branch submission metadata is read-only.'))
        protected = {'store_id', 'pos_client_token', 'line_ids', 'customer_id', 'employee_id',
                     'invoice_address', 'contract_id', 'new_customer_name', 'new_customer_phone',
                     'new_customer_address', 'bill_customer_name', 'bill_customer_phone', 'bill_customer_address',
                     'customer_insurance_name', 'customer_insurance_number', 'is_delivery', 'employee_delivery_id'}
        if protected.intersection(vals) and any(self.sudo().mapped('branch_submission_payload')):
            raise UserError(_('A submitted request cannot be edited. Retry the original bill.'))
        return super().write(vals)

    def action_submit(self):
        if self.env['ab_sales_branch_client']._is_callcenter():
            return self.action_retry_branch_submission()
        return super().action_submit()

    def unlink(self):
        if self.env['ab_sales_branch_client']._is_callcenter():
            raise UserError(_('Archive callcenter bills instead of deleting them.'))
        return super().unlink()

    def action_retry_branch_submission(self):
        self.ensure_one()
        self.check_access('write')
        if not self.env['ab_sales_branch_client']._is_callcenter():
            raise UserError(_('This action is only available on the callcenter.'))
        payload = self.sudo().branch_submission_payload
        if not payload:
            raise UserError(_('This bill has no stored branch submission request.'))
        self.env['ab_sales_pos_api']._pos_submit_to_branch_rpc(payload)
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    @api.model
    def refresh_bill_statuses(self, domain=None):
        """Explicit UI operation; never called implicitly by ORM search/read."""
        if not self.env['ab_sales_branch_client']._is_callcenter():
            return {'unavailable_branches': []}
        # Status filters are applied after synchronization. Other filters still scope work.
        domain = fields.Domain(domain or []).optimize(self).map_conditions(
            lambda c: fields.Domain.TRUE if c.field_expr == 'status' else c)
        records = self.search(domain & fields.Domain('status', '=', 'pending')
                              & fields.Domain('eplus_serial', '>', 0))
        return {'unavailable_branches': records._refresh_local_bill_statuses()}

    def _refresh_local_bill_statuses(self):
        self.check_access('read')
        client = self.env['ab_sales_branch_client']
        errors = []
        for store in self.store_id:
            bills = self.filtered(lambda h: h.store_id == store and h.status == 'pending' and h.eplus_serial > 0)
            try:
                with self.env.cr.savepoint():
                    config = client._config(store)
                    for bill in bills.sudo():
                        original_db = (bill.branch_submission_payload or {}).get('_branch_db_serial')
                        if original_db is not None and original_db != config.db_serial:
                            raise UserError(_('The branch database changed. Reconcile the original request before retrying.'))
                    serials = sorted(set(bills.mapped('eplus_serial')))
                    for offset in range(0, len(serials), 200):
                        batch = serials[offset:offset + 200]
                        response = client._call(store, 'get_invoice_statuses', batch)
                        if not isinstance(response, dict):
                            raise UserError(_('The branch returned invalid invoice status.'))
                        config._validate_identity(response)
                        if not isinstance(response.get('data'), list):
                            raise UserError(_('The branch returned invalid invoice status.'))
                        seen, saved = set(), []
                        for row in response['data']:
                            if (not isinstance(row, dict) or type(row.get('invoice')) is not int
                                    or row['invoice'] not in batch or row['invoice'] in seen
                                    or row.get('status') not in ('pending', 'saved')):
                                raise UserError(_('The branch returned invalid invoice status.'))
                            seen.add(row['invoice'])
                            if row['status'] == 'saved':
                                saved.append(row['invoice'])
                        # Elevation is limited to readable, branch-validated bills and one field.
                        targets = bills.filtered(lambda h: h.eplus_serial in saved)
                        targets.invalidate_recordset(['status'])
                        targets.filtered(lambda h: h.status == 'pending').sudo().write({'status': 'saved'})
            except (UserError, AccessError):
                _logger.warning('Bill status refresh failed for store %s; local bills retained.', store.id)
                errors.append(_('%s: status refresh unavailable; showing local bills.') % store.display_name)
        return errors

    def _compute_store_server_online(self):
        # Local forms must not depend on a live connectivity probe.
        if self.env['ab_sales_branch_client']._is_callcenter():
            for record in self:
                record.store_server_online = False
            return
        return super()._compute_store_server_online()


class LocalSaleLines(models.Model):
    _inherit = 'ab_sales_line'

    @api.depends('product_id', 'product_id.default_price')
    def _compute_sell_price(self):
        editable = self.filtered(lambda line: not line.header_id.sudo().branch_submission_payload)
        return super(LocalSaleLines, editable)._compute_sell_price()

    @api.constrains('sell_price', 'product_id', 'inventory_json', 'uom_id')
    def _check_sell_price_in_available_prices(self):
        # Frozen prices were validated at creation; catalog changes cannot reprice history.
        editable = self.filtered(lambda line: not line.header_id.sudo().branch_submission_payload)
        return super(LocalSaleLines, editable)._check_sell_price_in_available_prices()

    def write(self, vals):
        if {'product_id', 'uom_id', 'qty_str', 'qty', 'sell_price', 'header_id', 'products_not_exist'}.intersection(vals):
            targets = self.header_id | self.env['ab_sales_header'].browse(vals.get('header_id') or [])
            if any(targets.sudo().mapped('branch_submission_payload')):
                raise UserError(_('A submitted request cannot be edited. Retry the original bill.'))
        return super().write(vals)

    def unlink(self):
        if any(self.header_id.sudo().mapped('branch_submission_payload')):
            raise UserError(_('A submitted request cannot be edited. Retry the original bill.'))
        return super().unlink()

    @api.model_create_multi
    def create(self, vals_list):
        headers = self.env['ab_sales_header'].browse([v['header_id'] for v in vals_list if v.get('header_id')])
        if any(headers.sudo().mapped('branch_submission_payload')):
            raise UserError(_('A submitted request cannot be edited. Retry the original bill.'))
        return super().create(vals_list)


class LocalSubmission(models.TransientModel):
    _inherit = 'ab_sales_pos_api'

    @api.model
    def _pos_submit_to_branch_rpc(self, payload):
        client = self.env['ab_sales_branch_client']
        if not client._is_callcenter():
            return False
        payload = {k: deepcopy(v) for k, v in payload.items() if not k.startswith('_branch_')}
        values = payload.setdefault('header', {})
        token = str(values.get('pos_client_token') or uuid4()).strip()
        values['pos_client_token'] = token
        # Never accept lifecycle/transport fields from the browser.
        for key in ('branch_submission_payload', 'branch_submission_started', 'branch_header_id',
                    'eplus_serial', 'push_state', 'push_message'):
            values.pop(key, None)
        values['status'] = 'prepending'
        header, duplicate, _policy = self._pos_create_prepending_header_from_payload(payload)
        header.check_access('read')
        if header.store_id.id != int(values.get('store_id') or 0):
            raise AccessError(_('This store is not allowed.'))
        if duplicate and header.sudo().branch_submission_payload:
            payload = header.sudo().branch_submission_payload
        elif duplicate:
            raise UserError(_('This bill has no stored branch submission request.'))
        else:
            # Prepared before the network call, durable even when submission raises.
            header.write(header._get_bill_customer_snapshot_vals())
            header.sudo().write({'branch_submission_payload': payload, 'branch_submission_started': True})
        self.env.cr.commit()
        if header.branch_header_id:
            return dict(self._pos_remote_submit_response(header, duplicate_token=True),
                        branch_header_id=header.branch_header_id, remote_header_id=header.branch_header_id,
                        local_header_id=header.id)
        header.check_access('write')
        log = self.env['ab_sales_callcenter_rpc_log']
        try:
            config = client._config(header.store_id)
            if '_branch_wire_payload' not in payload:
                payload = dict(payload, _branch_wire_payload=client._sale_payload(payload),
                               _branch_push_to_eplus=bool(config.push_to_eplus_on_submit),
                               _branch_db_serial=config.db_serial)
                header.sudo().write({'branch_submission_payload': payload})
            if payload['_branch_db_serial'] != config.db_serial:
                raise UserError(_('The branch database changed. Reconcile the original request before retrying.'))
            if 'status' in payload['_branch_wire_payload'].get('header', {}):
                # Earlier local drafts included status in the stored request. The
                # branch rejects it before posting; retain the token and every
                # business value when correcting that rejected request for retry.
                payload = deepcopy(payload)
                payload['_branch_wire_payload']['header'].pop('status')
                header.sudo().write({'branch_submission_payload': payload})
            log = log.sudo().create({'rpc_config_id': config.id, 'store_id': header.store_id.id,
                'payload_token': token, 'push_to_eplus_requested': payload['_branch_push_to_eplus'],
                'state': 'started', 'submitted_by_id': self.env.uid, 'submitted_at': fields.Datetime.now()})
            self.env.cr.commit()
            response = config._execute_kw('ab_branch_api', 'submit_sale',
                [config.db_serial, token, payload['_branch_wire_payload'], payload['_branch_push_to_eplus']])
            if (not isinstance(response, dict) or type(response.get('branch_header_id')) is not int
                    or response['branch_header_id'] <= 0 or type(response.get('eplus_serial')) is not int
                    or response['eplus_serial'] < 0 or response.get('status') not in ('prepending', 'pending', 'saved')
                    or (response['status'] != 'prepending' and not response['eplus_serial'])):
                raise UserError(_('Branch RPC submit returned an invalid response.'))
            config._validate_identity(response)
            header.sudo().write({'branch_header_id': response['branch_header_id'],
                'status': response['status'], 'eplus_serial': response['eplus_serial'],
                'push_state': 'success', 'push_message': response.get('message') or ''})
            log.write({'state': 'success', 'remote_header_id': response['branch_header_id'],
                'remote_status': response['status'], 'remote_eplus_serial': response['eplus_serial'],
                'response_message': response.get('message') or ''})
            self.env.cr.commit()
            return dict(response, local_header_id=header.id)
        except Exception as error:
            self.env.cr.rollback()
            header.sudo().write({'push_state': 'error', 'push_message': str(error)})
            if log:
                log.write({'state': 'error', 'error_message': str(error)})
            self.env.cr.commit()
            raise


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
        if self.env['ab_sales_branch_client']._is_callcenter():
            raise UserError(_('Archive callcenter bills instead of deleting them.'))
        return super().unlink()
