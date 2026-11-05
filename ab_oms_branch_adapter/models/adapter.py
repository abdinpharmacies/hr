import json
from urllib.parse import urlsplit

import requests

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


class Connection(models.Model):
    _name = 'ab_oms_connection'
    _inherit = 'ab_crm_scoped'
    _description = 'OMS Branch Connection'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    endpoint = fields.Char(required=True)
    database = fields.Char(required=True)
    db_serial = fields.Integer(required=True)
    store_serial = fields.Integer(required=True)
    api_key = fields.Char(required=True, groups='ab_crm_core.group_manager', copy=False)
    verified = fields.Boolean(readonly=True)
    _branch_unique = models.Constraint('UNIQUE(branch_id)', 'Only one connection is allowed per branch.')

    @api.constrains('endpoint', 'db_serial', 'store_serial')
    def _check_config(self):
        for record in self:
            url = urlsplit(record.endpoint)
            if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in ('', '/'):
                raise ValidationError(_('Use an HTTPS origin without credentials, path or query.'))
            if record.db_serial <= 0 or record.store_serial <= 0:
                raise ValidationError(_('Branch and database serials must be positive.'))

    @api.model_create_multi
    def create(self, values_list):
        for values in values_list:
            values['verified'] = False
        return super().create(values_list)

    def write(self, values):
        from odoo.addons.ab_crm_core.models.core import _INTERNAL
        if 'verified' in values and not _INTERNAL.get():
            raise AccessError(_('Verify the branch connection through the supported action.'))
        if {'endpoint', 'database', 'db_serial', 'store_serial', 'api_key', 'branch_id'} & values.keys():
            values = dict(values, verified=False)
        return super().write(values)

    def _call(self, method, payload):
        self.ensure_one()
        self._authorize('read')
        if method not in ('get_capabilities', 'submit_sale', 'get_sale_statuses', 'get_product_balances'):
            raise AccessError(_('Unsupported branch operation.'))
        if not self.active:
            raise UserError(_('The branch connection is inactive.'))
        response = requests.post(self.endpoint.rstrip('/') + '/json/2/ab_branch_api/' + method,
            json=dict(payload, db_serial=self.db_serial, store_eplus_serial=self.store_serial),
            headers={'Authorization': 'Bearer ' + self.sudo().api_key, 'X-Odoo-Database': self.database},
            timeout=(5, 25), allow_redirects=False)
        response.raise_for_status()
        if len(response.content) > 2_000_000:
            raise UserError(_('The branch response exceeds the supported size.'))
        data = response.json()
        if not isinstance(data, dict) or type(data.get('db_serial')) is not int or data['db_serial'] != self.db_serial or type(data.get('store_eplus_serial')) is not int or data['store_eplus_serial'] != self.store_serial:
            raise UserError(_('The branch returned mismatched identity evidence.'))
        return data

    def action_verify(self):
        self._authorize()
        data = self._call('get_capabilities', {})
        if data.get('sales_submission_guard') != 1:
            raise UserError(_('The branch does not support guarded submissions.'))
        return self._internal_write({'verified': True})


class Request(models.Model):
    _inherit = 'ab_oms_request'

    def _destination(self):
        self.ensure_one()
        connection = self.env['ab_oms_connection'].search(fields.Domain('branch_id', '=', self.branch_id.id), limit=1)
        if not connection or not connection.verified:
            raise UserError(_('Verify the selected branch connection before submitting.'))
        return {'connection_id': connection.id, 'endpoint': connection.endpoint, 'database': connection.database,
                'db_serial': connection.db_serial, 'store_serial': connection.store_serial}


