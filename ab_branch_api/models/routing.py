"""Request-local SQL safety; endpoints come from the branch sales resolver."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
import logging

from odoo import api, models, _
from odoo.exceptions import AccessError, UserError
from odoo.addons.ab_eplus_connect.models.ab_eplus_connect import DB, USER
from odoo.addons.ab_eplus_connect.models.check_port_mssql import is_port_open

_logger = logging.getLogger(__name__)
_request = ContextVar('ab_branch_api_sql_request', default=None)
STORE_UNSET = object()
_STORE_OPTIONAL = {'get_capabilities', 'get_connection_status', 'search_products'}


@dataclass
class SqlRequest:
    database: str
    user_id: int
    store_id: int
    server: str | None = None
    pool: dict = field(default_factory=dict)
    health: dict = field(default_factory=dict)
    opened: dict = field(default_factory=dict)
    operation_locks: set = field(default_factory=set)
    posting_operation: object = None
    guarded: dict = field(default_factory=dict)
    deferred_commits: dict = field(default_factory=dict)


def current_request(model):
    scope = _request.get()
    if scope and (scope.database != model.env.cr.dbname or scope.user_id != model.env.uid):
        raise AccessError(model.env._('The API SQL request belongs to another database or user.'))
    return scope


def request_store(model, required=True):
    scope = current_request(model)
    if not scope:
        raise AccessError(model.env._('An authorized API SQL request is required.'))
    store = model.env['ab_store'].browse(scope.store_id)
    if required and not store:
        raise UserError(model.env._('Select a store or configure a default sales store for this operation.'))
    return store


def pin_server(model, store, server):
    scope = current_request(model)
    if not scope:
        return server
    store_id = store.id if isinstance(store, models.BaseModel) else int(store or 0)
    if not store_id or store_id != scope.store_id:
        raise AccessError(model.env._('The SQL store does not match the authorized API store.'))
    if scope.server is None:
        server = (server or '').strip()
        if not server:
            raise UserError(model.env._('The selected store has no E-Plus server address.'))
        if not is_port_open(server, port=1433):
            raise UserError(model.env._('The selected store E-Plus endpoint is unreachable.'))
        scope.server = server
    return scope.server


def selected_server(model, store=None):
    store = request_store(model) if store is None else store
    return model.env['ab_sales_header']._get_store_server(store)


def api_request(method):
    @wraps(method)
    def wrapped(self, db_serial, *args, store_eplus_serial=STORE_UNSET, **kwargs):
        replica = self._authenticate_replica(db_serial)
        store = self._resolve_store(replica, store_eplus_serial, required=method.__name__ not in _STORE_OPTIONAL)
        previous = current_request(self)
        if previous:
            if previous.store_id != store.id:
                raise AccessError(_('The SQL store does not match the authorized API store.'))
            return method(self, db_serial, *args, store_eplus_serial=store_eplus_serial, **kwargs)
        scope = SqlRequest(self.env.cr.dbname, self.env.uid, store.id)
        token = _request.set(scope)
        try:
            return method(self, db_serial, *args, store_eplus_serial=store_eplus_serial, **kwargs)
        finally:
            try:
                for connection in scope.guarded.values():
                    try:
                        connection.release()
                    except Exception:
                        _logger.warning('Could not release an API SQL operation lock', exc_info=True)
                for connection in scope.pool.values():
                    try:
                        connection.close()  # Rolls back any uncommitted SQL work.
                    except Exception:
                        _logger.warning('Could not close an API SQL connection', exc_info=True)
            finally:
                try:
                    for lock in scope.operation_locks:
                        # Session locks survive the posting workflow's commits.
                        # A failed transaction must be cleared before unlocking.
                        try:
                            self.env.cr.execute('SELECT pg_advisory_unlock(%s)', (lock,))
                        except Exception:
                            self.env.cr.rollback()
                            self.env.cr.execute('SELECT pg_advisory_unlock(%s)', (lock,))
                finally:
                    _request.reset(token)
    return wrapped


class ApiSqlConnector(models.AbstractModel):
    _inherit = 'ab_eplus_connect'

    @property
    def _connection_pool(self):
        scope = current_request(self)
        return scope.pool if scope else super()._connection_pool

    @property
    def _connection_health_cache(self):
        scope = current_request(self)
        return scope.health if scope else super()._connection_health_cache

    @contextmanager
    def connect_eplus(self, server=None, db=DB, user=USER, password=None, param_str='%s',
                      charset='CP1256', autocommit=True, port=1433, propagate_error=False,
                      validation_timeout=None, connect_timeout=None):
        scope = current_request(self)
        if scope:
            server = selected_server(self)
            port = 1433
        key = (server, db, user, param_str, charset, autocommit, port)
        if scope and key in scope.opened:
            # Reuse the same transaction without health-check reconnection.
            # A disconnected cursor must fail, never replay or start a new one.
            yield scope.opened[key]
            return
        cm = super().connect_eplus(server=server, db=db, user=user, password=password,
            param_str=param_str, charset=charset, autocommit=autocommit, port=port,
            propagate_error=propagate_error, validation_timeout=validation_timeout,
            connect_timeout=connect_timeout)
        if not scope:
            with cm as connection:
                yield connection
            return
        connection = cm.__enter__()
        connection._reconnect_cb = None
        scope.opened[key] = connection
        try:
            yield connection
        finally:
            # Legacy cleanup suppresses some exceptions. Preserve business/SQL
            # errors so the API can record an uncertain outcome after reservation.
            cm.__exit__(None, None, None)


class ApiSaleRouting(models.Model):
    _inherit = 'ab_sales_header'

    def _get_store_server(self, store):
        return pin_server(self, store, super()._get_store_server(store))


class ApiPosRouting(models.TransientModel):
    _inherit = 'ab_sales_pos_api'

    def _get_store_server(self, store):
        if current_request(self):
            return selected_server(self, store)
        return super()._get_store_server(store)


class ApiStatusRouting(models.TransientModel):
    _inherit = 'ab_sales_ui_api'

    @api.model
    def pos_store_status(self, store_id=None):
        if current_request(self):
            store = store_id if isinstance(store_id, models.BaseModel) else self.env['ab_store'].browse(int(store_id or 0))
            return bool(selected_server(self, store))
        return super().pos_store_status(store_id=store_id)
