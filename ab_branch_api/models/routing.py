"""Authenticated transport scope; backend session lifetime belongs to ab_sales."""
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
from odoo import _
from odoo.exceptions import AccessError, UserError

_request = ContextVar('ab_branch_api_request', default=None)
STORE_UNSET = object()
_STORE_OPTIONAL = {'get_capabilities', 'get_connection_status', 'search_products'}

@dataclass
class ApiRequest:
    database: str
    user_id: int
    store_id: int
    operation_locks: set = field(default_factory=set)

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
        scope = ApiRequest(self.env.cr.dbname, self.env.uid, store.id)
        token = _request.set(scope)
        try:
            with self.env['ab_sales_pos_api']._backend_request(store):
                return method(self, db_serial, *args, store_eplus_serial=store_eplus_serial, **kwargs)
        finally:
            try:
                for lock in scope.operation_locks:
                    try:
                        self.env.cr.execute('SELECT pg_advisory_unlock(%s)', (lock,))
                    except Exception:
                        self.env.cr.rollback()
                        self.env.cr.execute('SELECT pg_advisory_unlock(%s)', (lock,))
            finally:
                _request.reset(token)
    return wrapped
