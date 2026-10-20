from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.http import request, route

from odoo.addons.website_sale.controllers.payment import PaymentPortal

from .catalog import AbStorefrontCatalog
from .submission_security import submission_owner


def checkout_submission(order, renew_failed=False):
    order._ab_lock_cart()
    submission = order.ab_checkout_submission_id
    owner = submission_owner()
    if not submission or (renew_failed and submission.transaction_id.state in ("cancel", "error")) or (
        not submission.transaction_id
        and (submission.owner_hash != owner or submission.expires_at <= fields.Datetime.now())
    ):
        submission = request.env["ab_storefront_submission"]._issue(
            "checkout", request.website, owner, order,
        )
        order.ab_checkout_submission_id = submission
    return submission


class StorefrontCheckoutPage(AbStorefrontCatalog):
    @route("/shop/ab/cart-hold", type="http", auth="public", website=True, methods=["GET"], sitemap=False)
    def cart_hold_status(self):
        cart = request.cart
        deadline = False
        if cart and cart.website_id == request.website and cart.company_id == request.website.company_id:
            deadline = cart.ab_cart_hold_expires_at
        return request.make_json_response({
            "expires_at": deadline.isoformat() + "Z" if deadline else None,
            "server_time": fields.Datetime.now().isoformat() + "Z",
        }, headers=[("Cache-Control", "private, no-store")])

    def _get_shop_payment_values(self, order, **kwargs):
        values = super()._get_shop_payment_values(order, **kwargs)
        submission = checkout_submission(order, renew_failed=True)
        values["transaction_route"] = f"/shop/ab/transaction/{order.id}/{submission.key}"
        return values


class StorefrontPaymentPortal(PaymentPortal):
    @route("/shop/ab/transaction/<int:order_id>/<string:idempotency_key>",
           type="jsonrpc", auth="public", website=True, methods=["POST"])
    def storefront_payment_transaction(self, order_id, idempotency_key, access_token, **kwargs):
        return self.shop_payment_transaction(
            order_id, access_token, idempotency_key=idempotency_key, **kwargs,
        )

    @route(type="jsonrpc", auth="public", website=True)
    def shop_payment_transaction(self, order_id, access_token, **kwargs):
        order = self._document_check_access("sale.order", order_id, access_token)
        if order.website_id != request.website or order.company_id != request.website.company_id:
            raise AccessError(request.env._("This order does not belong to this website."))
        if request.env.user._is_public():
            owned_ids = {request.session.get("sale_order_id"), request.session.get("sale_last_order_id")}
            if order.id not in owned_ids:
                raise AccessError(request.env._("This order does not belong to your session."))
        elif order.partner_id.commercial_partner_id != request.env.user.partner_id.commercial_partner_id:
            raise AccessError(request.env._("This order does not belong to your account."))
        submission = checkout_submission(order)
        key = kwargs.pop("idempotency_key", None) or submission.key
        if key != submission.key or order.state == "cancel":
            raise ValidationError(request.env._("This checkout is no longer valid. Please review your cart."))
        self._validate_transaction_kwargs(kwargs)
        payload = {
            "order": order.id, "partner": order.partner_id.id,
            "shipping": order.partner_shipping_id.id, "invoice": order.partner_invoice_id.id,
            "currency": order.currency_id.id, "amount": order.amount_total,
            "lines": [(line.id, line.product_id.id, line.product_uom_id.id,
                       line.product_uom_qty, line.price_unit, line.discount, sorted(line.tax_ids.ids))
                      for line in order.order_line.sorted("id")],
            "payment": {name: value for name, value in kwargs.items() if name != "csrf_token"},
        }
        submission = request.env["ab_storefront_submission"]._claim(
            key, "checkout", request.website, submission_owner(), payload,
        )
        if submission.transaction_id:
            transaction = submission.transaction_id
            if transaction.sale_order_ids != order or transaction.state in ("cancel", "error"):
                raise ValidationError(request.env._("This checkout is no longer valid. Please review your cart."))
            request.session["__website_sale_last_tx_id"] = transaction.id
            return transaction._get_processing_values()
        result = super().shop_payment_transaction(order_id, access_token, **kwargs)
        transaction = request.env["payment.transaction"].sudo().browse(
            request.session["__website_sale_last_tx_id"]
        )
        submission.transaction_id = transaction
        return result
