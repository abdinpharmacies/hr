"""Store-scoped routing without changing the legacy sales or cashier addons."""
from contextvars import ContextVar
import logging

from odoo import api, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)
_status_server = ContextVar('ab_sales_routing_status_server', default=None)


def _store_server(model, store):
    if not isinstance(store, models.BaseModel):
        store = model.env['ab_store'].browse(int(store or 0))
    store = store.exists()
    if not store:
        raise UserError(model.env._('Store is required.'))
    store.ensure_one()
    server = (store.ip1 or '').strip()
    if not server:
        raise UserError(model.env._('No E-Plus server address is configured for store %s.', store.display_name))
    return server


def _raise_connection_error(record, error):
    # Legacy sales wraps the original connector exception in a generic UserError.
    # Recover that cause, but never expose a raw database-driver exception.
    cause = error.__cause__ or error.__context__ or error
    if isinstance(error, AccessError):
        raise error
    if isinstance(cause, UserError):
        raise cause from None
    _logger.warning('E-Plus connection failed for store %s (%s)', record.store_id.id, type(cause).__name__)
    raise UserError(record.env._(
        'Could not connect to E-Plus for store %s. Check the store address and database connection settings.',
        record.store_id.display_name,
    )) from None


class SalesHeaderRouting(models.Model):
    _inherit = 'ab_sales_header'

    def _get_store_server(self, store):
        server = _store_server(self, store)
        super()._get_store_server(store)
        return server

    def get_connection(self):
        try:
            return super().get_connection()
        except Exception as error:
            _raise_connection_error(self, error)


class SalesReturnRouting(models.Model):
    _inherit = 'ab_sales_return_header'

    def _get_store_server(self, store):
        server = _store_server(self, store)
        super()._get_store_server(store)
        return server

    def get_connection(self):
        try:
            return super().get_connection()
        except Exception as error:
            _raise_connection_error(self, error)


class SalesPosRouting(models.TransientModel):
    _inherit = 'ab_sales_pos_api'

    def _get_store_server(self, store):
        server = _store_server(self, store)
        # The effective legacy method expects a recordset.
        record = store if isinstance(store, models.BaseModel) else self.env['ab_store'].browse(int(store))
        super()._get_store_server(record)
        return server


class SalesInventoryRouting(models.Model):
    _inherit = 'ab_sales_inventory'

    @api.model
    def _get_default_sales_store_direct_server(self, store):
        server = _store_server(self, store)
        super()._get_default_sales_store_direct_server(store)
        return server


class SalesCashierRouting(models.TransientModel):
    _inherit = 'ab_sales_cashier_api'

    @api.model
    def _get_store_server(self, store):
        server = _store_server(self, store)
        super()._get_store_server(store)
        return server


class SalesStatusRouting(models.TransientModel):
    _inherit = 'ab_sales_ui_api'

    @api.model
    def pos_store_status(self, store_id=None):
        # The callcenter adapter checks its authenticated branch API, not SQL.
        if 'ab_sales_branch_client' in self.env and self.env['ab_sales_branch_client']._is_callcenter():
            return super().pos_store_status(store_id=store_id)
        if not store_id:
            return super().pos_store_status(store_id=store_id)
        server = _store_server(self, store_id)
        token = _status_server.set(server)
        try:
            # Keep inherited status behavior; replace only its legacy probe target.
            return super().pos_store_status(store_id=store_id)
        finally:
            _status_server.reset(token)

    def is_port_open(self, host, port=1433, timeout=2):
        return super().is_port_open(_status_server.get() or host, port=port, timeout=timeout)
