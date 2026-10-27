from odoo import models
from odoo.exceptions import ValidationError


class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"

    def _ab_is_storefront_cash_on_delivery(self):
        self.ensure_one()
        return (
            self.provider_code == "custom"
            and self.provider_id.custom_mode == "cash_on_delivery"
            and self.payment_method_code == "cash_on_delivery"
            and self.state == "pending"
            and self.operation == "online_redirect"
            and bool(self.sale_order_ids.filtered("website_id"))
        )

    def _ab_confirm_storefront_cash_on_delivery(self):
        self.ensure_one()
        if not self._ab_is_storefront_cash_on_delivery():
            return
        if len(self.sale_order_ids) != 1:
            raise ValidationError(self.env._("This checkout is no longer valid. Please review your cart."))
        order = self.sale_order_ids
        if order.state in ("draft", "sent"):
            order._ab_lock_cart()
        submission = order.ab_checkout_submission_id
        if (
            not submission
            or submission.kind != "checkout"
            or submission.transaction_id != self
            or submission.order_id != order
            or submission.website_id != order.website_id
            or submission.company_id != order.company_id
            or order.website_id.company_id != order.company_id
            or not order.warehouse_id
            or order.warehouse_id.company_id != order.company_id
            or self.company_id != order.company_id
            or self.provider_id.company_id != order.company_id
            or self.partner_id.commercial_partner_id != order.partner_id.commercial_partner_id
            or self.currency_id != order.currency_id
            or self.currency_id.compare_amounts(self.amount, order.amount_total)
            or order.state not in ("draft", "sent", "sale", "done")
        ):
            raise ValidationError(self.env._("This checkout is no longer valid. Please review your cart."))
        if order.state in ("draft", "sent"):
            order.with_company(order.company_id).with_context(send_email=True).action_confirm()

    def _post_process(self):
        for transaction in self:
            transaction._ab_confirm_storefront_cash_on_delivery()
        return super()._post_process()
