# -*- coding: utf-8 -*-

import ipaddress
import logging
from datetime import timedelta
from uuid import uuid4
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
    store_eplus_serial = fields.Integer(related="store_id.eplus_serial", readonly=True)
    store_code = fields.Char(related="store_id.code", readonly=True)
    rpc_url = fields.Char(string="Branch Odoo URL", required=True)
    rpc_db = fields.Char(string="Branch Database", required=True)
    rpc_user = fields.Char(string="Verified Integration User", readonly=True)
    api_key = fields.Char(string="API Key", compute='_compute_api_key', inverse='_inverse_api_key',
                          groups='base.group_system', exportable=False)
    api_key_encrypted = fields.Char(readonly=True, copy=False, groups='base.group_system', exportable=False)
    pending_key_encrypted = fields.Char(readonly=True, copy=False, groups='base.group_system', exportable=False)
    previous_key_encrypted = fields.Char(readonly=True, copy=False, groups='base.group_system', exportable=False)
    enrollment_state = fields.Selection([('required', 'Enrollment Required'), ('ready', 'Ready'),
                                         ('revoked', 'Revoked')], default='required', readonly=True, copy=False)
    rotation_state = fields.Selection([('idle', 'Idle'), ('generating', 'Generating'),
        ('pending', 'Verification Pending'), ('overlap', 'Overlap'), ('review', 'Needs Review')],
        default='idle', readonly=True, copy=False)
    expires_at = fields.Datetime(readonly=True, copy=False)
    retire_at = fields.Datetime(readonly=True, copy=False)
    last_success_at = fields.Datetime(readonly=True, copy=False)
    management_message = fields.Text(readonly=True, copy=False)
    administrator_id = fields.Many2one('res.users', string='Responsible Administrator',
        required=True, default=lambda self: self.env.user)
    remote_user_id = fields.Integer(readonly=True, copy=False)
    can_post = fields.Boolean(readonly=True, copy=False)
    rotation_name = fields.Char(readonly=True, copy=False)
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
                if record.rotation_state not in ('idle', 'review'):
                    raise UserError(_('Complete credential rotation before replacing the enrollment key.'))
                record.write({'api_key_encrypted': record._encrypt_secret(record.api_key.strip()),
                              'enrollment_state': 'required', 'rotation_state': 'idle',
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
        if set(vals) & {'rpc_url', 'rpc_db', 'store_id'}:
            if any(r.rotation_state not in ('idle', 'review') for r in self):
                raise UserError(_('Complete credential rotation before changing the destination.'))
            vals = dict(vals, enrollment_state='required', remote_user_id=0)
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
        if not isinstance(body, (dict, str, bool)):
            raise UserError(_('The branch returned an invalid JSON response.'))
        return body

    def _execute_kw(self, model_name, method, args=None, kwargs=None):
        # Internal compatibility adapter only; all outbound requests use JSON-2.
        signatures = {
            'get_capabilities': ('store_serial',),
            'get_stock_lines': ('store_serial', 'product_serials'),
            'search_products': ('store_serial', 'query', 'limit', 'offset'),
            'submit_sale': ('store_serial', 'token', 'payload', 'push_to_eplus'),
            'get_return_invoice': ('store_serial', 'invoice', 'token', 'selections'),
            'submit_return': ('store_serial', 'invoice', 'token', 'lines', 'notes', 'employee_ref'),
            'get_operation_status': ('store_serial', 'token'),
        }
        self.ensure_one()
        if not self.active or self.enrollment_state != 'ready':
            raise UserError(_('Verify and activate the branch connection before using it.'))
        if model_name != 'ab_branch_api' or method not in signatures or len(args or []) > len(signatures[method]):
            raise UserError(_('Unsupported branch API operation.'))
        values = dict(zip(signatures[method], args or []), **(kwargs or {}))
        return self._json_call(model_name, method, values)

    def _status(self, key=None):
        result = self._json_call('ab_branch_api', 'get_connection_status',
                                 {'store_serial': int(self.store_id.eplus_serial)}, key=key)
        if (not isinstance(result, dict) or result.get('version') != 1
                or result.get('store_serial') != self.store_id.eplus_serial
                or not result.get('expires_at') or not result.get('programmatic_keys')
                or not result.get('user_id')):
            raise UserError(_('Branch identity, expiry, or programmatic key management is not configured correctly.'))
        if self.remote_user_id and result['user_id'] != self.remote_user_id:
            raise AccessError(_('The replacement credential belongs to a different integration user.'))
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
        warning = (self.last_test_state == 'error' or self.rotation_state in ('review', 'generating', 'pending')
                   or bool(self.management_message)
                   or (self.expires_at and self.expires_at <= fields.Datetime.now() + timedelta(days=30)))
        activity = self.alert_activity_id.exists()
        if warning and not activity:
            self.alert_activity_id = self.activity_schedule(
                'mail.mail_activity_data_todo', user_id=self.administrator_id.id,
                summary=_('Branch connection needs attention'),
                note=_('Review the connection health, credential expiry, and rotation status.'))
        elif not warning and activity:
            activity.action_feedback()


    def action_check_connections(self):
        self._require_admin()
        for record in self.filtered('active'):
            record.with_delay(identity_key='branch-check-%s' % record.id).job_manage_connection('check')
        return True

    def action_rotate_credentials(self):
        self._require_admin()
        for record in self.filtered('active'):
            record.with_delay(identity_key='branch-rotate-%s' % record.id).job_manage_connection('rotate')
        return True

    def action_revoke_credential(self):
        self._require_admin()
        self.ensure_one()
        self.env.cr.execute('SELECT pg_try_advisory_lock(%s, %s)', (190901, self.id))
        if not self.env.cr.fetchone()[0]:
            raise UserError(_('Complete or reconcile rotation before revoking this connection.'))
        try:
            self.flush_recordset()
            self.invalidate_recordset()
            if self.rotation_state != 'idle':
                raise UserError(_('Complete or reconcile rotation before revoking this connection.'))
            self._json_call('ab_branch_api', 'revoke_credential', {
                'store_serial': self.store_id.eplus_serial,
                'key': self._decrypt_secret(self.api_key_encrypted)})
            self.write({'enrollment_state': 'revoked', 'active': False, 'api_key_encrypted': False})
            self.env.cr.commit()
        except Exception:
            self.env.cr.rollback()
            raise
        finally:
            self.env.cr.execute('SELECT pg_advisory_unlock(%s, %s)', (190901, self.id))
        return True

    def _rotate(self):
        if self.enrollment_state != 'ready':
            return
        if self.rotation_state == 'generating':
            self.write({'rotation_state': 'review', 'management_message': _('Credential generation was interrupted. Review branch keys before enrolling again.')})
            return
        if self.rotation_state == 'review':
            return
        if self.rotation_state == 'idle':
            self.write({'rotation_state': 'generating', 'rotation_name': 'Branch connection %s %s' % (self.id, uuid4())})
            self.env.cr.commit()  # Durable marker before the independent remote transaction.
            try:
                new_key = self._json_call('res.users.apikeys', 'generate', {
                    'key': self._decrypt_secret(self.api_key_encrypted), 'scope': 'rpc',
                    'name': self.rotation_name,
                    'expiration_date': fields.Datetime.to_string(fields.Datetime.now() + timedelta(days=90))})
                if not isinstance(new_key, str) or not new_key:
                    raise UserError(_('The branch did not return a replacement credential.'))
                self.write({'pending_key_encrypted': self._encrypt_secret(new_key), 'rotation_state': 'pending'})
                self.env.cr.commit()
            except (UserError, AccessError):
                self.write({'rotation_state': 'review', 'management_message': _('Credential generation could not be confirmed. Review branch keys before enrolling again.')})
                return
        if self.rotation_state == 'pending':
            result = self._status(self._decrypt_secret(self.pending_key_encrypted))
            self.write({'previous_key_encrypted': self.api_key_encrypted,
                        'api_key_encrypted': self.pending_key_encrypted, 'pending_key_encrypted': False,
                        'expires_at': result['expires_at'], 'retire_at': fields.Datetime.now() + timedelta(hours=24),
                        'rotation_state': 'overlap', 'management_message': False})
            self.env.cr.commit()
        if self.rotation_state == 'overlap' and self.retire_at <= fields.Datetime.now():
            self._status()
            self._json_call('ab_branch_api', 'revoke_credential', {
                'store_serial': self.store_id.eplus_serial,
                'key': self._decrypt_secret(self.previous_key_encrypted)})
            self.write({'previous_key_encrypted': False, 'retire_at': False,
                        'rotation_state': 'idle', 'management_message': False})

    def job_manage_connection(self, operation='check'):
        self._require_admin()
        self.ensure_one()
        if not self.active:
            return
        slot = None
        for candidate in range(4):
            self.env.cr.execute('SELECT pg_try_advisory_lock(%s, %s)', (190902, candidate))
            if self.env.cr.fetchone()[0]:
                slot = candidate
                break
        if slot is None:
            return
        # Session lock spans the deliberate commits around remote key creation.
        self.env.cr.execute('SELECT pg_try_advisory_lock(%s, %s)', (190901, self.id))
        if not self.env.cr.fetchone()[0]:
            self.env.cr.execute('SELECT pg_advisory_unlock(%s, %s)', (190902, slot))
            return
        try:
            self.flush_recordset()
            self.invalidate_recordset()
            if not self.active:
                return
            if operation == 'check':
                self._check_connection()
            elif operation == 'rotate':
                try:
                    self._rotate()
                except (UserError, AccessError) as error:
                    self.management_message = str(error)
                self._update_alert()
            self.env.cr.commit()
        except Exception:
            self.env.cr.rollback()
            raise
        finally:
            self.env.cr.execute('SELECT pg_advisory_unlock(%s, %s)', (190901, self.id))
            self.env.cr.execute('SELECT pg_advisory_unlock(%s, %s)', (190902, slot))

    @api.model
    def _cron_connections(self, operation='check'):
        for record in self.search(fields.Domain('active', '=', True)):
            if operation == 'rotate' and not (record.rotation_state != 'idle' or
                    (record.expires_at and record.expires_at <= fields.Datetime.now() + timedelta(days=30))):
                continue
            record.with_delay(identity_key='branch-%s-%s' % (operation, record.id)).job_manage_connection(operation)
