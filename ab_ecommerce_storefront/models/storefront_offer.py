from collections import defaultdict
from math import floor, isfinite

from psycopg2 import IntegrityError

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request


class StorefrontOffer(models.Model):
    _name = "ab_storefront_offer"
    _description = "Storefront Offer"
    _inherit = ["mail.thread"]
    _check_company_auto = True
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    once_per_customer = fields.Boolean(
        string="Once per Customer", tracking=True,
        help="Allow this offer on only one confirmed order per customer, including their delivery addresses. Cancelling the order does not restore eligibility.",
    )
    sequence = fields.Integer(default=10)
    website_id = fields.Many2one(
        "website", required=True, ondelete="restrict", tracking=True,
        default=lambda self: self._default_offer_website(),
    )
    company_id = fields.Many2one(related="website_id.company_id", store=True)
    carousel_slide_id = fields.Many2one(
        "ab_website_carousel_slide", string="Carousel Slide", ondelete="set null", tracking=True,
        domain="[('active', '=', True), '|', ('website_id', '=', False), ('website_id', '=', website_id)]",
        help="Optionally link this offer to an existing homepage carousel image.",
    )
    carousel_image_1920 = fields.Image(
        related="carousel_slide_id.image_1920", string="Carousel Image", readonly=True,
    )
    product_id = fields.Many2one(
        "product.product", required=True, ondelete="restrict", check_company=True,
        domain="[('sale_ok', '=', True), '|', ('website_id', '=', False), ('website_id', '=', website_id)]",
        tracking=True,
    )
    offer_type = fields.Selection(
        [("gift", "Buy X + Free Gifts"), ("price", "Before / After Price"),
         ("second_half", "Second Item Discount"),
         ("mix_discount", "Mix & Match Quantity Discount"),
         ("sheet", "Product Group Promotion"),
         ("percent", "Percentage Discount"), ("amount", "Fixed Amount Discount")],
        required=True, default="gift", tracking=True,
    )
    sheet_group_qty = fields.Integer(string="Qualifying Group Size", default=1, tracking=True)
    sheet_discount_qty = fields.Integer(string="Discounted Units per Group", default=1, tracking=True)
    sheet_rate = fields.Float(string="Discount Percentage", default=10, tracking=True)
    sheet_fixed_price = fields.Float(string="Final Unit Price in EGP", tracking=True)
    sheet_priority = fields.Integer(string="Offer Priority", tracking=True)
    second_item_mode = fields.Selection(
        [("same", "Same Product"), ("choice", "Customer Chooses")],
        string="Second Item", default="same", tracking=True,
    )
    second_product_ids = fields.Many2many(
        "product.product", "ab_storefront_offer_second_product_rel", "offer_id", "product_id",
        string="Eligible Second Products", check_company=True,
        domain="[('sale_ok', '=', True), '|', ('website_id', '=', False), ('website_id', '=', website_id)]",
    )
    main_product_max_offer_units = fields.Integer(
        string="Main Product Units Allocated to This Offer", default=0, tracking=True,
        help="The maximum number of this product's units that may participate across confirmed orders during the offer. No limit keeps it available.",
    )
    collection_product_line_ids = fields.One2many(
        "ab_storefront_offer_collection_product", "offer_id", string="Additional Collection Products",
    )
    percentage_rate = fields.Selection(
        [(str(rate), f"{rate}%") for rate in (5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 60, 70)],
        string="Percentage Rate", default="10", tracking=True,
    )
    second_discount_rate = fields.Selection(
        [(str(rate), f"{rate}%") for rate in (20, 25, 30, 35, 40, 45, 50, 60, 70, 100)],
        string="Second Item Discount Rate", default="50", tracking=True,
    )
    amount_discount = fields.Selection(
        [(str(amount), str(amount)) for amount in (80, 100, 120, 125, 130, 140, 150, 200, 250)]
        + [("custom", "Custom Amount")],
        string="Discount Amount", default="80", tracking=True,
    )
    custom_amount_discount = fields.Monetary(
        string="Custom Discount Amount", currency_field="currency_id", tracking=True,
    )
    max_offer_units = fields.Integer(
        string="Units Allocated to This Offer", default=0, tracking=True,
        help="The offer stops after this many paid units of its main product are sold across all customers. No limit keeps it available.",
    )
    max_applications = fields.Integer(
        string="Maximum Benefit Applications per Order", default=0, tracking=True,
        help="Limit how many times the benefit applies in one order. A new order starts a new limit. No limit allows every eligible quantity.",
    )
    current_price = fields.Monetary(string="Current Price", compute="_compute_current_offer_price")
    discounted_price = fields.Monetary(string="Discounted Price", compute="_compute_current_offer_price")

    buy_qty = fields.Integer(string="Buy Quantity", default=1, tracking=True)
    gift_qty = fields.Integer(string="Free Quantity", default=1, tracking=True)
    pricelist_id = fields.Many2one(
        "product.pricelist", check_company=True, ondelete="restrict", tracking=True,
        compute="_compute_offer_pricelist", store=True, precompute=True, readonly=False,
        domain="[('website_id', '=', website_id)]",
    )
    currency_id = fields.Many2one(related="pricelist_id.currency_id")
    price_before = fields.Monetary(
        string="Price Before", compute="_compute_price_before", store=True,
        precompute=True, readonly=False, tracking=True,
    )
    price_after = fields.Monetary(string="Price After", tracking=True)
    discount_percentage = fields.Float(
        string="Discount (%)", compute="_compute_discount_percentage",
        inverse="_inverse_discount_percentage", readonly=False,
    )
    date_from = fields.Date(string="Start Date", tracking=True)
    date_to = fields.Date(string="End Date", tracking=True)
    use_odoo_promotion = fields.Boolean(string="Link Existing Odoo Promotion", tracking=True)
    program_id = fields.Many2one(
        "loyalty.program", string="Odoo Promotion", check_company=True,
        ondelete="restrict", tracking=True,
        domain="[('website_id', '=', website_id), ('program_type', 'in', ['promotion', 'buy_x_get_y'])]",
    )
    generated_program_ids = fields.One2many("loyalty.program", "ab_storefront_offer_id", readonly=True)
    price_rule_ids = fields.One2many("product.pricelist.item", "ab_storefront_offer_id", readonly=True)

    @api.depends("product_id.lst_price", "currency_id", "website_id", "percentage_rate", "amount_discount", "custom_amount_discount", "offer_type")
    def _compute_current_offer_price(self):
        for offer in self:
            product = offer.product_id.with_company(offer.company_id or self.env.company)
            price = product.lst_price if product else 0
            if product and offer.currency_id:
                price = product.currency_id._convert(
                    price, offer.currency_id, offer.company_id, fields.Date.context_today(offer),
                )
            offer.current_price = price
            offer.discounted_price = max(0, (
                price * (1 - float(offer.percentage_rate or 0) / 100)
                if offer.offer_type == "percent" else price - offer._fixed_discount_amount()
            ))

    def _fixed_discount_amount(self):
        self.ensure_one()
        return self.custom_amount_discount if self.amount_discount == "custom" else float(self.amount_discount or 0)

    def _maximum_fixed_discount(self):
        self.ensure_one()
        price = self.currency_id.round(self.current_price) if self.currency_id else self.current_price
        return max(0.0, price - 1)

    def _benefit_products(self):
        self.ensure_one()
        if self.offer_type == "mix_discount":
            return self._qualifying_products()
        return self.product_id if self.second_item_mode == "same" else self.second_product_ids

    def _qualifying_products(self):
        self.ensure_one()
        if self.offer_type == "sheet":
            return self.product_id | self.second_product_ids
        if self.offer_type == "mix_discount":
            return self.product_id | self._collection_products()
        return self.product_id

    def _collection_products(self):
        self.ensure_one()
        return self.collection_product_line_ids.product_id or self.second_product_ids

    def _product_offer_limit(self, product):
        self.ensure_one()
        if product == self.product_id:
            return self.main_product_max_offer_units
        line = self.collection_product_line_ids.filtered(lambda current: current.product_id == product)[:1]
        return line.max_offer_units if line else 0

    def _sold_product_quantity(self, product):
        self.ensure_one()
        return sum(
            sum(
                line.product_uom_id._compute_quantity(
                    line.product_uom_qty, line.product_id.uom_id, round=False,
                )
                for line in order.order_line.filtered(lambda current: (
                    not current.is_reward_line and current.product_id == product
                    and current.product_uom_qty > 0
                ))
            )
            for order in self._orders_using_offer()
        )

    def _remaining_product_offer_units(self, product):
        self.ensure_one()
        limit = self._product_offer_limit(product)
        return max(0, limit - self._sold_product_quantity(product)) if limit else float("inf")

    def _orders_using_offer(self):
        self.ensure_one()
        programs = self.with_context(active_test=False).generated_program_ids | self.program_id
        applied_line = fields.Domain("ab_storefront_price_offer_id", "=", self.id)
        if programs:
            applied_line |= fields.Domain("reward_id.program_id", "in", programs.ids)
        return self.env["sale.order"].sudo().search(
            fields.Domain("website_id", "=", self.website_id.id)
            & fields.Domain("company_id", "=", self.company_id.id)
            & fields.Domain("state", "=", "sale")
            & fields.Domain("order_line", "any", applied_line)
        )

    def _paid_primary_quantity(self, order):
        self.ensure_one()
        programs = self.with_context(active_test=False).generated_program_ids | self.program_id
        has_reward = bool(order.order_line.filtered(lambda line: line.reward_id.program_id in programs))
        qualifying_products = self._qualifying_products()
        lines = order.order_line.filtered(lambda line: (
            not line.is_reward_line and line.product_id in qualifying_products and line.product_uom_qty > 0
            and (has_reward or line.ab_storefront_price_offer_id == self)
        ))
        return sum(
            line.product_uom_id._compute_quantity(line.product_uom_qty, line.product_id.uom_id, round=False)
            for line in lines
        )

    def _sold_primary_quantity(self):
        self.ensure_one()
        return sum(self._paid_primary_quantity(order) for order in self._orders_using_offer())

    def _storefront_description(self):
        self.ensure_one()
        if self.offer_type == "gift":
            message = _("Buy %(buy)s and get %(free)s free.", buy=self.buy_qty, free=self.gift_qty)
            message += " " + (
                _("The gift is the same product.") if self.second_item_mode == "same"
                else _("Choose your gift from the eligible products.")
            )
        elif self.offer_type == "second_half":
            message = _("Buy one and get %(rate)s%% off a second eligible unit.", rate=self.second_discount_rate)
            message += " " + _("The cheapest eligible units receive the discount.")
        else:
            message = _(
                "Buy any %(buy)s items from this collection and get %(discounted)s more at %(rate)s%% off.",
                buy=self.buy_qty, discounted=self.gift_qty, rate=self.second_discount_rate,
            )
            message += " " + _("The cheapest other eligible product is added automatically and receives the discount.")
        if self.max_applications:
            message += " " + _("Up to %(count)s benefit applications per order.", count=self.max_applications)
        else:
            message += " " + _("Repeats for every qualifying purchase quantity.")
        return message

    @api.model
    def _default_offer_website(self):
        websites = self.env["website"].search([("company_id", "=", self.env.company.id)], limit=2)
        return websites if len(websites) == 1 else self.env["website"]

    @api.depends("website_id")
    def _compute_offer_pricelist(self):
        pricelists = self.env["product.pricelist"].search([
            ("active", "=", True), ("website_id", "in", self.website_id.ids),
        ], order="sequence, id")
        for offer in self:
            offer.pricelist_id = pricelists.filtered(lambda pricelist: (
                pricelist.website_id == offer.website_id
                and (not pricelist.company_id or pricelist.company_id == offer.company_id)
            ))[:1]

    @api.depends("product_id", "pricelist_id", "website_id")
    def _compute_price_before(self):
        for offer in self:
            product = offer.product_id.with_company(offer.company_id or self.env.company)
            price = product.lst_price if product else 0.0
            if product and offer.currency_id:
                price = product.currency_id._convert(
                    price, offer.currency_id, offer.company_id or self.env.company,
                    fields.Date.context_today(offer),
                )
            offer.price_before = price

    @api.depends("price_before", "price_after")
    def _compute_discount_percentage(self):
        for offer in self:
            offer.discount_percentage = (
                100 * (1 - offer.price_after / offer.price_before) if offer.price_before else 0.0
            )

    @api.onchange("discount_percentage")
    def _inverse_discount_percentage(self):
        for offer in self:
            price = offer.price_before * (1 - offer.discount_percentage / 100)
            offer.price_after = offer.currency_id.round(price) if offer.currency_id and isfinite(price) else price

    @api.onchange("offer_type")
    def _onchange_offer_type(self):
        if self.offer_type not in ("gift", "price"):
            self.use_odoo_promotion = False
            self.program_id = False

    @api.onchange("product_id", "pricelist_id", "website_id")
    def _onchange_original_price(self):
        self.price_after = self.price_before

    @api.constrains(
        "website_id", "product_id", "offer_type", "buy_qty", "gift_qty", "pricelist_id",
        "price_before", "price_after", "date_from", "date_to", "use_odoo_promotion", "program_id", "active",
        "second_item_mode", "second_product_ids", "percentage_rate", "amount_discount",
        "second_discount_rate", "max_offer_units", "max_applications", "custom_amount_discount",
        "main_product_max_offer_units", "collection_product_line_ids",
        "carousel_slide_id", "sheet_group_qty", "sheet_discount_qty", "sheet_rate",
        "sheet_fixed_price", "sheet_priority",
    )
    def _check_offer(self):
        other_offers = self.search([
            ("active", "=", True),
            ("website_id", "in", self.website_id.ids),
        ])
        for offer in self:
            if offer.date_from and offer.date_to and offer.date_to < offer.date_from:
                raise ValidationError(_("The end date must not precede the start date."))
            if offer.carousel_slide_id.website_id and offer.carousel_slide_id.website_id != offer.website_id:
                raise ValidationError(_("Select a carousel slide for this website or a shared slide."))
            product = offer.product_id
            if (
                not product.sale_ok or (offer.offer_type != "sheet" and product.product_tmpl_id.product_variant_count != 1)
                or (product.website_id and product.website_id != offer.website_id)
            ):
                raise ValidationError(_("Select a single-variant sale product available on this website."))
            if offer.max_offer_units < 0:
                raise ValidationError(_("The maximum offer product units must be a positive whole number or no limit."))
            if offer.main_product_max_offer_units < 0:
                raise ValidationError(_("The main product allocation must be a positive whole number or no limit."))
            if offer.max_applications < 0:
                raise ValidationError(_("The maximum benefit applications must be a positive whole number or no limit."))
            if offer.max_applications and (
                offer.offer_type not in ("gift", "second_half", "mix_discount")
                or offer.use_odoo_promotion
            ):
                raise ValidationError(_("Benefit application limits are available only for quantity-based offers managed here."))
            if offer.use_odoo_promotion:
                if offer.offer_type not in ("gift", "price"):
                    raise ValidationError(_("This offer type is managed here, without a linked promotion."))
                offer._check_linked_program()
            elif offer.offer_type == "sheet":
                if (not 1 <= offer.sheet_discount_qty <= offer.sheet_group_qty
                        or not isfinite(offer.sheet_rate) or not 0 < offer.sheet_rate <= 100
                        or not isfinite(offer.sheet_fixed_price) or offer.sheet_fixed_price < 0
                        or offer.sheet_priority < 0):
                    raise ValidationError(_("Check the website, promotion settings, quantities and price of the imported offer."))
                products = offer._qualifying_products()
                if any(not p.active or not p.sale_ok or p.type in ("combo", "service")
                       or (p.website_id and p.website_id != offer.website_id) for p in products):
                    raise ValidationError(_("Select active saleable products for this website and company."))
            elif offer.offer_type in ("gift", "second_half", "mix_discount"):
                if offer.offer_type == "gift" and (offer.buy_qty < 1 or offer.gift_qty < 1):
                    raise ValidationError(_("Buy and free quantities must be positive whole numbers."))
                if offer.offer_type == "mix_discount" and (offer.buy_qty < 1 or offer.gift_qty < 1):
                    raise ValidationError(_("Buy and discounted quantities must be positive whole numbers."))
                if offer.offer_type in ("second_half", "mix_discount") and not offer.second_discount_rate:
                    raise ValidationError(_("Select a second-item discount rate."))
                if offer.offer_type == "mix_discount":
                    products = offer._collection_products()
                    if not products or offer.product_id in products:
                        raise ValidationError(_("Choose at least one additional collection product."))
                    if any(
                        not candidate.sale_ok or candidate.product_tmpl_id.product_variant_count != 1
                        or candidate.type == "combo"
                        or (candidate.website_id and candidate.website_id != offer.website_id)
                        for candidate in products
                    ):
                        raise ValidationError(_("Collection products must be single-variant sale products on this website."))
                elif offer.second_item_mode == "choice":
                    products = offer.second_product_ids
                    if not products or offer.product_id in products:
                        raise ValidationError(_("Choose at least one other eligible benefit product."))
                    if any(
                        not candidate.sale_ok or candidate.product_tmpl_id.product_variant_count != 1
                        or candidate.type == "combo"
                        or (candidate.website_id and candidate.website_id != offer.website_id)
                        for candidate in products
                    ):
                        raise ValidationError(_("Benefit products must be single-variant sale products on this website."))
                elif offer.second_item_mode != "same":
                    raise ValidationError(_("Select how the customer receives the benefit product."))
            else:
                if not offer.pricelist_id or offer.pricelist_id.website_id != offer.website_id:
                    raise ValidationError(_("Select a pricelist for this website."))
                if offer.offer_type == "price" and (
                    not isfinite(offer.price_before) or not isfinite(offer.price_after)
                    or offer.price_after <= 0 or offer.price_before <= offer.price_after
                ):
                    raise ValidationError(_("Select a pricelist for this website and set a positive reduced price below the original price."))
                if offer.offer_type == "percent" and not offer.percentage_rate:
                    raise ValidationError(_("Select a percentage discount rate."))
                if offer.offer_type == "amount" and offer.active:
                    discount_amount = offer._fixed_discount_amount()
                    if not isfinite(discount_amount) or discount_amount <= 0:
                        raise ValidationError(_("Enter a positive fixed discount amount."))
                    if discount_amount > offer._maximum_fixed_discount():
                        raise ValidationError(_("The discounted product price must be at least EGP 1."))
                    if offer.currency_id != self.env.ref("base.EGP"):
                        raise ValidationError(_("Select an EGP pricelist and a discount amount below the current product price."))
            if offer.active:
                overlapping_carousel = other_offers.filtered(lambda other: (
                    other != offer and offer.carousel_slide_id
                    and other.website_id == offer.website_id
                    and other.carousel_slide_id == offer.carousel_slide_id
                    and (
                        (not offer.date_to or not other.date_from or other.date_from <= offer.date_to)
                        and (not offer.date_from or not other.date_to or other.date_to >= offer.date_from)
                    )
                ))
                if overlapping_carousel:
                    raise ValidationError(_(
                        "This carousel slide already has an overlapping storefront offer on this website."
                    ))
                overlapping = other_offers.filtered(lambda other: (
                    other != offer and not (offer.offer_type == other.offer_type == "sheet")
                    and other.website_id == offer.website_id
                    and bool(other._qualifying_products() & offer._qualifying_products())
                    and (
                        offer.use_odoo_promotion or other.use_odoo_promotion
                        or (
                            (not offer.date_to or not other.date_from or other.date_from <= offer.date_to)
                            and (not offer.date_from or not other.date_to or other.date_to >= offer.date_from)
                        )
                    )
                ))
                if overlapping:
                    raise ValidationError(_("This product already has an overlapping storefront offer on this website."))

    def _check_linked_program(self):
        self.ensure_one()
        program = self.program_id
        if (
            not program or program.ab_storefront_offer_id or program.website_id != self.website_id
            or program.company_id not in (self.company_id, self.env["res.company"])
            or not program.ecommerce_ok or program.trigger != "auto" or program.applies_on != "current"
            or program.program_type not in ("promotion", "buy_x_get_y")
        ):
            raise ValidationError(_("Select an automatic current-order promotion for this website and company."))
        rules = program.rule_ids.filtered("active")
        rewards = program.reward_ids.filtered("active")
        if len(rules) != 1 or len(rewards) != 1 or rules.minimum_amount:
            raise ValidationError(_("The linked promotion must have one automatic product rule and one reward, without a minimum amount."))
        if rules.mode != "auto" or not self.product_id.filtered_domain(rules._get_valid_product_domain()):
            raise ValidationError(_("The selected product must qualify for the linked promotion."))
        if self.offer_type == "gift":
            if (
                rewards.reward_type != "product" or rewards.multi_product
                or rewards.reward_product_id != self.product_id
                or rules.reward_point_mode != "unit"
                or rules.minimum_qty > rewards.required_points / rules.reward_point_amount
            ):
                raise ValidationError(_("Select a same-product free-gift promotion."))
        elif (
            rewards.reward_type != "discount" or rewards.discount_mode != "percent"
            or not 0 < rewards.discount < 100
            or rewards.discount_applicability != "specific" or rewards.discount_max_amount
            or rules.minimum_qty > 1 or rules.reward_point_amount < rewards.required_points
            or rules.reward_point_mode not in ("unit", "order")
            or not self.product_id.filtered_domain(rewards._get_discount_product_domain())
        ):
            raise ValidationError(_("Select an uncapped percentage discount for this product, valid from one unit."))

    @api.model_create_multi
    def create(self, vals_list):
        if any({"generated_program_ids", "price_rule_ids"} & set(vals) for vals in vals_list):
            raise ValidationError(_("Offer rules are managed automatically."))
        self.check_access("create")
        prepared_values = []
        for values in vals_list:
            values = dict(values)
            if "discount_percentage" in values:
                if "price_after" not in values:
                    offer = self.new(values)
                    offer._inverse_discount_percentage()
                    values.update(price_before=offer.price_before, price_after=offer.price_after)
                values.pop("discount_percentage")
            prepared_values.append(values)
        offers = super().create(prepared_values)
        offers._sync_offer_rules()
        return offers

    def write(self, vals):
        if {"generated_program_ids", "price_rule_ids"} & set(vals):
            raise ValidationError(_("Offer rules are managed automatically."))
        if "price_after" in vals and "discount_percentage" in vals:
            vals = {key: value for key, value in vals.items() if key != "discount_percentage"}
        if any(offer.offer_type == "sheet" and (
            vals.get("offer_type", "sheet") != "sheet" or vals.get("website_id", offer.website_id.id) != offer.website_id.id
        ) or offer.offer_type != "sheet" and vals.get("offer_type") == "sheet" for offer in self):
            raise ValidationError(_("Create a new product group promotion to change its type or website."))
        result = super().write(vals)
        if set(vals) & {
            "name", "active", "website_id", "product_id", "offer_type", "buy_qty", "gift_qty",
            "pricelist_id", "price_before", "price_after", "date_from", "date_to",
            "use_odoo_promotion", "program_id", "second_item_mode", "second_product_ids",
            "percentage_rate", "amount_discount", "custom_amount_discount", "second_discount_rate",
            "main_product_max_offer_units", "collection_product_line_ids", "sheet_group_qty",
            "sheet_discount_qty", "sheet_rate", "sheet_fixed_price", "sheet_priority",
        }:
            self._sync_offer_rules()
        if vals.get("once_per_customer"):
            self._remember_confirmed_offer_uses()
        return result

    def _remember_confirmed_offer_uses(self):
        self.check_access("write")
        for offer in self.sudo():
            programs = offer.with_context(active_test=False).generated_program_ids
            if offer.use_odoo_promotion:
                programs |= offer.program_id
            lines = self.env["sale.order.line"].sudo().search(
                fields.Domain("order_id.website_id", "=", offer.website_id.id)
                & fields.Domain("company_id", "=", offer.company_id.id)
                & fields.Domain("order_id.state", "=", "sale")
                & (
                    fields.Domain("ab_storefront_price_offer_id", "=", offer.id)
                    | fields.Domain("reward_id.program_id", "in", programs.ids)
                ),
            )
            uses = self.env["ab_storefront_offer_use"].sudo()
            partners = set(uses.search([("offer_id", "=", offer.id)]).partner_id.ids)
            for order in lines.order_id.sorted(lambda order: (order.date_order, order.id)):
                partner = order.partner_id.commercial_partner_id
                if partner.id in partners:
                    continue
                try:
                    with self.env.cr.savepoint():
                        uses.create({"offer_id": offer.id, "partner_id": partner.id, "order_id": order.id})
                except IntegrityError as error:
                    if error.diag.constraint_name != "ab_storefront_offer_use_offer_customer_unique":
                        raise
                partners.add(partner.id)

    def unlink(self):
        self.check_access("unlink")
        if self.env["ab_storefront_offer_use"].sudo().search_count([("offer_id", "in", self.ids)]):
            raise ValidationError(_("This offer has already been used. Archive it to preserve customer usage history."))
        if self.env["sale.order.line"].sudo().search_count([
            ("ab_storefront_price_offer_id", "in", self.ids),
        ]):
            raise ValidationError(_("This offer is referenced by an order. Archive it instead."))
        programs = self.sudo().with_context(active_test=False).generated_program_ids
        programs.write({"active": False, "ab_storefront_offer_id": False})
        self.sudo().price_rule_ids.unlink()
        return super().unlink()

    @api.model
    def _unavailable_for_customer(self, website, partner, order=None):
        offers = self.sudo().with_context(active_test=False).search([
            ("website_id", "=", website.id), ("company_id", "=", website.company_id.id),
            "|", "|", ("once_per_customer", "=", True), ("max_offer_units", ">", 0),
            ("offer_type", "=", "mix_discount"),
        ])
        sold_out = offers.filtered(lambda offer: (
            offer.max_offer_units and offer._sold_primary_quantity() >= offer.max_offer_units
            or offer.offer_type == "mix_discount" and len(offer._qualifying_products().filtered(
                lambda product: offer._remaining_product_offer_units(product) > 0
            )) < 2
        ))
        customer_limited = offers.filtered("once_per_customer")
        if not partner or partner == website.sudo().user_id.partner_id:
            return sold_out | customer_limited
        uses = self.env["ab_storefront_offer_use"].sudo().search([
            ("offer_id", "in", customer_limited.ids),
            ("partner_id", "=", partner.commercial_partner_id.id),
            ("order_id", "!=", order.id if order else False),
        ])
        return sold_out | uses.offer_id

    def _sync_offer_rules(self):
        self.check_access("write")
        if not self.env.su and self.company_id - self.env.companies:
            raise AccessError(_("You cannot manage offers outside your allowed companies."))
        for offer in self.filtered(lambda o: o.active and o.offer_type == "sheet"):
            products = offer._qualifying_products()
            quantities = offer.website_id._ab_offer_available_quantities(products)
            issue = offer.website_id._ab_offer_stock_issue(products, quantities, offer.sheet_group_qty)
            if issue:
                raise ValidationError(issue)
            if not offer.date_to or offer.date_to >= fields.Date.context_today(offer):
                offer.website_id._ab_publish_offer_products(products)
        self = self.sudo()
        for offer in self:
            programs = offer.with_context(active_test=False).generated_program_ids
            if offer.offer_type == "sheet":
                product_ids = offer._qualifying_products().ids
                values = self.env["loyalty.program"]._ab_sheet_values(
                    offer.name, offer.website_id, product_ids, f"storefront-{offer.id}",
                    offer.sheet_group_qty, offer.sheet_discount_qty,
                    100 if offer.sheet_fixed_price else offer.sheet_rate, offer.sheet_fixed_price,
                    offer.sheet_priority, offer.date_from, offer.date_to,
                )
                values.update(active=offer.active, ab_storefront_offer_id=offer.id)
                if programs:
                    rule_values = values.pop("rule_ids")[0][2]
                    reward_values = values.pop("reward_ids")[0][2]
                    programs.write(values)
                    programs.rule_ids.write(rule_values)
                    programs.reward_ids.write(reward_values)
                else:
                    self.env["loyalty.program"].create(values)
                continue
            programs.write({"active": False})
            if offer.use_odoo_promotion or offer.offer_type not in ("gift", "second_half", "mix_discount"):
                continue
            values = {
                "name": offer.name, "active": offer.active, "program_type": "buy_x_get_y",
                "company_id": offer.company_id.id, "website_id": offer.website_id.id,
                "sale_ok": False, "ecommerce_ok": True, "trigger": "auto", "applies_on": "current",
                "date_from": offer.date_from, "date_to": offer.date_to,
                "ab_storefront_offer_id": offer.id,
            }
            rule_values = {
                "mode": "auto",
                "minimum_qty": (
                    offer.buy_qty if offer.offer_type == "gift"
                    else offer.buy_qty + offer.gift_qty if offer.offer_type == "mix_discount"
                    else 2 if offer.second_item_mode == "same" else 1
                ),
                "minimum_amount": 0, "reward_point_mode": "unit", "reward_point_amount": 1,
                "product_ids": [fields.Command.set(offer._qualifying_products().ids)],
            }
            if offer.offer_type == "gift":
                reward_values = {
                    "reward_type": "product", "reward_product_id": offer._benefit_products()[:1].id,
                    "ab_storefront_gift_product_ids": [fields.Command.set(offer._benefit_products().ids)],
                    "reward_product_qty": offer.gift_qty, "required_points": offer.buy_qty,
                }
            else:
                reward_values = {
                    "reward_type": "discount", "discount": float(offer.second_discount_rate), "discount_mode": "percent",
                    "discount_applicability": "cheapest", "discount_max_amount": 0,
                    "discount_product_ids": [fields.Command.set(offer._benefit_products().ids)],
                    "required_points": (
                        offer.buy_qty + offer.gift_qty if offer.offer_type == "mix_discount"
                        else 2 if offer.second_item_mode == "same" else 1
                    ),
                }
            if programs:
                programs.write(values)
                programs.rule_ids.write(rule_values)
                programs.reward_ids.write(reward_values)
            else:
                values.update({
                    "rule_ids": [fields.Command.create(rule_values)],
                    "reward_ids": [fields.Command.create(reward_values)],
                })
                self.env["loyalty.program"].create(values)
        for offer in self.filtered(lambda rec: rec.offer_type in ("price", "percent", "amount") and not rec.use_odoo_promotion):
            values = {
                "pricelist_id": offer.pricelist_id.id, "product_id": offer.product_id.id,
                "applied_on": "0_product_variant", "min_quantity": 0,
                "compute_price": "fixed", "base": "list_price", "fixed_price": offer.price_after,
                "date_start": offer.date_from,
                "date_end": fields.Datetime.to_datetime(offer.date_to).replace(hour=23, minute=59, second=59) if offer.date_to else False,
                "ab_storefront_offer_id": offer.id,
            }
            if offer.offer_type == "percent":
                values.update(compute_price="percentage", percent_price=float(offer.percentage_rate))
            elif offer.offer_type == "amount":
                values.update(compute_price="formula", price_discount=0, price_surcharge=-offer._fixed_discount_amount())
            if offer.price_rule_ids:
                offer.price_rule_ids.write(values)
            else:
                self.env["product.pricelist.item"].create(values)


