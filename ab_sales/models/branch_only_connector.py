"""Block connector entry points before health checks, credentials, or pool access."""
from contextlib import contextmanager
from odoo import models
from .access_policy import require_sql


class BranchOnlyConnector(models.AbstractModel):
    _inherit = 'ab_eplus_connect'

    @contextmanager
    def connect_eplus(self, *args, **kwargs):
        require_sql()
        with super().connect_eplus(*args, **kwargs) as connection:
            yield connection

    def decrypt_password(self):
        require_sql()
        return super().decrypt_password()

    def _probe_connection(self, *args, **kwargs):
        require_sql()
        return super()._probe_connection(*args, **kwargs)

    def is_connection_valid(self, *args, **kwargs):
        require_sql()
        return super().is_connection_valid(*args, **kwargs)

    def _validate_connection_now(self, *args, **kwargs):
        require_sql()
        return super()._validate_connection_now(*args, **kwargs)

    def is_port_open(self, *args, **kwargs):
        require_sql()
        return super().is_port_open(*args, **kwargs)
