# -*- coding: utf-8 -*-
from odoo import api, models, _

PARAM_STR = "?"


class AbSalesUiStoreStatus(models.TransientModel):
    _name = "ab_sales_ui_api"
    _inherit = ["ab_sales_ui_api", "ab_eplus_connect"]

    @api.model
    def pos_store_status(self, store_id=None):
        if not store_id:
            return False
        store = self.env["ab_store"].browse(int(store_id)).exists()
        if not store:
            return False
        target_ip = store.ip1
        replica_db = self.env["ab_replica_db"].sudo().get_current_from_config()
        if (
            replica_db
            and replica_db.default_sales_store_id
            and replica_db.default_sales_store_id.id == store.id
        ):
            target_ip = "192.168.1.150"
        if not target_ip:
            return False
        try:
            return self.is_port_open(target_ip)

        except Exception:
            return False