class StorefrontOfferCollectionProduct(models.Model):
    _name = "ab_storefront_offer_collection_product"
    _description = "Storefront Offer Collection Product"
    _check_company_auto = True
    _order = "sequence, id"

    offer_id = fields.Many2one(
        "ab_storefront_offer", required=True, ondelete="cascade", check_company=True, index=True,
    )
    company_id = fields.Many2one(related="offer_id.company_id", store=True)
    website_id = fields.Many2one(related="offer_id.website_id", store=True)
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one(
        "product.product", required=True, ondelete="restrict", check_company=True,
        domain="[('sale_ok', '=', True), '|', ('website_id', '=', False), ('website_id', '=', website_id)]",
    )
    max_offer_units = fields.Integer(
        string="Units Allocated to This Offer", default=0,
        help="The maximum number of this product's units that may participate across confirmed orders during the offer. No limit keeps it available.",
    )

    _offer_product_unique = models.Constraint(
        "UNIQUE(offer_id, product_id)",
        "Each collection product can be added only once per offer.",
    )

    @api.constrains("offer_id", "product_id", "max_offer_units")
    def _check_collection_product(self):
        for line in self:
            if line.max_offer_units < 0:
                raise ValidationError(_("The product allocation must be a positive whole number or no limit."))
            product = line.product_id
            if product == line.offer_id.product_id:
                raise ValidationError(_("The main product cannot be repeated in the additional collection products."))
            if (
                not product.sale_ok or product.product_tmpl_id.product_variant_count != 1
                or product.type == "combo"
                or (product.website_id and product.website_id != line.website_id)
            ):
                raise ValidationError(_("Collection products must be single-variant sale products on this website."))

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines.offer_id._check_offer()
        lines.offer_id._sync_offer_rules()
        return lines

    def write(self, vals):
        offers = self.offer_id
        result = super().write(vals)
        (offers | self.offer_id)._check_offer()
        (offers | self.offer_id)._sync_offer_rules()
        return result

    def unlink(self):
        offers = self.offer_id
        result = super().unlink()
        offers._check_offer()
        offers._sync_offer_rules()
        return result


