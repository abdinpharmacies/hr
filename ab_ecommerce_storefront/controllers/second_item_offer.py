from math import floor

from odoo import fields, http
from odoo.exceptions import UserError
from odoo.http import request
from odoo.tools import format_amount


class StorefrontSecondItemOffer(http.Controller):
    def _gift_purchase_quantity(self, offer, requested):
        if requested is None:
            return offer.buy_qty
        if type(requested) is not int or requested < 1 or requested > 1000:
            raise UserError(request.env._("Choose a valid purchase quantity."))
        return max(offer.buy_qty, requested)

    def _get_offer(self, offer_id):
        website = request.website
        today = fields.Date.context_today(website)
        offer = request.env["ab_storefront_offer"].sudo().search([
            ("id", "=", int(offer_id)),
            ("website_id", "=", website.id),
            ("company_id", "=", website.company_id.id),
            ("offer_type", "in", ["second_half", "gift", "mix_discount"]),
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
    def second_items(self, offer_id, search="", offset=0, purchase_quantity=None):
        offer = self._get_offer(offer_id)
        if offer.second_item_mode != "choice":
            raise UserError(request.env._("This offer uses the same benefit product."))
        candidates = request.env["product.product"].sudo().browse(offer.second_product_ids.ids).exists().filtered_domain([
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
        gift_slots = 0
        allocations = {}
        if offer.offer_type == "gift":
            purchase_quantity = self._gift_purchase_quantity(offer, purchase_quantity)
            cart = request.cart
            if cart and (cart.website_id != request.website or cart.company_id != request.website.company_id):
                raise UserError(request.env._("This cart is not available for this website."))
            paid_quantity = sum(
                line.product_uom_id._compute_quantity(line.product_uom_qty, offer.product_id.uom_id, round=False)
                for line in cart.order_line.filtered(
                    lambda line: not line.is_reward_line and line.product_id == offer.product_id
                )
            ) if cart else 0
            applications = floor((paid_quantity + purchase_quantity) / offer.buy_qty)
            if offer.max_applications:
                applications = min(applications, offer.max_applications)
            gift_slots = applications * offer.gift_qty
            if cart:
                allocations = {
                    line.product_id.id: int(line.product_uom_qty)
                    for line in cart.order_line.filtered(
                        lambda line: line.is_reward_line
                        and line.reward_id.program_id in offer.generated_program_ids
                    )
                }
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
            "offer_type": offer.offer_type,
            "gift_slots": gift_slots,
            "allocations": allocations,
        }

    @http.route("/shop/offer/add-second-item", type="jsonrpc", auth="public", methods=["POST"], website=True)
    def add_second_item(
        self, offer_id, second_product_id=None, gift_allocations=None,
        purchase_quantity=None, primary_product_id=None,
    ):
        offer = self._get_offer(offer_id)
        if offer.offer_type == "mix_discount":
            return self._add_mix_offer(offer, primary_product_id, purchase_quantity)
        if offer.offer_type == "gift":
            purchase_quantity = self._gift_purchase_quantity(offer, purchase_quantity)
        first = request.env["product.product"].sudo().browse(offer.product_id.id).exists()
        allocation_ids = []
        if offer.offer_type == "gift" and gift_allocations is not None:
            if offer.second_item_mode != "choice":
                raise UserError(request.env._("This offer uses the same benefit product."))
            if not isinstance(gift_allocations, list) or not gift_allocations or len(gift_allocations) > 100:
                raise UserError(request.env._("Choose the required number of gifts."))
            allocation_ids = [item.get("product_id") for item in gift_allocations if isinstance(item, dict)]
            if len(allocation_ids) != len(gift_allocations) or any(type(item) is not int for item in allocation_ids):
                raise UserError(request.env._("Choose eligible gift products and valid quantities."))
            if len(set(allocation_ids)) != len(allocation_ids):
                raise UserError(request.env._("Choose eligible gift products and valid quantities."))
            if any(product_id not in offer.second_product_ids.ids for product_id in allocation_ids):
                raise UserError(request.env._("Choose eligible gift products and valid quantities."))
            second_product_id = allocation_ids[0]
        second_id = first.id if offer.second_item_mode == "same" else int(second_product_id or 0)
        if offer.second_item_mode == "choice" and second_id not in offer.second_product_ids.ids:
            raise UserError(request.env._("Choose an eligible benefit product."))
        second = request.env["product.product"].sudo().browse(second_id).exists()
        if not first or not second:
            raise UserError(request.env._("An item in this offer is no longer available."))
        chosen = request.env["product.product"].sudo().browse(allocation_ids).exists() if allocation_ids else second
        if allocation_ids and len(chosen) != len(allocation_ids):
            raise UserError(request.env._("Choose eligible gift products and valid quantities."))
        for product in first | chosen:
            if not product or not product._is_add_to_cart_allowed() or product._is_sold_out():
                raise UserError(request.env._("An item in this offer is no longer available."))
        order = request.cart or request.website._create_cart()
        if order.website_id != request.website or order.company_id != request.website.company_id:
            raise UserError(request.env._("This cart is not available for this website."))
        with request.env.cr.savepoint():
            if offer.offer_type == "gift":
                result = order.with_context(skip_cart_verification=True)._cart_add(first.id, quantity=purchase_quantity)
                if result["added_qty"] != purchase_quantity:
                    raise UserError(request.env._("The required purchase quantity is no longer available."))
                order._update_programs_and_rewards()
                program = offer.generated_program_ids.filtered("active")
                reward = program.reward_ids.filtered("active")
                coupon = order.coupon_point_ids.coupon_id.filtered(lambda candidate: candidate.program_id == program)
                if len(reward) != 1 or len(coupon) != 1:
                    raise UserError(request.env._("The gift could not be applied. Please try again."))
                lines = order.order_line.filtered(lambda line: line.reward_id == reward)
                lines._reset_loyalty()
                allocations = None
                if gift_allocations is not None:
                    allocations = {
                        item["product_id"]: item.get("quantity") for item in gift_allocations
                    }
                values = order._get_reward_line_values(
                    reward, coupon, product=second, gift_allocations=allocations,
                )
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

    def _add_mix_offer(self, offer, primary_product_id, purchase_quantity):
        if type(primary_product_id) is not int or primary_product_id not in offer._qualifying_products().ids:
            raise UserError(request.env._("Choose an eligible offer product."))
        if purchase_quantity is None:
            purchase_quantity = offer.buy_qty
        if type(purchase_quantity) is not int or not 1 <= purchase_quantity <= 1000:
            raise UserError(request.env._("Choose a valid purchase quantity."))
        purchase_quantity = max(offer.buy_qty, purchase_quantity)
        applications = floor(purchase_quantity / offer.buy_qty)
        if offer.max_applications:
            applications = min(applications, offer.max_applications)
        discounted_quantity = applications * offer.gift_qty
        if not discounted_quantity:
            raise UserError(request.env._("Increase the purchase quantity to qualify for this offer."))
        primary = request.env["product.product"].sudo().browse(primary_product_id).exists()
        if not primary or not primary._is_add_to_cart_allowed() or primary._is_sold_out():
            raise UserError(request.env._("An item in this offer is no longer available."))
        order = request.cart or request.website._create_cart()
        if order.website_id != request.website or order.company_id != request.website.company_id:
            raise UserError(request.env._("This cart is not available for this website."))

        def cart_quantity(product):
            return sum(
                line.product_uom_id._compute_quantity(
                    line.product_uom_qty, product.uom_id, round=False,
                )
                for line in order.order_line.filtered(lambda current: (
                    not current.is_reward_line and current.product_id == product
                ))
            )

        primary_capacity = offer._remaining_product_offer_units(primary)
        if primary_capacity != float("inf") and cart_quantity(primary) + purchase_quantity > primary_capacity:
            raise UserError(request.env._("This product has reached its allocation for the offer."))
        candidates = (offer._qualifying_products() - primary).exists().filtered(lambda product: (
            product._is_add_to_cart_allowed() and not product._is_sold_out()
        ))
        prices = candidates.product_tmpl_id._get_sales_prices(request.website)
        candidates = candidates.sorted(lambda product: (
            prices[product.product_tmpl_id.id]["price_reduce"], product.id,
        ))
        allocations = []
        remaining = discounted_quantity
        for product in candidates:
            capacity = offer._remaining_product_offer_units(product)
            if capacity != float("inf"):
                capacity = max(0, floor(capacity - cart_quantity(product)))
            quantity = remaining if capacity == float("inf") else min(remaining, capacity)
            if quantity:
                allocations.append((product, quantity))
                remaining -= quantity
            if not remaining:
                break
        if remaining:
            raise UserError(request.env._("No other collection product has enough offer allocation."))
        with request.env.cr.savepoint():
            result = order.with_context(skip_cart_verification=True)._cart_add(
                primary.id, quantity=purchase_quantity,
            )
            if result["added_qty"] != purchase_quantity:
                raise UserError(request.env._("The required purchase quantity is no longer available."))
            for product, quantity in allocations:
                result = order.with_context(skip_cart_verification=True)._cart_add(
                    product.id, quantity=quantity,
                )
                if result["added_qty"] != quantity:
                    raise UserError(request.env._("An item in this offer is no longer available."))
                line = order.order_line.filtered(lambda current: current.id == result["line_id"])
                if not line:
                    raise UserError(request.env._("The offer could not be applied. Please try again."))
                line.sudo().with_context(ab_storefront_manage_offer_lines=True).write({
                    "ab_storefront_mix_benefit_offer_id": offer.id,
                })
            order._verify_cart_after_update()
            if not order.order_line.filtered(
                lambda line: line.is_reward_line and line.reward_id.program_id in offer.generated_program_ids
            ):
                raise UserError(request.env._("The offer could not be applied. Please try again."))
        return {"url": "/shop/cart"}
