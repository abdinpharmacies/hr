from odoo import api, models


class AbSalesHeader(models.Model):
    _name = "ab_sales_header"
    _inherit = ["ab_sales_header", "ab_sales_prevent.access.mixin"]

    def action_open_add_products(self):
        self._raise_sales_prevented()
        return super().action_open_add_products()

    @api.model
    def get_sales_dashboard_payload(self):
        self._raise_sales_prevented()
        return super().get_sales_dashboard_payload()

    def action_open_form_dialog(self):
        self._raise_sales_prevented()
        return super().action_open_form_dialog()

    def action_open_sales_return(self):
        self._raise_sales_prevented()
        return super().action_open_sales_return()

    @api.model
    def action_fix_bill_customer_data(self, domain=None, limit=None):
        self._raise_sales_prevented()
        return super().action_fix_bill_customer_data(domain=domain, limit=limit)

    def action_push_to_eplus(self):
        self._raise_sales_prevented()
        return super().action_push_to_eplus()

    def action_submit(self):
        self._raise_sales_prevented()
        return super().action_submit()

    @api.model
    def cron_update_status_from_store(self):
        self._raise_sales_prevented()
        return super().cron_update_status_from_store()


class AbSalesLine(models.Model):
    _name = "ab_sales_line"
    _inherit = ["ab_sales_line", "ab_sales_prevent.access.mixin"]

    def btn_get_product_balance(self):
        self._raise_sales_prevented()
        return super().btn_get_product_balance()


class AbSalesReturnHeader(models.Model):
    _name = "ab_sales_return_header"
    _inherit = ["ab_sales_return_header", "ab_sales_prevent.access.mixin"]

    def action_clear_lines(self):
        self._raise_sales_prevented()
        return super().action_clear_lines()

    def action_total_return_invoice(self):
        self._raise_sales_prevented()
        return super().action_total_return_invoice()

    def action_set_pending(self):
        self._raise_sales_prevented()
        return super().action_set_pending()

    def action_load_lines(self):
        self._raise_sales_prevented()
        return super().action_load_lines()

    def action_push_to_eplus_return(self):
        self._raise_sales_prevented()
        return super().action_push_to_eplus_return()


class AbSalesReturnLine(models.Model):
    _name = "ab_sales_return_line"
    _inherit = ["ab_sales_return_line", "ab_sales_prevent.access.mixin"]


class AbSalesPosDraftCache(models.Model):
    _name = "ab_sales_pos_draft_cache"
    _inherit = ["ab_sales_pos_draft_cache", "ab_sales_prevent.access.mixin"]


class AbSalesPosSettings(models.Model):
    _name = "ab_sales_pos_settings"
    _inherit = ["ab_sales_pos_settings", "ab_sales_prevent.access.mixin"]


class AbSalesPosReplicationTurn(models.Model):
    _name = "ab_sales_pos_replication_turn"
    _inherit = ["ab_sales_pos_replication_turn", "ab_sales_prevent.access.mixin"]