class LoyaltyProgram(models.Model):
    _inherit = "loyalty.program"

    ab_storefront_offer_id = fields.Many2one("ab_storefront_offer", copy=False, ondelete="restrict")


class LoyaltyReward(models.Model):
    _inherit = "loyalty.reward"

    ab_storefront_gift_product_ids = fields.Many2many(
        "product.product", "ab_storefront_reward_gift_product_rel", "reward_id", "product_id",
        string="Storefront Gift Products", check_company=True,
    )

    @api.depends("ab_storefront_gift_product_ids", "ab_storefront_gift_product_ids.active")
    def _compute_multi_product(self):
        super()._compute_multi_product()
        for reward in self.filtered(lambda current: current.reward_type == "product" and current.ab_storefront_gift_product_ids):
            reward.reward_product_ids = reward.ab_storefront_gift_product_ids.filtered("active")
            reward.multi_product = len(reward.reward_product_ids) != 1

    def _search_reward_product_ids(self, operator, value):
        domain = super()._search_reward_product_ids(operator, value)
        if domain is NotImplemented:
            return domain
        return fields.Domain(domain) | (
            fields.Domain("reward_type", "=", "product")
            & fields.Domain("ab_storefront_gift_product_ids", operator, value)
        )

    @api.model
    def _get_active_products_domain(self):
        return fields.Domain(super()._get_active_products_domain()) | (
            fields.Domain("reward_type", "=", "product")
            & fields.Domain("ab_storefront_gift_product_ids.active", "=", True)
        )


