from odoo.exceptions import UserError, ValidationError
from odoo.http import request, route

from odoo.addons.payment.controllers.post_processing import PaymentPostProcessing


class StorefrontPaymentPostProcessing(PaymentPostProcessing):
    @route()
    def poll_status(self, **kwargs):
        transaction = self._get_monitored_transaction()
        if transaction and transaction._ab_is_storefront_cash_on_delivery() and not transaction.is_post_processed:
            try:
                with request.env.cr.savepoint():
                    transaction._post_process()
            except (UserError, ValidationError) as error:
                transaction._set_error(str(error))
                return {
                    "provider_code": transaction.provider_code,
                    "state": transaction.state,
                    "landing_route": "/payment/status",
                }
        return super().poll_status(**kwargs)

    @route()
    def display_status(self, **kwargs):
        transaction = self._get_monitored_transaction()
        if transaction and transaction._ab_is_storefront_cash_on_delivery() and not transaction.is_post_processed:
            try:
                with request.env.cr.savepoint():
                    transaction._post_process()
            except (UserError, ValidationError) as error:
                transaction._set_error(str(error))
                return request.render("payment.payment_status", {
                    "tx": transaction,
                    "ab_cod_error": str(error),
                })
        return super().display_status(**kwargs)
