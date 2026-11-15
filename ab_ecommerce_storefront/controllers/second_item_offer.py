from odoo import fields, http
from odoo.exceptions import UserError
from odoo.http import request
from odoo.tools import format_amount


class StorefrontSecondItemOffer(http.Controller):
    def _get_offer(self, offer_id):
        website = request.website
        today = fields.Date.context_today(website)
        offer = request.env["ab_storefront_offer"].sudo().search([
            ("id", "=", int(offer_id)),
            ("website_id", "=", website.id),
            ("company_id", "=", website.company_id.id),
            ("offer_type", "in", ["second_half", "gift"]),
            ("use_odoo_promotion", "=", False),
            ("active", "=", True),
            "|", ("date_from", "=", False), ("date_from", "<=", today),
            "|", ("date_to", "=", False), ("date_to", ">=", today),
        ], limit=1)
        if not offer or not offer.generated_program_ids.filtered("active"):
            raise UserError(request.env._("This offer is no longer available."))
        if offer in request.env["ab_storefront_offer"]._unavailable_for_customer(
            website, request.env.user.partner_id, request.cart,
        ):
            raise UserError(request.env._("This offer is no longer available for this customer."))
        return offer

    @http.route("/shop/offer/second-items", type="jsonrpc", auth="public", methods=["POST"], website=True)
    def second_items(self, offer_id, search="", offset=0):
        offer = self._get_offer(offer_id)
        if offer.second_item_mode != "choice":
            raise UserError(request.env._("This offer uses the same benefit product."))
        candidates = request.env["product.product"].browse(offer.second_product_ids.ids).exists().filtered_domain([
            ("id", "!=", offer.product_id.id),
            ("sale_ok", "=", True),
        ])
        term = str(search or "").strip()[:80]
        if term:
            candidates = candidates.filtered_domain([("name", "ilike", term)])
        candidates = candidates.sorted(lambda product: (product.name, product.id))
        available = candidates.filtered(lambda product: (
            product._is_add_to_cart_allowed() and not product._is_sold_out()
        ))
        start = max(0, min(int(offset), 1000))
        page = available[start:start + 12]
        prices = page.product_tmpl_id._get_sales_prices(request.website)
        return {
            "items": [{
                "id": product.id,
                "name": product.name,
                "image": request.website.image_url(product.product_tmpl_id, "image_256"),
                "price": format_amount(
                    request.env, prices[product.product_tmpl_id.id]["price_reduce"],
                    request.website.currency_id,
                ),
                "discounted_price": format_amount(
                    request.env, prices[product.product_tmpl_id.id]["price_reduce"] * (
                        1 - float(offer.second_discount_rate) / 100
                    ) if offer.offer_type == "second_half" else 0,
                    request.website.currency_id,
                ),
            } for product in page],
            "has_more": len(available) > start + len(page),
        }

    @http.route("/shop/offer/add-second-item", type="jsonrpc", auth="public", methods=["POST"], website=True)
    def add_second_item(self, offer_id, second_product_id=None):
        offer = self._get_offer(offer_id)
        first = request.env["product.product"].browse(offer.product_id.id).exists()
        second_id = first.id if offer.second_item_mode == "same" else int(second_product_id or 0)
        if offer.second_item_mode == "choice" and second_id not in offer.second_product_ids.ids:
            raise UserError(request.env._("Choose an eligible benefit product."))
        second = request.env["product.product"].browse(second_id).exists()
        for product in (first, second):
            if not product or not product._is_add_to_cart_allowed() or product._is_sold_out():
                raise UserError(request.env._("An item in this offer is no longer available."))
        order = request.cart or request.website._create_cart()
        if order.website_id != request.website or order.company_id != request.website.company_id:
            raise UserError(request.env._("This cart is not available for this website."))
        with request.env.cr.savepoint():
            if offer.offer_type == "gift":
                result = order.with_context(skip_cart_verification=True)._cart_add(first.id, quantity=offer.buy_qty)
                if result["added_qty"] != offer.buy_qty:
                    raise UserError(request.env._("The required purchase quantity is no longer available."))
                order._update_programs_and_rewards()
                program = offer.generated_program_ids.filtered("active")
                reward = program.reward_ids.filtered("active")
                coupon = order.coupon_point_ids.coupon_id.filtered(lambda candidate: candidate.program_id == program)
                if len(reward) != 1 or len(coupon) != 1:
                    raise UserError(request.env._("The gift could not be applied. Please try again."))
                lines = order.order_line.filtered(lambda line: line.reward_id == reward)
                lines._reset_loyalty()
                values = order._get_reward_line_values(reward, coupon, product=second)
                order._write_vals_from_reward_vals(values, lines)
            elif offer.second_item_mode == "same":
                result = order.with_context(skip_cart_verification=True)._cart_add(first.id, quantity=2)
                if result["added_qty"] != 2:
                    raise UserError(request.env._("Two units are required for this offer."))
            else:
                for product in (first, second):
                    result = order.with_context(skip_cart_verification=True)._cart_add(product.id, quantity=1)
                    if result["added_qty"] != 1:
                        raise UserError(request.env._("An item in this offer is no longer available."))
            order._verify_cart_after_update()
            if not order.order_line.filtered(
                lambda line: line.is_reward_line and line.reward_id.program_id in offer.generated_program_ids
            ):
                raise UserError(request.env._("The offer could not be applied. Please try again."))
        return {"url": "/shop/cart"}
