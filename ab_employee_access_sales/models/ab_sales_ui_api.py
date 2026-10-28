from odoo import api, models


class AbSalesUiApi(models.TransientModel):
    _inherit = "ab_sales_ui_api"

    @api.model
    def _require_pos_ui_session(self, pos_hr_session_token=None, store_id=False):
        return self.env["ab_sales_pos_api"]._require_pos_operation_session(
            pos_hr_session_token=pos_hr_session_token,
            store_id=store_id,
        )

    @api.model
    def get_sales_store_settings(self):
        scope = self.env["ab_employee_access_sales_pos_api"]._resolve_pos_store_scope()
        default_store = scope["default_store"]
        return {
            "stores": scope["stores"],
            "visible_store_ids": scope["visible_store_ids"],
            "available_store_ids": scope["available_store_ids"],
            "allowed_store_codes": scope["available_stores"].mapped("code"),
            "default_store_code": default_store.code if default_store else "",
            "empty_reason": scope["empty_reason"],
            "empty_message": scope["empty_message"],
        }

    @api.model
    def search_products(
        self,
        query="",
        limit=60,
        has_balance=True,
        has_pos_balance=False,
        header_id=None,
        store_id=None,
        customer_phone=None,
        item_type="all",
        min_price=None,
        max_price=None,
        pos_hr_session_token=None,
    ):
        session = self._require_pos_ui_session(pos_hr_session_token, store_id=store_id)
        return super(AbSalesUiApi, self.with_context(ab_pos_session_token=session.session_token)).search_products(
            query=query,
            limit=limit,
            has_balance=has_balance,
            has_pos_balance=has_pos_balance,
            header_id=header_id,
            store_id=store_id,
            customer_phone=customer_phone,
            item_type=item_type,
            min_price=min_price,
            max_price=max_price,
        )

    @api.model
    def get_products_promo_status(self, product_ids, store_id=None, pos_hr_session_token=None):
        session = self._require_pos_ui_session(pos_hr_session_token, store_id=store_id)
        return super(AbSalesUiApi, self.with_context(ab_pos_session_token=session.session_token)).get_products_promo_status(
            product_ids,
            store_id=store_id,
        )

    @api.model
    def pos_customer_insights(
        self,
        header_id=None,
        store_id=None,
        customer_phone=None,
        customer_name=None,
        pos_hr_session_token=None,
    ):
        session = self._require_pos_ui_session(pos_hr_session_token, store_id=store_id)
        return super(AbSalesUiApi, self.with_context(ab_pos_session_token=session.session_token)).pos_customer_insights(
            header_id=header_id,
            store_id=store_id,
            customer_phone=customer_phone,
            customer_name=customer_name,
        )

    @api.model
    def pos_customer_invoices(
        self,
        header_id=None,
        store_id=None,
        customer_phone=None,
        limit=20,
        pos_hr_session_token=None,
    ):
        session = self._require_pos_ui_session(pos_hr_session_token, store_id=store_id)
        return super(AbSalesUiApi, self.with_context(ab_pos_session_token=session.session_token)).pos_customer_invoices(
            header_id=header_id,
            store_id=store_id,
            customer_phone=customer_phone,
            limit=limit,
        )

    @api.model
    def pos_store_status(self, store_id=None, pos_hr_session_token=None):
        session = self._require_pos_ui_session(pos_hr_session_token, store_id=store_id)
        return super(AbSalesUiApi, self.with_context(ab_pos_session_token=session.session_token)).pos_store_status(
            store_id=store_id,
        )
