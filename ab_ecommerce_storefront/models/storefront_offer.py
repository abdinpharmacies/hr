from math import isfinite

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.http import request


class StorefrontOffer(models.Model):
    _name = "ab_storefront_offer"
    _description = "Storefront Offer"
    _inherit = ["mail.thread"]
    _check_company_auto = True
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    sequence = fields.Integer(default=10)
    website_id = fields.Many2one(
        "website", required=True, ondelete="restrict", tracking=True,
        default=lambda self: self._default_offer_website(),
    )
    company_id = fields.Many2one(related="website_id.company_id", store=True)
    product_id = fields.Many2one(
        "product.product", required=True, ondelete="restrict", check_company=True,
        domain="[('sale_ok', '=', True), '|', ('website_id', '=', False), ('website_id', '=', website_id)]",
        tracking=True,
    )
    offer_type = fields.Selection(
        [("gift", "Buy X + Free Gifts"), ("price", "Before / After Price")],
        required=True, default="gift", tracking=True,
    )
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

    @api.onchange("product_id", "pricelist_id", "website_id")
    def _onchange_original_price(self):
        self.price_after = self.price_before

    @api.constrains(
        "website_id", "product_id", "offer_type", "buy_qty", "gift_qty", "pricelist_id",
        "price_before", "price_after", "date_from", "date_to", "use_odoo_promotion", "program_id", "active",
    )
    def _check_offer(self):
        other_offers = self.search([
            ("active", "=", True), ("website_id", "in", self.website_id.ids),
            ("product_id", "in", self.product_id.ids),
        ])
        for offer in self:
            if offer.date_from and offer.date_to and offer.date_to < offer.date_from:
                raise ValidationError(_("The end date must not precede the start date."))
            product = offer.product_id
            if (
                not product.sale_ok or product.product_tmpl_id.product_variant_count != 1
                or (product.website_id and product.website_id != offer.website_id)
            ):
                raise ValidationError(_("Select a single-variant sale product available on this website."))
            if offer.use_odoo_promotion:
                offer._check_linked_program()
            elif offer.offer_type == "gift":
                if offer.buy_qty < 1 or offer.gift_qty < 1:
                    raise ValidationError(_("Buy and free quantities must be positive whole numbers."))
            elif (
                not offer.pricelist_id or offer.pricelist_id.website_id != offer.website_id
                or not isfinite(offer.price_before) or not isfinite(offer.price_after)
                or offer.price_after <= 0 or offer.price_before <= offer.price_after
            ):
                raise ValidationError(_("Select a pricelist for this website and set a positive reduced price below the original price."))
            if offer.active:
                overlapping = other_offers.filtered(lambda other: (
                    other != offer and other.website_id == offer.website_id
                    and other.product_id == offer.product_id
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
        result = super().write(vals)
        if set(vals) & {
            "name", "active", "website_id", "product_id", "offer_type", "buy_qty", "gift_qty",
            "pricelist_id", "price_before", "price_after", "date_from", "date_to",
            "use_odoo_promotion", "program_id",
        }:
            self._sync_offer_rules()
        return result

    def _sync_offer_rules(self):
        self.check_access("write")
        if not self.env.su and self.company_id - self.env.companies:
            raise AccessError(_("You cannot manage offers outside your allowed companies."))
        self = self.sudo()
        for offer in self:
            programs = offer.with_context(active_test=False).generated_program_ids
            programs.write({"active": False})
            if offer.use_odoo_promotion or offer.offer_type != "gift":
                continue
            values = {
                "name": offer.name, "active": offer.active, "program_type": "buy_x_get_y",
                "company_id": offer.company_id.id, "website_id": offer.website_id.id,
                "sale_ok": False, "ecommerce_ok": True, "trigger": "auto", "applies_on": "current",
                "date_from": offer.date_from, "date_to": offer.date_to,
                "ab_storefront_offer_id": offer.id,
            }
            rule_values = {
                "mode": "auto", "minimum_qty": offer.buy_qty, "minimum_amount": 0,
                "reward_point_mode": "unit", "reward_point_amount": 1,
                "product_ids": [fields.Command.set(offer.product_id.ids)],
            }
            reward_values = {
                "reward_type": "product", "reward_product_id": offer.product_id.id,
                "reward_product_qty": offer.gift_qty, "required_points": offer.buy_qty,
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
        for offer in self.filtered(lambda rec: rec.offer_type == "price" and not rec.use_odoo_promotion):
            values = {
                "pricelist_id": offer.pricelist_id.id, "product_id": offer.product_id.id,
                "applied_on": "0_product_variant", "min_quantity": 0,
                "compute_price": "fixed", "base": "list_price", "fixed_price": offer.price_after,
                "date_start": offer.date_from,
                "date_end": fields.Datetime.to_datetime(offer.date_to).replace(hour=23, minute=59, second=59) if offer.date_to else False,
                "ab_storefront_offer_id": offer.id,
            }
            if offer.price_rule_ids:
                offer.price_rule_ids.write(values)
            else:
                self.env["product.pricelist.item"].create(values)


class LoyaltyProgram(models.Model):
    _inherit = "loyalty.program"

    ab_storefront_offer_id = fields.Many2one("ab_storefront_offer", copy=False, ondelete="restrict")


class ProductPricelist(models.Model):
    _inherit = "product.pricelist"

    def _get_applicable_rules(self, products, date, **kwargs):
        rules = super()._get_applicable_rules(products, date, **kwargs)
        return rules.sorted(key=lambda rule: not rule.ab_storefront_offer_id)

    def _get_applicable_rules_domain(self, products, date, **kwargs):
        domain = fields.Domain(super()._get_applicable_rules_domain(products, date, **kwargs))
        website_id = kwargs.get("ab_storefront_website_id")
        if website_id is None:
            website_id = request.website.id if request and getattr(request, "website", False) else False
        return domain & (
            fields.Domain("ab_storefront_offer_id", "=", False)
            | fields.Domain("ab_storefront_offer_id", "any!", [
                ("active", "=", True), ("offer_type", "=", "price"),
                ("use_odoo_promotion", "=", False), ("website_id", "=", website_id),
            ])
        )


class ProductPricelistItem(models.Model):
    _inherit = "product.pricelist.item"

    ab_storefront_offer_id = fields.Many2one("ab_storefront_offer", copy=False, ondelete="restrict")

    def _show_discount_on_shop(self):
        return super()._show_discount_on_shop() or bool(self.sudo().ab_storefront_offer_id)

    def _compute_base_price(self, product, quantity, uom, date, currency, **kwargs):
        price = super()._compute_base_price(product, quantity, uom, date, currency, **kwargs)
        offer = self.sudo().ab_storefront_offer_id
        if offer:
            price = product.uom_id._compute_price(offer.price_before, uom)
            price = offer.currency_id._convert(price, currency, offer.company_id, date, round=False)
        return price


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _get_pricelist_kwargs(self):
        return {
            **super()._get_pricelist_kwargs(),
            "ab_storefront_website_id": self.order_id.website_id.id,
        }
