# -*- coding: utf-8 -*-

from odoo import models


class AbSalesUiApiSettingsInherit(models.TransientModel):
    _inherit = "ab_sales_ui_api"

    _POS_UI_SETTINGS_DEFAULTS = {
        "productHasBalanceOnly": True,
        "productHasPosBalanceOnly": True,
        "productColumnPercent": 30.0,
        "enableProductSearchKeyboardMapping": True,
        "enableAbMany2oneKeyboardMapping": True,
    }
