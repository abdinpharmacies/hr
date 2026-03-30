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
        if not store or not store.ip1:
            return False
        try:
            return self.is_port_open(store.ip1)

        except Exception:
            return False
