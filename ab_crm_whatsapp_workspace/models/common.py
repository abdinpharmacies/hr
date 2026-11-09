from contextlib import contextmanager
from contextvars import ContextVar

from odoo.addons.ab_crm_core.models.core import _INTERNAL
from odoo.addons.ab_crm_messaging.models.messaging import _MUTATION

_BRIDGE = ContextVar('ab_crm_whatsapp_bridge', default=False)
_DASHBOARD = ContextVar('ab_crm_whatsapp_dashboard', default=False)


@contextmanager
def bridge_mutation():
    tokens = [(flag, flag.set(True)) for flag in (_BRIDGE, _INTERNAL, _MUTATION)]
    try:
        yield
    finally:
        for flag, token in reversed(tokens):
            flag.reset(token)