class StorefrontOfferUse(models.Model):
    _name = "ab_storefront_offer_use"
    _description = "Storefront Offer Use"
    _check_company_auto = True

    offer_id = fields.Many2one("ab_storefront_offer", required=True, ondelete="restrict", index=True)
    partner_id = fields.Many2one("res.partner", required=True, ondelete="restrict", index=True)
    order_id = fields.Many2one("sale.order", required=True, ondelete="restrict", check_company=True)
    company_id = fields.Many2one(related="offer_id.company_id", store=True)

    _offer_customer_unique = models.Constraint(
        "UNIQUE(offer_id, partner_id)",
        "This customer has already used this offer.",
    )


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _program_check_compute_points(self, programs):
        result = super()._program_check_compute_points(programs)
        for program, status in result.items():
            offer = program.sudo().ab_storefront_offer_id
            if (
                offer and offer.offer_type == "gift" and offer.max_applications
                and self.website_id == offer.website_id and self.company_id == offer.company_id
                and "points" in status
            ):
                status["points"] = [min(points, offer.max_applications * offer.buy_qty) for points in status["points"]]
        return result

    def _discountable_cheapest(self, reward):
        result = super()._discountable_cheapest(reward)
        offer = reward.program_id.sudo().ab_storefront_offer_id
        if not offer or offer.offer_type not in ("second_half", "mix_discount"):
            return result
        if self.website_id != offer.website_id or self.company_id != offer.company_id:
            return 0, {}
        lines = (self.order_line - self._get_no_effect_on_threshold_lines()).filtered(
            lambda line: not line.reward_id and not line.combo_item_id and line.product_uom_qty > 0
            and line.price_total > 0
        )
        purchase_lines = lines.filtered(lambda line: line.product_id in offer._qualifying_products())
        purchase_quantity = sum(
            line.product_uom_id._compute_quantity(line.product_uom_qty, line.product_id.uom_id, round=False)
            for line in purchase_lines
        )
        if offer.offer_type == "mix_discount":
            applications = floor(purchase_quantity / (offer.buy_qty + offer.gift_qty))
            if offer.max_applications:
                applications = min(applications, offer.max_applications)
            count = applications * offer.gift_qty
        else:
            count = floor(purchase_quantity / (2 if offer.second_item_mode == "same" else 1))
            if offer.max_applications:
                count = min(count, offer.max_applications)
        candidates = lines.filtered(lambda line: line.product_id in offer._benefit_products()).sorted(
            lambda line: (line.product_uom_id._compute_price(line.price_unit * (1 - line.discount / 100), line.product_id.uom_id), line.id)
        )
        if offer.offer_type == "mix_discount":
            marked_candidates = candidates.filtered(
                lambda line: line.ab_storefront_mix_benefit_offer_id == offer
            )
            if marked_candidates:
                candidates = marked_candidates
        discountable = 0
        amounts = defaultdict(float)
        for line in candidates:
            quantity = line.product_uom_id._compute_quantity(line.product_uom_qty, line.product_id.uom_id, round=False)
            units = min(count, floor(quantity))
            if not units:
                continue
            discountable += line.price_total / quantity * units
            taxes = line.tax_ids.filtered(lambda tax: tax.amount_type != "fixed")
            amounts[taxes] += line.product_uom_id._compute_price(
                line.price_unit * (1 - line.discount / 100), line.product_id.uom_id,
            ) * units
            count -= units
            if not count:
                break
        return discountable, amounts

    def _get_reward_values_product(self, reward, coupon, product=None, **kwargs):
        values = super()._get_reward_values_product(reward, coupon, product=product, **kwargs)
        offer = reward.program_id.sudo().ab_storefront_offer_id
        if offer and offer.offer_type == "gift":
            if self.website_id != offer.website_id or self.company_id != offer.company_id:
                raise UserError(_("This offer is not available for this website."))
            if offer.max_applications:
                for value in values:
                    value["product_uom_qty"] = min(value["product_uom_qty"], offer.max_applications * offer.gift_qty)
            if offer.second_item_mode == "choice" and values:
                total = int(values[0]["product_uom_qty"])
                requested = kwargs.get("gift_allocations")
                if requested is not None:
                    if not isinstance(requested, dict) or not requested or len(requested) > 100:
                        raise UserError(_("Choose the required number of gifts."))
                    allocations = {}
                    for product_id, quantity in requested.items():
                        if (
                            type(product_id) is not int or type(quantity) is not int
                            or quantity < 1 or product_id not in offer.second_product_ids.ids
                        ):
                            raise UserError(_("Choose eligible gift products and valid quantities."))
                        allocations[product_id] = quantity
                    if sum(allocations.values()) != total:
                        raise UserError(_("Choose exactly %(count)s gifts.", count=total))
                else:
                    existing = self.order_line.filtered(
                        lambda line: line.reward_id == reward and line.coupon_id == coupon
                        and line.product_id in offer.second_product_ids
                    )
                    allocations = {line.product_id.id: int(line.product_uom_qty) for line in existing}
                    if not allocations:
                        allocations = {values[0]["product_id"]: total}
                    remainder = total - sum(allocations.values())
                    if remainder > 0:
                        first_id = next(iter(allocations))
                        allocations[first_id] += remainder
                    elif remainder < 0:
                        for product_id in reversed(tuple(allocations)):
                            removed = min(allocations[product_id], -remainder)
                            allocations[product_id] -= removed
                            remainder += removed
                            if not allocations[product_id]:
                                del allocations[product_id]
                            if not remainder:
                                break
                base = values[0]
                values = [
                    {
                        **base,
                        "product_id": product_id,
                        "product_uom_qty": quantity,
                        "points_cost": base["points_cost"] if index == 0 else 0,
                    }
                    for index, (product_id, quantity) in enumerate(allocations.items())
                ]
        return values

    def _ab_applied_storefront_offers(self):
        self.ensure_one()
        offers = self.order_line.ab_storefront_price_offer_id.sudo()
        programs = self.order_line.filtered("is_reward_line").reward_id.program_id
        if programs:
            offers |= self.env["ab_storefront_offer"].sudo().with_context(active_test=False).search([
                "|", ("generated_program_ids", "in", programs.ids),
                "&", ("use_odoo_promotion", "=", True), ("program_id", "in", programs.ids),
            ])
        return offers

    def _ab_check_offer_eligibility(self, lock=False):
        capped_offers = self.env["ab_storefront_offer"].sudo()
        applied_by_order = {}
        for order in self:
            applied = order._ab_applied_storefront_offers()
            applied_by_order[order.id] = applied
            capped_offers |= applied.filtered(lambda offer: (
                offer.max_offer_units
                or offer.offer_type == "mix_discount" and (
                    offer.main_product_max_offer_units
                    or any(offer.collection_product_line_ids.mapped("max_offer_units"))
                )
            ))
        if lock:
            for offer in capped_offers.sorted("id"):
                if not offer.try_lock_for_update():
                    raise ValidationError(_("An offer is being confirmed in another order. Please try again."))
        pending_sales = defaultdict(float)
        pending_product_sales = defaultdict(float)
        for order in self:
            order.check_access("write")
            applied = applied_by_order[order.id]
            for offer in applied.filtered("max_offer_units"):
                if offer.website_id != order.website_id or offer.company_id != order.company_id:
                    raise ValidationError(_("This offer is no longer available for this order."))
                pending_sales[offer.id] += offer._paid_primary_quantity(order)
                if offer._sold_primary_quantity() + pending_sales[offer.id] > offer.max_offer_units:
                    raise ValidationError(_("This offer has reached its product sales limit. Reduce the quantity or update the cart."))
            for offer in applied.filtered(lambda current: current.offer_type == "mix_discount"):
                if offer.website_id != order.website_id or offer.company_id != order.company_id:
                    raise ValidationError(_("This offer is no longer available for this order."))
                for product in offer._qualifying_products():
                    limit = offer._product_offer_limit(product)
                    if not limit:
                        continue
                    quantity = sum(
                        line.product_uom_id._compute_quantity(
                            line.product_uom_qty, line.product_id.uom_id, round=False,
                        )
                        for line in order.order_line.filtered(lambda current: (
                            not current.is_reward_line and current.product_id == product
                            and current.product_uom_qty > 0
                        ))
                    )
                    key = (offer.id, product.id)
                    pending_product_sales[key] += quantity
                    if offer._sold_product_quantity(product) + pending_product_sales[key] > limit:
                        raise ValidationError(_(
                            "%(product)s has reached its allocation for this offer. Reduce its quantity or update the cart.",
                            product=product.display_name,
                        ))
            offers = applied.filtered("once_per_customer")
            if offers:
                if (
                    not order.website_id or not order.partner_id
                    or order.partner_id == order.website_id.sudo().user_id.partner_id
                    or any(offer.website_id != order.website_id or offer.company_id != order.company_id for offer in offers)
                ):
                    raise ValidationError(_("Sign in with an eligible customer account to use this offer."))
                if self.env["ab_storefront_offer_use"].sudo().search_count([
                    ("offer_id", "in", offers.ids),
                    ("partner_id", "=", order.partner_id.commercial_partner_id.id),
                    ("order_id", "!=", order.id),
                ]):
                    raise ValidationError(_("This customer has already used this offer. Update the cart before continuing."))

    def _get_program_domain(self):
        domain = fields.Domain(super()._get_program_domain())
        if self.website_id:
            excluded = self.env["ab_storefront_offer"]._unavailable_for_customer(
                self.website_id, self.partner_id, self,
            )
            programs = excluded.with_context(active_test=False).generated_program_ids | excluded.filtered("use_odoo_promotion").program_id
            domain &= fields.Domain("id", "not in", programs.ids)
        return domain

    def _check_cart_is_ready_to_be_paid(self):
        self._ab_check_offer_eligibility()
        return super()._check_cart_is_ready_to_be_paid()

    def action_confirm(self):
        self._ab_check_offer_eligibility(lock=True)
        result = super().action_confirm()
        for order in self.filtered(lambda current: current.state == "sale"):
            for offer in order._ab_applied_storefront_offers():
                uses = self.env["ab_storefront_offer_use"].sudo()
                existing = uses.search([
                    ("offer_id", "=", offer.id),
                    ("partner_id", "=", order.partner_id.commercial_partner_id.id),
                ])
                if existing and (not offer.once_per_customer or existing.order_id == order):
                    continue
                try:
                    with self.env.cr.savepoint():
                        uses.create({
                            "offer_id": offer.id,
                            "partner_id": order.partner_id.commercial_partner_id.id,
                            "order_id": order.id,
                        })
                except IntegrityError as error:
                    if error.diag.constraint_name != "ab_storefront_offer_use_offer_customer_unique":
                        raise
                    if offer.once_per_customer:
                        raise ValidationError(_("This customer has already used this offer. Update the cart before continuing.")) from error
        return result


