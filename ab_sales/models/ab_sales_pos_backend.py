"""Request-local SQL safety; endpoints come from the branch sales resolver."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
import logging
import hashlib

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.addons.ab_eplus_connect.models.ab_eplus_connect import DB, USER
from odoo.addons.ab_eplus_connect.models.check_port_mssql import is_port_open

_logger = logging.getLogger(__name__)
_request = ContextVar('ab_sales_backend_request', default=None)


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
    connection_factories: dict = field(default_factory=dict)


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
    store.ensure_one()
    store.check_access('read')
    if current_request(model) and request_store(model) != store:
        raise AccessError(model.env._('The SQL store does not match the authorized API store.'))
    return model.env['ab_sales_header']._get_store_server(store)


class SalesBackendConnector(models.AbstractModel):
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
        key = (server, db, user, param_str, charset, autocommit, port,
               self.env.context.get("_eplus_pos_balance_read") is True)
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
        # Keep the established connector factory for an isolated native sale
        # session, while disabling replay on this API read/pool connection.
        scope.connection_factories.setdefault(id(connection), connection._reconnect_cb)
        connection._reconnect_cb = None
        scope.opened[key] = connection
        try:
            yield connection
        finally:
            # Legacy cleanup suppresses some exceptions. Preserve business/SQL
            # errors so the API can record an uncertain outcome after reservation.
            cm.__exit__(None, None, None)


class SalesPosBackend(models.TransientModel):
    _inherit = 'ab_sales_pos_api'

    @contextmanager
    def _backend_request(self, store):
        """Pin one authorized branch; own read sessions, never post on exit.

        No ORM changes. Exceptions propagate; all sessions and reference locks
        are released on success or failure. Nested scopes cannot change branch.
        """
        previous = current_request(self)
        if previous:
            if previous.store_id != store.id:
                raise AccessError(_('The SQL store does not match the authorized API store.'))
            yield
            return
        scope = SqlRequest(self.env.cr.dbname, self.env.uid, store.id)
        token = _request.set(scope)
        try:
            yield
        finally:
            try:
                for connection in scope.pool.values():
                    try:
                        connection.close()
                    except Exception:
                        _logger.warning('Could not close a backend connection', exc_info=True)
                for lock in scope.operation_locks:
                    try:
                        self.env.cr.execute('SELECT pg_advisory_unlock(%s)', (lock,))
                    except Exception:
                        self.env.cr.rollback()
                        self.env.cr.execute('SELECT pg_advisory_unlock(%s)', (lock,))
            finally:
                _request.reset(token)

    def _backend_lock_customer(self, serial):
        """Serialize customer imports across commits; scope exit releases lock."""
        scope = current_request(self)
        if not scope:
            raise AccessError(_('An authorized API SQL request is required.'))
        lock = int.from_bytes(hashlib.sha256(
            ('ab_branch_api:customer-reference:%s' % serial).encode()).digest()[:8], 'big', signed=True)
        if lock not in scope.operation_locks:
            self.env.cr.execute('SELECT pg_try_advisory_lock(%s)', (lock,))
            if not self.env.cr.fetchone()[0]:
                raise UserError(_('The branch is still processing this request. Retry shortly using the same bill.'))
            scope.operation_locks.add(lock)
            self.env.cr.commit()
            self.env.invalidate_all()

    def _backend_customer_values(self, store, reference=None, phone=None):
        """Read one branch customer; return values or False, without ORM writes."""
        with self.connect_eplus(server=selected_server(self, store), param_str='?',
                                charset='CP1256', autocommit=False) as connection:
            with connection.cursor() as cursor:
                row = (self._bconnect_customer_by_id(cursor, reference) if reference is not None
                       else self._bconnect_customer_by_phone(cursor, phone))
        if not row or (reference is not None and int(row.get('eplus_serial') or 0) != reference):
            return False
        return self._customer_vals_from_bconnect(row, store)

    def _backend_lookup_customer(self, store, phone):
        """Read branch customer and import/update the local customer; caller commits."""
        phone = self._normalize_phone(phone)
        if not phone:
            raise UserError(_('Phone is required.'))
        values = self._backend_customer_values(store, phone=phone)
        if not values:
            return {'status': 'not_found'}
        customer = self._upsert_customer_from_bconnect(values)
        return {'status': 'found', 'customer': self._customer_payload(customer)}

    def _backend_create_customer(self, store, **values):
        """Delegate customer creation; native workflow owns external transaction."""
        return self.pos_customer_create(store_id=store.id, **values)

    def _get_store_server(self, store):
        if current_request(self):
            return selected_server(self, store)
        return super()._get_store_server(store)


    def _backend_import_customer(self, values):
        store = request_store(self)
        serial = values.get('eplus_serial')
        if type(serial) is not int or serial <= 0:
            raise UserError(self.env._('A valid customer E-Plus reference is required.'))
        self._backend_lock_customer(serial)
        if not values.get('active') or not (values.get('name') or '').strip():
            raise UserError(self.env._('The branch customer is inactive or incomplete. Review the customer before using it.'))
        Customer = self.env['ab_customer'].with_context(active_test=False)
        matches = Customer.sudo().search(fields.Domain('eplus_serial', '=', serial), limit=2)
        if len(matches) > 1:
            raise UserError(self.env._('The customer reference is duplicated on this branch. Review the customer records before retrying.'))
        customer = Customer.browse(matches.ids)
        allowed = {'code', 'name', 'address', 'mobile_phone', 'work_phone', 'last_update_date',
                   'eplus_serial', 'eplus_create_date'}
        values = {key: value for key, value in values.items() if key in allowed}
        if customer:
            customer.check_access('read')
            if not customer.active:
                raise UserError(self.env._('The customer is archived on this branch. Review the customer before using it.'))
            customer.sudo().write(values)
        else:
            Customer.check_access('create')
            customer = Customer.create(dict(values, default_store_id=store.id, active=True))
            customer.check_access('read')
            _logger.info('Branch API imported customer E-Plus reference %s for store %s by user %s',
                         serial, store.id, self.env.uid)
        return customer

    def _upsert_customer_from_bconnect(self, vals):
        if current_request(self):
            return self._backend_import_customer(vals)
        return super()._upsert_customer_from_bconnect(vals)


class SalesBackendStatusRouting(models.TransientModel):
    _inherit = 'ab_sales_ui_api'

    @api.model
    def pos_store_status(self, store_id=None):
        if current_request(self):
            store = store_id if isinstance(store_id, models.BaseModel) else self.env['ab_store'].browse(int(store_id or 0))
            return bool(selected_server(self, store))
        return super().pos_store_status(store_id=store_id)
