import logging
from odoo import models
from odoo.tools import config
from .ab_wan_get import wan_get_ip

_logger = logging.getLogger(__name__)


class WanUpdateEPlus(models.AbstractModel):
    _name = 'ab_wan_update_eplus'
    _description = 'ab_wan_update_eplus'
    _inherit = ['ab_eplus_connect']

    def update_eplus_wan_main_and_store_dbs(self):
        wan = wan_get_ip()
        repl_db = int(config.get('repl_db') or 0)
        eplus_store = self.env['ab_store'].browse(repl_db)
        eplus_sto_id = eplus_store.eplus_serial
        eplus_sto_internal_ip = eplus_store.ip2
        self._update_main_db(eplus_sto_id, wan)
        self._update_store_db(eplus_sto_id, wan, eplus_sto_internal_ip)

    def _update_main_db(self, eplus_sto_id, wan, ):
        try:
            with self.connect_eplus() as conn:
                with conn.cursor() as cr:
                    cr.execute("""
                    UPDATE store set sto_ip1=%(wan)s 
                    WHERE sto_id=%(eplus_sto_id)s and sto_ip1 != %(wan)s

                    """, {'wan': wan, 'eplus_sto_id': eplus_sto_id})
        except Exception as ex:
            _logger.error(f"### Error in updating sto_ip1 in MainDB {repr(ex)}")

    def _update_store_db(self, eplus_sto_id, wan, eplus_sto_internal_ip):
        try:
            with self.connect_eplus(server=eplus_sto_internal_ip) as conn:
                with conn.cursor() as cr:
                    cr.execute("""
                    UPDATE store set sto_ip1=%(wan)s
                    WHERE sto_id=%(eplus_sto_id)s and sto_ip1 != %(wan)s
                    """, {'wan': wan, 'eplus_sto_id': eplus_sto_id})
        except Exception as ex:
            _logger.error(f"### Error in updating sto_ip1 in StoreDB {repr(ex)}")