class Attempt(models.Model):
    _inherit = 'ab_oms_attempt'

    def _worker(self):
        if not self.env.user.has_group('ab_oms_branch_adapter.group_worker'):
            raise AccessError(_('Only the integration worker can deliver submissions.'))

    @api.model
    def lease_submission(self):
        self._worker()
        attempt = self.search(fields.Domain('queued', '=', True) & fields.Domain('retired', '=', False), order='id', limit=1)
        if not attempt:
            return False
        attempt._authorize()
        attempt.lock_for_update()
        attempt._internal_write({'queued': False, 'state': 'unknown', 'can_edit': False})
        return {'id': attempt.id, 'revision': attempt.revision}

    def _connection(self):
        self.ensure_one()
        self._authorize()
        connection = self.env['ab_oms_connection'].browse(self.destination['connection_id'])
        connection._authorize('read')
        expected = {'connection_id': connection.id, 'endpoint': connection.endpoint, 'database': connection.database,
                    'db_serial': connection.db_serial, 'store_serial': connection.store_serial}
        if connection.branch_id != self.branch_id or expected != self.destination or not connection.verified:
            raise UserError(_('The frozen destination no longer matches the verified connection.'))
        return connection

    def _apply_result(self, result):
        self.ensure_one()
        state = result.get('status')
        remote = result.get('branch_header_id')
        invoice = result.get('eplus_serial')
        if (result.get('submission_guard_version') != 1 or result.get('token') != self.token
                or type(result.get('request_revision')) is not int or result['request_revision'] != self.revision
                or state not in ('unknown', 'rejected', 'pending', 'saved')
                or type(remote) is not int or remote < 0 or type(invoice) is not int or invoice < 0
                or (state in ('pending', 'saved') and (remote <= 0 or invoice <= 0))
                or (state in ('unknown', 'rejected') and invoice != 0)
                or (self.branch_header_id and remote != self.branch_header_id)
                or (self.invoice_reference and invoice != self.invoice_reference)
                or (self.state in ('pending', 'saved') and state in ('unknown', 'rejected'))
                or (self.state == 'saved' and state != 'saved')):
            raise UserError(_('The branch returned invalid submission evidence.'))
        self._internal_write({'state': state, 'branch_header_id': remote, 'invoice_reference': invoice,
                              'result': result, 'can_edit': state == 'rejected' and result.get('can_edit') is True,
                              'last_error': result.get('message') or False, 'last_success': fields.Datetime.now()})
        self._status_event()

    def _status_event(self):
        return None

    def deliver_submission(self, revision):
        self.ensure_one()
        self._worker()
        self._authorize()
        self.lock_for_update()
        if self.retired or self.queued or self.revision != revision or self.state != 'unknown':
            raise UserError(_('This delivery lease is no longer valid.'))
        try:
            self.request_id._validate_ready()
            connection = self._connection()
            result = connection._call('submit_sale', {'token': self.token, 'payload': self.payload, 'request_revision': self.revision, 'push_to_eplus': True})
            with self.env.cr.savepoint():
                self._apply_result(result)
        except (requests.RequestException, ValueError, UserError):
            self._internal_write({'last_error': _('The outcome is unknown. Check branch status before retrying the original operation.')})
        return {'id': self.id, 'state': self.state}

    def action_check_status(self):
        self.ensure_one()
        self._authorize()
        self.lock_for_update()
        response = self._connection()._call('get_sale_statuses', {'tokens': [self.token]})
        rows = response.get('data', [])
        if len(rows) != 1:
            raise UserError(_('The branch returned invalid submission evidence.'))
        self._apply_result(rows[0])
        return True


class ReferenceMap(models.Model):
    _name = 'ab_oms_reference_map'
    _inherit = 'ab_crm_scoped'
    _description = 'OMS Product and Unit Mapping'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    source = fields.Char(required=True)
    product_reference = fields.Char(required=True)
    unit_reference = fields.Char(required=True)
    branch_product_reference = fields.Integer(required=True)
    unit_factor = fields.Float(required=True)
    _mapping_unique = models.Constraint('UNIQUE(branch_id, source, product_reference, unit_reference)', 'A product and unit mapping already exists for this branch and source.')

    @api.constrains('branch_product_reference', 'unit_factor')
    def _check_mapping(self):
        import math
        for record in self:
            if record.branch_product_reference <= 0 or not math.isfinite(record.unit_factor) or record.unit_factor <= 0:
                raise ValidationError(_('Provide a positive branch product reference and unit factor.'))


class Line(models.Model):
    _inherit = 'ab_oms_line'

    mapping_id = fields.Many2one('ab_oms_reference_map', string='Verified Product Mapping', ondelete='restrict', check_company=True, copy=False)

    @api.constrains('mapping_id', 'branch_id')
    def _check_mapping_scope(self):
        for line in self:
            if line.mapping_id:
                line.mapping_id.check_access('read')
                if line.mapping_id.branch_id != line.branch_id:
                    raise ValidationError(_('Related records must belong to the same branch.'))

    def action_apply_mapping(self):
        self._authorize()
        for line in self:
            mapping = line.mapping_id
            mapping._authorize('read')
            if not mapping or not mapping.active or mapping.branch_id != line.branch_id:
                raise UserError(_('Choose an active product mapping for the request branch.'))
            source_reference = line.request_id.source_reference or line.request_id.replacement_of.source_reference
            if source_reference and mapping.source != json.loads(source_reference)[0]:
                raise UserError(_('The mapping does not match the website product and unit.'))
            if line.source_product_reference and (mapping.product_reference != line.source_product_reference or mapping.unit_reference != line.source_unit_reference):
                raise UserError(_('The mapping does not match the website product and unit.'))
            line.write({'branch_product_reference': mapping.branch_product_reference, 'unit_factor': mapping.unit_factor})
        return True