class ProductPricelist(models.Model):
    _inherit = "product.pricelist"

    def _get_applicable_rules(self, products, date, **kwargs):
        rules = super()._get_applicable_rules(products, date, **kwargs)
        eligible_rules = self.env["product.pricelist.item"]
        for rule in rules:
            offer = rule.sudo().ab_storefront_offer_id
            if offer.offer_type == "amount" and (
                offer.currency_id != self.env.ref("base.EGP")
                or offer._fixed_discount_amount() > offer._maximum_fixed_discount()
            ):
                continue
            eligible_rules |= rule
        return eligible_rules.sorted(key=lambda rule: not rule.ab_storefront_offer_id)

    def _get_applicable_rules_domain(self, products, date, **kwargs):
        domain = fields.Domain(super()._get_applicable_rules_domain(products, date, **kwargs))
        website_id = kwargs.get("ab_storefront_website_id")
        if website_id is None:
            website_id = request.website.id if request and getattr(request, "website", False) else False
        domain &= (
            fields.Domain("ab_storefront_offer_id", "=", False)
            | fields.Domain("ab_storefront_offer_id", "any!", [
                ("active", "=", True),
                ("offer_type", "in", ["price", "percent", "amount"]),
                ("use_odoo_promotion", "=", False), ("website_id", "=", website_id),
            ])
        )
        website = self.env["website"].browse(website_id)
        if website:
            partner = kwargs.get("ab_storefront_partner")
            if partner is None:
                partner = self.env.user.partner_id
            excluded = self.env["ab_storefront_offer"]._unavailable_for_customer(
                website, partner, kwargs.get("ab_storefront_order"),
            )
            domain &= fields.Domain("ab_storefront_offer_id", "not in", excluded.ids)
        return domain


