# -*- coding: utf-8 -*-

from contextlib import contextmanager
import socket
from urllib.parse import urlparse
from xmlrpc import client

from cryptography.fernet import Fernet, InvalidToken

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import config


class AbSalesBranchRpcConfig(models.Model):
    _name = "ab_sales_branch_rpc_config"
    _description = "Sales Branch RPC Configuration"
    _order = "store_id, id"

    name = fields.Char(required=True, default=lambda self: _("New Branch RPC Configuration"))
    active = fields.Boolean(default=True)
    store_id = fields.Many2one("ab_store", required=True, ondelete="restrict", index=True)
    store_eplus_serial = fields.Integer(related="store_id.eplus_serial", readonly=True)
    store_code = fields.Char(related="store_id.code", readonly=True)
    rpc_url = fields.Char(string="Branch Odoo URL", required=True)
    rpc_db = fields.Char(string="Branch Database", required=True)
    rpc_user = fields.Char(string="RPC User", required=True)
    rpc_password = fields.Char(
        string="RPC Password/API Key",
        compute="_compute_rpc_password",
        inverse="_inverse_rpc_password",
    )
    rpc_password_encrypted = fields.Char(string="Encrypted RPC Password", readonly=True, copy=False)
    rpc_sync_key = fields.Char(
        string="RPC Sync Key",
        compute="_compute_rpc_sync_key",
        inverse="_inverse_rpc_sync_key",
    )
    rpc_sync_key_encrypted = fields.Char(string="Encrypted RPC Sync Key", readonly=True, copy=False)
    connection_timeout = fields.Integer(default=15)
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

    @api.depends("rpc_password_encrypted")
    def _compute_rpc_password(self):
        for record in self:
            record.rpc_password = False

    def _inverse_rpc_password(self):
        for record in self:
            if record.rpc_password:
                record.rpc_password_encrypted = record._encrypt_secret(record.rpc_password)

    @api.depends("rpc_sync_key_encrypted")
    def _compute_rpc_sync_key(self):
        for record in self:
            record.rpc_sync_key = False

    def _inverse_rpc_sync_key(self):
        for record in self:
            if record.rpc_sync_key:
                record.rpc_sync_key_encrypted = record._encrypt_secret(record.rpc_sync_key)

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._normalize_vals(vals) for vals in vals_list]
        records = super().create(vals_list)
        records._sync_display_name()
        return records

    def write(self, vals):
        vals = self._normalize_vals(dict(vals or {}))
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

    @api.constrains("rpc_url")
    def _check_rpc_url(self):
        for record in self:
            parsed = urlparse((record.rpc_url or "").strip())
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                raise ValidationError(_("Branch Odoo URL must be a valid HTTP or HTTPS URL."))

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

    def _get_rpc_password(self):
        self.ensure_one()
        password = self._decrypt_secret(self.rpc_password_encrypted)
        if not password:
            raise UserError(_("RPC password/API key is required."))
        return password

    def _get_rpc_sync_key(self):
        self.ensure_one()
        return self._decrypt_secret(self.rpc_sync_key_encrypted)

    def _rpc_headers(self):
        self.ensure_one()
        sync_key = self._get_rpc_sync_key()
        return [("x-sync-key", sync_key)] if sync_key else []

    @contextmanager
    def _socket_timeout(self):
        self.ensure_one()
        old_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(int(self.connection_timeout or 15))
        try:
            yield
        finally:
            socket.setdefaulttimeout(old_timeout)

    def _rpc_common_proxy(self):
        self.ensure_one()
        return client.ServerProxy(
            "%s/xmlrpc/2/common" % self.rpc_url,
            allow_none=True,
            headers=self._rpc_headers(),
        )

    def _rpc_object_proxy(self):
        self.ensure_one()
        return client.ServerProxy(
            "%s/xmlrpc/2/object" % self.rpc_url,
            allow_none=True,
            headers=self._rpc_headers(),
        )

    def _authenticate(self):
        self.ensure_one()
        password = self._get_rpc_password()
        with self._socket_timeout():
            uid = self._rpc_common_proxy().authenticate(self.rpc_db, self.rpc_user, password, {})
        if not uid:
            raise UserError(_("Authentication failed for the configured branch Odoo connection."))
        return int(uid), password

    def _execute_kw(self, model_name, method, args=None, kwargs=None):
        self.ensure_one()
        uid, password = self._authenticate()
        with self._socket_timeout():
            return self._rpc_object_proxy().execute_kw(
                self.rpc_db,
                uid,
                password,
                model_name,
                method,
                args or [],
                kwargs or {},
            )

    def _remote_store_domain(self):
        self.ensure_one()
        if self.store_id.eplus_serial:
            return [("eplus_serial", "=", int(self.store_id.eplus_serial))]
        if self.store_id.code:
            return [("code", "=", self.store_id.code)]
        raise UserError(_("Selected store must have an E-Plus serial or code before testing RPC."))

    def action_test_connection(self):
        for record in self:
            try:
                uid, password = record._authenticate()
                with record._socket_timeout():
                    object_proxy = record._rpc_object_proxy()
                    object_proxy.execute_kw(
                        record.rpc_db,
                        uid,
                        password,
                        "res.users",
                        "check_access_rights",
                        ["read"],
                        {"raise_exception": True},
                    )
                    stores = object_proxy.execute_kw(
                        record.rpc_db,
                        uid,
                        password,
                        "ab_store",
                        "search_read",
                        [record._remote_store_domain()],
                        {"fields": ["id", "name", "code", "eplus_serial"], "limit": 1},
                    )
                if not stores:
                    raise UserError(_("Connection works, but matching branch store was not found on remote Odoo."))
                remote_store = stores[0]
                record.write({
                    "last_test_state": "success",
                    "last_test_message": _("Connection succeeded. Remote store matched."),
                    "last_tested_at": fields.Datetime.now(),
                    "remote_store_id": int(remote_store.get("id") or 0),
                    "remote_store_name": remote_store.get("name") or "",
                })
            except Exception as error:
                record.write({
                    "last_test_state": "error",
                    "last_test_message": str(error),
                    "last_tested_at": fields.Datetime.now(),
                    "remote_store_id": 0,
                    "remote_store_name": "",
                })
                raise
        return True
