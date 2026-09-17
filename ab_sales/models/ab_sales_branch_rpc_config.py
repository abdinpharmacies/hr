# -*- coding: utf-8 -*-

import ipaddress
import logging
import requests
from urllib.parse import urlparse

from cryptography.fernet import Fernet, InvalidToken

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import config


_logger = logging.getLogger(__name__)


class AbSalesBranchRpcConfig(models.Model):
    _name = "ab_sales_branch_rpc_config"
    _description = "Sales Branch RPC Configuration"
    _order = "store_id, id"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(required=True, default=lambda self: _("New Branch RPC Configuration"))
    active = fields.Boolean(default=True)
    store_id = fields.Many2one("ab_store", required=True, ondelete="restrict", index=True)
    db_serial = fields.Integer(string="DB Serial", required=True, index=True)
    store_code = fields.Char(related="store_id.code", readonly=True)
    rpc_url = fields.Char(string="Branch Odoo URL", required=True)
    rpc_db = fields.Char(string="Branch Database", required=True)
    rpc_user = fields.Char(string="Verified Integration User", readonly=True)
    api_key = fields.Char(string="API Key", compute='_compute_api_key', inverse='_inverse_api_key',
                          groups='base.group_system', exportable=False)
    api_key_encrypted = fields.Char(readonly=True, copy=False, groups='base.group_system', exportable=False)
    enrollment_state = fields.Selection(
        [('required', 'Verification Required'), ('ready', 'Ready')],
        string='Connection Status', default='required', readonly=True, copy=False)
    expires_at = fields.Datetime(readonly=True, copy=False)
    last_success_at = fields.Datetime(readonly=True, copy=False)
    administrator_id = fields.Many2one('res.users', string='Responsible Administrator',
        required=True, default=lambda self: self.env.user)
    remote_user_id = fields.Integer(readonly=True, copy=False)
    can_post = fields.Boolean(readonly=True, copy=False)
    alert_activity_id = fields.Many2one('mail.activity', readonly=True, copy=False)

    connection_timeout = fields.Integer(default=15)
    push_to_eplus_on_submit = fields.Boolean(
        string="Push to E-Plus on Submit",
        help="When enabled, call-center POS submit asks the branch Odoo to push the remote prepending invoice to E-Plus immediately.",
    )
    last_test_state = fields.Selection(
        selection=[
            ("untested", "Untested"),
            ("success", "Success"),
            ("error", "Error"),
        ],
        default="untested",
        readonly=True,
        copy=False,
    )
    last_test_message = fields.Text(readonly=True, copy=False)
    last_tested_at = fields.Datetime(readonly=True, copy=False)
    remote_store_id = fields.Integer(readonly=True, copy=False)
    remote_store_name = fields.Char(readonly=True, copy=False)

    _uniq_store_rpc_config = models.Constraint(
        "UNIQUE(store_id)",
        "Only one branch RPC configuration is allowed per store.",
    )

    def _require_admin(self):
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Settings administrator access is required.'))

    def _compute_api_key(self):
        for record in self:
            record.api_key = False

    def _inverse_api_key(self):
        self._require_admin()
        for record in self:
            if record.api_key:
                record.write({'api_key_encrypted': record._encrypt_secret(record.api_key.strip()),
                              'enrollment_state': 'required',
                              'remote_user_id': 0, 'expires_at': False})

    def export_data(self, fields_to_export):
        if any('key' in path.split('/')[0] for path in fields_to_export):
            raise AccessError(_('Credentials cannot be exported.'))
        return super().export_data(fields_to_export)

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._normalize_vals(vals) for vals in vals_list]
        records = super().create(vals_list)
        records._sync_display_name()
        return records

    def write(self, vals):
        vals = self._normalize_vals(dict(vals or {}))
        if set(vals) & {'rpc_url', 'rpc_db', 'store_id', 'db_serial', 'api_key_encrypted', 'active'}:
            vals = dict(vals, enrollment_state='required', remote_user_id=0, rpc_user=False,
                        remote_store_id=0, remote_store_name=False, can_post=False, expires_at=False,
                        last_test_state='untested', last_test_message=False, last_tested_at=False)
        result = super().write(vals)
        if any(key in vals for key in ("store_id", "rpc_url", "rpc_db")):
            self._sync_display_name()
        return result

    @api.model
    def _normalize_vals(self, vals):
        normalized = dict(vals or {})
        if "rpc_url" in normalized and normalized["rpc_url"]:
            normalized["rpc_url"] = str(normalized["rpc_url"]).strip().rstrip("/")
        for key in ("rpc_db", "rpc_user"):
            if key in normalized and normalized[key]:
                normalized[key] = str(normalized[key]).strip()
        return normalized

    def _sync_display_name(self):
        for record in self:
            if record.name and record.name != _("New Branch RPC Configuration"):
                continue
            store_name = record.store_id.display_name if record.store_id else _("Branch")
            record.name = _("%s RPC") % store_name

    @api.constrains('administrator_id')
    def _check_administrator(self):
        for record in self:
            if not record.administrator_id.active or not record.administrator_id.has_group('base.group_system'):
                raise ValidationError(_('Choose an active Settings administrator.'))

    @api.constrains('db_serial', 'store_id')
    def _check_branch_connection(self):
        for record in self:
            if record.db_serial <= 0:
                raise ValidationError(_('DB serial must be a positive integer.'))
            if (not record.store_id.active or not record.store_id.allow_sale
                    or record.store_id.eplus_serial <= 0):
                raise ValidationError(_('This store is not allowed.'))

    @api.constrains("rpc_url")
    def _check_rpc_url(self):
        for record in self:
            parsed = urlparse((record.rpc_url or "").strip())
            try:
                loopback = parsed.hostname == 'localhost' or ipaddress.ip_address(parsed.hostname).is_loopback
            except ValueError:
                loopback = False
            if (parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.username
                    or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/')
                    or (parsed.scheme == 'http' and not loopback)):
                raise ValidationError(_("Use HTTPS for branch connections; HTTP is allowed only on loopback addresses."))

    @api.constrains("connection_timeout")
    def _check_connection_timeout(self):
        for record in self:
            timeout = int(record.connection_timeout or 0)
            if timeout < 3 or timeout > 120:
                raise ValidationError(_("Connection timeout must be between 3 and 120 seconds."))

    @api.model
    def _fernet(self):
        key = config.get("decryption_key")
        if not key:
            raise UserError(_("Odoo configuration key 'decryption_key' is required for RPC secrets."))
        return Fernet(bytes(key, "utf-8"))

    def _encrypt_secret(self, value):
        value = str(value or "")
        if not value:
            return False
        return self._fernet().encrypt(bytes(value, "utf-8")).decode("utf-8")

    def _decrypt_secret(self, encrypted_value):
        encrypted_value = str(encrypted_value or "")
        if not encrypted_value:
            return ""
        try:
            return self._fernet().decrypt(bytes(encrypted_value, "utf-8")).decode("utf-8")
        except InvalidToken as error:
            raise UserError(_("Stored RPC secret cannot be decrypted with the current decryption key.")) from error

    def _json_call(self, model, method, values, key=None):
        self.ensure_one()
        self._check_rpc_url()
        secret = key or self._decrypt_secret(self.api_key_encrypted)
        if not secret:
            raise UserError(_('Enroll a branch API credential first.'))
        try:
            response = requests.post(
                '%s/json/2/%s/%s' % (self.rpc_url, model, method), json=values,
                headers={'Authorization': 'bearer ' + secret, 'X-Odoo-Database': self.rpc_db},
                timeout=int(self.connection_timeout), allow_redirects=False)
        except requests.RequestException:
            raise UserError(_('The branch connection failed. Check its network address and availability.')) from None
        try:
            body = response.json()
        except ValueError:
            body = {}
        if not response.ok or response.is_redirect:
            if isinstance(body, dict) and body.get('name') in (
                    'odoo.exceptions.UserError', 'odoo.exceptions.ValidationError', 'odoo.exceptions.AccessError'):
                message = str(body.get('message', ''))
                for value in (secret, values.get('key')):
                    if value:
                        message = message.replace(value, '[redacted]')
                raise UserError(message) from None
            if response.status_code in (401, 403):
                raise AccessError(_('The branch rejected the credential or its permissions.'))
            _logger.warning('Branch connection %s: %s.%s HTTP %s', self.id, model, method, response.status_code)
            raise UserError(_('The branch returned an unexpected response (HTTP %s).') % response.status_code)
        if not isinstance(body, (dict, list, str, bool)):
            raise UserError(_('The branch returned an invalid JSON response.'))
        return body

    def _execute_kw(self, model_name, method, args=None, kwargs=None):
        # Internal compatibility adapter only; all outbound requests use JSON-2.
        signatures = {
            'get_capabilities': ('db_serial',),
            'get_product_balances': ('db_serial', 'product_serials'),
            'lookup_customer': ('db_serial', 'phone'),
            'create_customer': ('db_serial', 'token', 'phone', 'name', 'address'),
            'get_inventory_snapshot': ('db_serial', 'token', 'offset'),
            'get_sales_day': ('db_serial', 'sale_date', 'token', 'offset'),
            'get_invoice_statuses': ('db_serial', 'invoices'),
            'get_sale_statuses': ('db_serial', 'tokens'),
            'search_bills': ('db_serial', 'filters', 'token', 'offset'),
            'get_bill_details': ('db_serial', 'reference'),
            'update_bill_notes': ('db_serial', 'reference', 'notes'),
            'render_bill_print': ('db_serial', 'reference', 'print_format'),
            'get_stock_lines': ('db_serial', 'product_serials'),
            'search_products': ('db_serial', 'query', 'limit', 'offset'),
            'submit_sale': ('db_serial', 'token', 'payload', 'push_to_eplus'),
            'get_return_invoice': ('db_serial', 'invoice', 'token', 'selections'),
            'submit_return': ('db_serial', 'invoice', 'token', 'lines', 'notes', 'employee_ref'),
            'get_operation_status': ('db_serial', 'token'),
            'reconcile_operation': ('db_serial', 'token'),
        }
        self.ensure_one()
        if not self.active or self.enrollment_state != 'ready':
            raise UserError(_('Verify and activate the branch connection before using it.'))
        if model_name != 'ab_branch_api' or method not in signatures or len(args or []) > len(signatures[method]):
            raise UserError(_('Unsupported branch API operation.'))
        self._check_branch_connection()
        values = dict(zip(signatures[method], args or []), **(kwargs or {}))
        if type(values.get('db_serial')) is not int or values['db_serial'] != self.db_serial:
            raise UserError(_('Branch identity or credential metadata is not configured correctly.'))
        selected_serial = int(self.store_id.eplus_serial)
        if ('store_eplus_serial' in values and
                (type(values['store_eplus_serial']) is not int or values['store_eplus_serial'] != selected_serial)):
            raise UserError(_('Branch identity or credential metadata is not configured correctly.'))
        values['store_eplus_serial'] = selected_serial
        if method in ('search_bills', 'get_bill_details', 'update_bill_notes',
                      'render_bill_print', 'get_return_invoice', 'submit_return'):
            self._require_callcenter_bill_scope()
        writes = ('submit_sale', 'submit_return', 'create_customer')
        status_values = {'db_serial': self.db_serial, 'store_eplus_serial': selected_serial,
                         'token': values.get('token')}
        if method == 'create_customer':
            status = self._json_call('ab_branch_api', 'get_operation_status', status_values)
            self._validate_identity(status)
            if status.get('state') in ('processing', 'uncertain'):
                raise UserError(_('Operation outcome needs reconciliation. Check the branch before retrying.'))
        try:
            result = self._json_call(model_name, method, values)
        except UserError as original_error:
            if method in ('submit_sale', 'submit_return'):
                try:
                    status = self._json_call('ab_branch_api', 'reconcile_operation', status_values)
                    self._validate_identity(status)
                except (UserError, AccessError) as recovery_error:
                    raise UserError(_('Submission error: %(submission)s\nRecovery error: %(recovery)s\nYour bill is retained with its original request token.') % {
                        'submission': str(original_error), 'recovery': str(recovery_error)}) from original_error
                if status.get('state') == 'done':
                    # Replay only the API result. The provider checks the original
                    # payload hash before returning it; no blind external repost.
                    result = self._json_call(model_name, method, values)
                    self._validate_identity(result)
                    return result
                if status.get('state') in ('processing', 'uncertain'):
                    raise UserError(_('The branch is still processing this submission. Your bill is retained; retry the same bill shortly.')) from original_error
                # A proven rollback is retryable, but preserve the original error
                # (e.g. missing employee mapping) instead of repeatedly posting it.
                raise
            if method in writes:
                try:
                    status = self._json_call('ab_branch_api', 'get_operation_status', status_values)
                    self._validate_identity(status)
                except (UserError, AccessError):
                    raise UserError(_('The operation outcome is unknown. Keep the request token and check the branch before retrying.')) from None
                # Do not hide a payload mismatch by returning an older completed result.
                # A retry uses the same token and lets the provider verify its payload hash.
                if status.get('state') in ('processing', 'uncertain', 'done'):
                    raise UserError(_('The operation may have completed. Retry with the same request token to reconcile.')) from None
            raise
        if method != 'search_products':
            self._validate_identity(result)
            if method in ('get_operation_status', 'reconcile_operation') and result.get('result'):
                self._validate_identity(result['result'])
        return result

    def _require_callcenter_bill_scope(self):
        self.ensure_one()
        capabilities = self._json_call('ab_branch_api', 'get_capabilities',
            {'db_serial': self.db_serial, 'store_eplus_serial': int(self.store_id.eplus_serial)})
        self._validate_identity(capabilities)
        if capabilities.get('bill_scope') != 'callcenter_only':
            raise UserError(_('Upgrade the branch API to support call-center-only bills, then retest the connection.'))

    def _validate_identity(self, result):
        self.ensure_one()
        if (not isinstance(result, dict)
                or type(result.get('db_serial')) is not int or result['db_serial'] != self.db_serial
                or type(result.get('store_eplus_serial')) is not int
                or result['store_eplus_serial'] != self.store_id.eplus_serial):
            raise UserError(_('Branch identity or credential metadata is not configured correctly.'))

    def _status(self, key=None):
        self._check_branch_connection()
        result = self._json_call('ab_branch_api', 'get_connection_status',
                                 {'db_serial': self.db_serial, 'store_eplus_serial': int(self.store_id.eplus_serial)}, key=key)
        self._validate_identity(result)
        if (not isinstance(result, dict) or result.get('version') != 1
                or type(result.get('db_serial')) is not int or result['db_serial'] != self.db_serial
                or 'expires_at' not in result
                or not result.get('user_id')):
            raise UserError(_('Branch identity or credential metadata is not configured correctly.'))
        required = {'get_product_balances', 'lookup_customer', 'create_customer', 'search_bills',
                    'get_bill_details', 'update_bill_notes', 'render_bill_print',
                    'get_inventory_snapshot', 'get_sales_day', 'get_invoice_statuses', 'get_sale_statuses',
                    'reconcile_operation'}
        if result.get('bill_scope') != 'callcenter_only':
            raise UserError(_('Upgrade the branch API to support call-center-only bills, then retest the connection.'))
        if not required.issubset(set(result.get('methods') or [])):
            raise UserError(_('Upgrade the branch API before using this call-center version.'))
        return result

    def action_test_connection(self):
        self._require_admin()
        for record in self:
            record.job_manage_connection('check')
        return True

    def _check_connection(self):
        try:
            result = self._status()
            self.write({'last_test_state': 'success', 'last_test_message': _('Connection verified.'),
                'last_tested_at': fields.Datetime.now(), 'last_success_at': fields.Datetime.now(),
                'remote_store_id': result['branch_store_id'], 'remote_store_name': result['store_name'],
                'remote_user_id': result['user_id'], 'rpc_user': result['login'],
                'expires_at': result['expires_at'], 'can_post': result['can_post'], 'enrollment_state': 'ready'})
        except (UserError, AccessError) as error:
            self.write({'last_test_state': 'error', 'last_test_message': str(error),
                        'last_tested_at': fields.Datetime.now()})
        self._update_alert()

    def _update_alert(self):
        warning = self.last_test_state == 'error'
        activity = self.alert_activity_id.exists()
        if warning and not activity:
            self.alert_activity_id = self.activity_schedule(
                'mail.mail_activity_data_todo', user_id=self.administrator_id.id,
                summary=_('Branch connection needs attention'),
                note=_('Review the connection address, credential, and branch permissions.'))
        elif not warning and activity:
            activity.action_feedback()

    def action_check_connections(self):
        self._require_admin()
        for record in self.filtered('active'):
            record.with_delay(identity_key='branch-check-%s' % record.id).job_manage_connection('check')
        return True

    def job_manage_connection(self, operation='check'):
        self._require_admin()
        self.ensure_one()
        # Only health checks may run; queued rotation requests perform no action.
        if operation != 'check' or not self.active:
            return
        slot = None
        for candidate in range(4):
            self.env.cr.execute('SELECT pg_try_advisory_lock(%s, %s)', (190902, candidate))
            if self.env.cr.fetchone()[0]:
                slot = candidate
                break
        if slot is None:
            return
        # Serialize health checks for the same connection.
        self.env.cr.execute('SELECT pg_try_advisory_lock(%s, %s)', (190901, self.id))
        if not self.env.cr.fetchone()[0]:
            self.env.cr.execute('SELECT pg_advisory_unlock(%s, %s)', (190902, slot))
            return
        try:
            self.flush_recordset()
            self.invalidate_recordset()
            if not self.active:
                return
            self._check_connection()
            self.env.cr.commit()
        except Exception:
            self.env.cr.rollback()
            raise
        finally:
            self.env.cr.execute('SELECT pg_advisory_unlock(%s, %s)', (190901, self.id))
            self.env.cr.execute('SELECT pg_advisory_unlock(%s, %s)', (190902, slot))

    @api.model
    def _cron_connections(self, operation='check'):
        if operation != 'check':
            return
        for record in self.search(fields.Domain('active', '=', True)):
            record.with_delay(identity_key='branch-check-%s' % record.id).job_manage_connection('check')