class ProductPricelistItem(models.Model):
    _inherit = "product.pricelist.item"

    ab_storefront_offer_id = fields.Many2one("ab_storefront_offer", copy=False, ondelete="restrict")

    def _show_discount_on_shop(self):
        return super()._show_discount_on_shop() or bool(self.sudo().ab_storefront_offer_id)

    def _compute_base_price(self, product, quantity, uom, date, currency, **kwargs):
        price = super()._compute_base_price(product, quantity, uom, date, currency, **kwargs)
        offer = self.sudo().ab_storefront_offer_id
        if offer.offer_type == "price":
            price = product.uom_id._compute_price(offer.price_before, uom)
            price = offer.currency_id._convert(price, currency, offer.company_id, date, round=False)
        return price

    def _compute_price(self, product, quantity, uom, date, currency=None, **kwargs):
        price = super()._compute_price(product, quantity, uom, date, currency, **kwargs)
        if self.sudo().ab_storefront_offer_id.offer_type == "amount":
            return max(0, price)
        return price


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    ab_storefront_mix_benefit_offer_id = fields.Many2one(
        "ab_storefront_offer", string="Applied Mix Offer Benefit", copy=False,
        ondelete="restrict", check_company=True, index=True,
    )
    ab_storefront_price_offer_id = fields.Many2one(
        "ab_storefront_offer", string="Applied Storefront Price Offer",
        compute="_compute_ab_storefront_price_offer", store=True,
        copy=False, ondelete="restrict", check_company=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        managed_fields = {"ab_storefront_price_offer_id", "ab_storefront_mix_benefit_offer_id"}
        if any(managed_fields & set(vals) for vals in vals_list) and not self.env.context.get("ab_storefront_manage_offer_lines"):
            raise AccessError(_("Applied offers are managed automatically."))
        return super().create(vals_list)

    def write(self, vals):
        if (
            {"ab_storefront_price_offer_id", "ab_storefront_mix_benefit_offer_id"} & set(vals)
            and not self.env.context.get("ab_storefront_manage_offer_lines")
        ):
            raise AccessError(_("Applied offers are managed automatically."))
        return super().write(vals)

    def copy_data(self, default=None):
        values_list = super().copy_data(default)
        for line, values in zip(self, values_list):
            if line.ab_storefront_price_offer_id.sudo().once_per_customer:
                for name in ("price_unit", "technical_price_unit", "discount"):
                    values.pop(name, None)
        return values_list

    @api.depends("price_unit", "discount", "product_id")
    def _compute_ab_storefront_price_offer(self):
        for line in self:
            line.ab_storefront_price_offer_id = line.pricelist_item_id.sudo().ab_storefront_offer_id

    def _get_pricelist_kwargs(self):
        return {
            **super()._get_pricelist_kwargs(),
            "ab_storefront_website_id": self.order_id.website_id.id,
            "ab_storefront_partner": self.order_id.partner_id,
            "ab_storefront_order": self.order_id,
        }
