from contextlib import contextmanager

from odoo import models, _
from odoo.exceptions import UserError


class AbSalesExternalConnector(models.AbstractModel):
    _name = 'ab_sales_external_connector'
    _description = 'Sales External Connector'

    _connection_pool = {}
    _connection_health_cache = {}

    def _legacy_connector(self):
        model_name = 'ab_sales_eplus_legacy.connector'
        if model_name not in self.env.registry:
            raise UserError(_(
                'Legacy E-Plus operations are unavailable. Install the optional Sales E-Plus Legacy module.'
            ))
        return self.env[model_name].with_context(self.env.context)

    @contextmanager
    def connect_eplus(self, **kwargs):
        with self._legacy_connector().connect_eplus(**kwargs) as connection:
            yield connection

    def is_connection_valid(self, connection, **kwargs):
        return self._legacy_connector().is_connection_valid(connection, **kwargs)

    def is_port_open(self, host, port=1433, timeout=2):
        if 'ab_sales_eplus_legacy.connector' not in self.env.registry:
            return False
        return self._legacy_connector().is_port_open(host, port=port, timeout=timeout)

    def _clone_external_connection(self, connection, factory=None):
        return self._legacy_connector().clone_connection(connection, factory=factory)
