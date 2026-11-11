from odoo import api, models


class AbSalesCashierApi(models.TransientModel):
    _name = "ab_sales_cashier_api"
    _inherit = ["ab_sales_cashier_api", "ab_sales_prevent.access.mixin"]

    @api.model
    def _blocked_super(self, method_name, *args, **kwargs):
        self._raise_sales_prevented()
        return getattr(super(AbSalesCashierApi, self), method_name)(*args, **kwargs)

    @api.model
    def get_cashier_bootstrap(self, session_token=False):
        return self._blocked_super("get_cashier_bootstrap", session_token=session_token)

    @api.model
    def cashier_pin_login(self, *args, **kwargs):
        return self._blocked_super("cashier_pin_login", *args, **kwargs)

    @api.model
    def cashier_change_store(self, session_token, store_id):
        return self._blocked_super("cashier_change_store", session_token, store_id)

    @api.model
    def cashier_logout(self, session_token=False):
        return self._blocked_super("cashier_logout", session_token=session_token)

    @api.model
    def get_pending_invoices(self, limit=300, store_id=None, session_token=False):
        return self._blocked_super(
            "get_pending_invoices",
            limit=limit,
            store_id=store_id,
            session_token=session_token,
        )

    @api.model
    def get_invoice_snapshot(self, invoice_id, store_id=None, document_type="sale", session_token=False):
        return self._blocked_super(
            "get_invoice_snapshot",
            invoice_id,
            store_id=store_id,
            document_type=document_type,
            session_token=session_token,
        )

    @api.model
    def get_invoice_print_ref(self, invoice_id, store_id=None, document_type="sale", session_token=False):
        return self._blocked_super(
            "get_invoice_print_ref",
            invoice_id,
            store_id=store_id,
            document_type=document_type,
            session_token=session_token,
        )

    @api.model
    def get_store_wallets(self, store_id=None, session_token=False):
        return self._blocked_super(
            "get_store_wallets",
            store_id=store_id,
            session_token=session_token,
        )

    @api.model
    def save_pending_invoice(
        self,
        invoice_id,
        request_id=None,
        store_id=None,
        wallet_id=None,
        document_type="sale",
        session_token=False,
    ):
        return self._blocked_super(
            "save_pending_invoice",
            invoice_id,
            request_id=request_id,
            store_id=store_id,
            wallet_id=wallet_id,
            document_type=document_type,
            session_token=session_token,
        )


class AbSalesCashierCloseWizard(models.TransientModel):
    _name = "ab_sales_cashier_close_wizard"
    _inherit = ["ab_sales_cashier_close_wizard", "ab_sales_prevent.access.mixin"]

    @api.model
    def default_get(self, fields_list):
        self._raise_sales_prevented()
        return super().default_get(fields_list)

    def action_confirm_close(self):
        self._raise_sales_prevented()
        return super().action_confirm_close()


class AbSalesCashierCloseWizardLine(models.TransientModel):
    _name = "ab_sales_cashier_close_wizard_line"
    _inherit = ["ab_sales_cashier_close_wizard_line", "ab_sales_prevent.access.mixin"]
