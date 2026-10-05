from math import ceil, floor

from markupsafe import Markup
from werkzeug.urls import url_encode

from odoo import _, _lt, fields, models
from odoo.fields import Domain
from odoo.http import request


_CATEGORY_LABELS = {
    "medications": _lt("Medications"),
    "medicines": _lt("Medicines"),
    "pain relief": _lt("Pain Relief"),
    "digestive health": _lt("Digestive Health"),
    "respiratory care": _lt("Respiratory Care"),
    "allergy care": _lt("Allergy Care"),
    "brain & nervous system": _lt("Brain & Nervous System"),
    "heart & circulation": _lt("Heart & Circulation"),
    "hormones": _lt("Hormones"),
    "infections": _lt("Infections"),
    "kidney & urinary care": _lt("Kidney & Urinary Care"),
    "eye care medicines": _lt("Eye Care Medicines"),
    "ear care": _lt("Ear Care"),
    "mouth & throat": _lt("Mouth & Throat"),
    "skin medicines": _lt("Skin Medicines"),
    "women's health": _lt("Women's Health"),
    "men's health": _lt("Men's Health"),
    "specialty medicines": _lt("Specialty Medicines"),
    "vitamins": _lt("Vitamins"),
    "vitamins & supplements": _lt("Vitamins & Supplements"),
    "multivitamins": _lt("Multivitamins"),
    "minerals": _lt("Minerals"),
    "kids vitamins": _lt("Kids Vitamins"),
    "pregnancy supplements": _lt("Pregnancy Supplements"),
    "omega & eye supplements": _lt("Omega & Eye Supplements"),
    "beauty supplements": _lt("Beauty Supplements"),
    "weight management": _lt("Weight Management"),
    "herbal products": _lt("Herbal Products"),
    "personal care": _lt("Personal Care"),
    "bath & shower": _lt("Bath & Shower"),
    "oral care": _lt("Oral Care"),
    "deodorants": _lt("Deodorants"),
    "feminine care": _lt("Feminine Care"),
    "men's grooming": _lt("Men's Grooming"),
    "hair removal": _lt("Hair Removal"),
    "hygiene & household": _lt("Hygiene & Household"),
    "first aid": _lt("First Aid"),
    "health devices": _lt("Health Devices"),
    "health devices & supplies": _lt("Health Devices & Supplies"),
    "diagnostics": _lt("Diagnostics"),
    "patient care": _lt("Patient Care"),
    "mobility aids": _lt("Mobility Aids"),
    "orthopedics & supports": _lt("Orthopedics & Supports"),
    "wound care": _lt("Wound Care"),
    "fitness & sport": _lt("Fitness & Sport"),
    "beauty": _lt("Beauty"),
    "beauty & skin care": _lt("Beauty & Skin Care"),
    "face care": _lt("Face Care"),
    "body care": _lt("Body Care"),
    "sun care": _lt("Sun Care"),
    "hair care": _lt("Hair Care"),
    "skin treatment": _lt("Skin Treatment"),
    "makeup & nails": _lt("Makeup & Nails"),
    "perfumes": _lt("Perfumes"),
    "baby care": _lt("Baby Care"),
    "mother & baby": _lt("Mother & Baby"),
    "baby diapers & wipes": _lt("Baby Diapers & Wipes"),
    "baby feeding": _lt("Baby Feeding"),
    "baby nutrition": _lt("Baby Nutrition"),
    "baby toiletries": _lt("Baby Toiletries"),
    "baby accessories": _lt("Baby Accessories"),
    "mom care": _lt("Mom Care"),
    "wellness": _lt("Wellness"),
    "everyday essentials": _lt("Everyday Essentials"),
}

_CATEGORY_ICON_RULES = (
    (("first aid",), "fa-plus-square", "orange"),
    (("health device", "medical device", "equipment"), "fa-stethoscope", "blue"),
    (("medication", "medicine", "drug", "pharmacy"), "fa-medkit", "green"),
    (("vitamin", "supplement"), "fa-flask", "orange"),
    (("baby", "child"), "fa-child", "blue"),
    (("personal care", "beauty", "cosmetic"), "fa-heart", "orange"),
    (("wellness", "health"), "fa-leaf", "green"),
)

_CATEGORY_ICON_FALLBACKS = (
    ("fa-medkit", "green"),
    ("fa-heartbeat", "orange"),
    ("fa-leaf", "blue"),
)

_HEADER_NEED_MENU = (
    ('acne_treatment', _lt("Acne treatment"), "fa-medkit", "green"),
    ('skin_brightening', _lt("Skin brightening and tone correction"), "fa-sun-o", "orange"),
    ('dry_skin_hydration', _lt("Dry skin hydration"), "fa-tint", "blue"),
    ('hair_loss_treatment', _lt("Hair loss treatment"), "fa-leaf", "green"),
    ('dandruff_control', _lt("Dandruff control"), "fa-shield", "blue"),
    ('sun_protection', _lt("Sun protection"), "fa-sun-o", "orange"),
    ('anti_aging', _lt("Anti-aging and wrinkle care"), "fa-heart", "orange"),
    ('immune_support', _lt("Immune support"), "fa-plus-square", "green"),
    ('energy_vitality', _lt("Energy and vitality"), "fa-bolt", "orange"),
    ('sensitive_skin', _lt("Sensitive skin care"), "fa-heart-o", "blue"),
)


class Website(models.Model):
    _inherit = "website"

    def _control_third_party_trackers_in_html(self, html):
        return Markup(html or "")

    @staticmethod
    def _ab_storefront_category_source_name(category):
        category.ensure_one()
        return (category.with_context(lang=False).name or category.name or "").strip()

    def _ab_storefront_category_label(self, category):
        """Return a translated label for the initial storefront categories.

        User-maintained record translations still take precedence.  The fallback
        labels cover the initial categories, which were created without XML IDs
        and therefore cannot receive portable record translations from a PO file.
        """
        self.ensure_one()
        category.ensure_one()
        source_name = self._ab_storefront_category_source_name(category)
        translated_name = (category.name or "").strip()
        if translated_name and translated_name != source_name:
            return translated_name
        label = _CATEGORY_LABELS.get(source_name.casefold())
        return self.env._(label) if label else translated_name or source_name

    def _ab_storefront_category_presentation(self, category):
        self.ensure_one()
        category.ensure_one()
        source_name = self._ab_storefront_category_source_name(category).casefold()
        for keywords, icon, tone in _CATEGORY_ICON_RULES:
            if any(keyword in source_name for keyword in keywords):
                return {"icon": icon, "tone": tone}
        fallback_index = (category.id - 1) % len(_CATEGORY_ICON_FALLBACKS)
        icon, tone = _CATEGORY_ICON_FALLBACKS[fallback_index]
        return {"icon": icon, "tone": tone}

    def _ab_storefront_categories(self, limit=8):
        self.ensure_one()
        domain = self.website_domain() & fields.Domain("parent_id", "=", False)
        domain &= fields.Domain("has_published_products", "=", True)
        return self.env["product.public.category"].with_context(bin_size=True).search(
            domain,
            order="sequence, name, id",
            limit=limit,
        )

    def _ab_storefront_header_nav_labels(self):
        self.ensure_one()
        return {
            "home": self.env._("Home"),
            "offers": self.env._("Offers"),
            "offers_aria": self.env._("Offers and discounts"),
            "prescription": self.env._("Order by prescription"),
            "account": self.env._("My account"),
            "signin": self.env._("Sign in"),
            "wishlist": self.env._("Wishlist"),
            "track_order": self.env._("Track order"),
            "your_orders": self.env._("Your orders"),
            "store": self.env._("Store navigation"),
            "category": self.env._("Shop by Category"),
            "need": self.env._("Shop by Need"),
        }

    def _ab_storefront_location_label(self, location_name=False):
        self.ensure_one()
        if location_name:
            return self.env._("Deliver to %s") % location_name
        return self.env._("Your current area")

    def _ab_storefront_header_category_menu(self):
        self.ensure_one()
        menu = []
        for category in self._ab_storefront_categories(limit=8):
            presentation = self._ab_storefront_category_presentation(category)
            menu.append({
                "label": self._ab_storefront_category_label(category),
                "href": "/shop/category/%s" % self.env["ir.http"]._slug(category),
                "icon": presentation["icon"],
                "tone": presentation["tone"],
            })
        return menu

    def _ab_storefront_header_need_menu(self):
        self.ensure_one()
        return [
            {
                "label": self.env._(label),
                "href": "/shop?%s" % url_encode({
                    "need": key,
                }),
                "icon": icon,
                "tone": tone,
            }
            for key, label, icon, tone in _HEADER_NEED_MENU
        ]

    def _ab_storefront_is_first_cart_addition(self):
        self.ensure_one()
        if self.is_public_user():
            return False
        partner = self.env.user.partner_id
        if partner.ab_storefront_has_cart_history:
            return False
        prior_line = self.env["sale.order.line"].sudo().search([
            ("order_id.partner_id", "=", partner.id),
            ("order_id.website_id", "=", self.id),
            ("product_id", "!=", False),
            ("display_type", "=", False),
        ], limit=1)
        return not prior_line

    def _ab_storefront_is_first_wishlist_addition(self):
        self.ensure_one()
        if self.is_public_user():
            return False
        partner = self.env.user.partner_id
        if partner.ab_storefront_has_wishlist_history:
            return False
        prior_wish = self.env["product.wishlist"].with_context(active_test=False).sudo().search([
            ("partner_id", "=", partner.id),
            ("website_id", "=", self.id),
        ], limit=1)
        return not prior_wish

    def _ab_storefront_home_catalog(self, product_limit=8, category_limit=8, offers_offset=0):
        self.ensure_one()
        categories = self._ab_storefront_categories(limit=category_limit)
        candidate_limit = max(product_limit * 8, 32)
        candidates = self.env["product.template"].with_context(bin_size=True).search(
            self.sale_product_domain(),
            order="website_sequence, id DESC",
            limit=candidate_limit,
        )
        prices = candidates._get_sales_prices(self)
        offers, offer_prices, has_more_offers = self._ab_storefront_offer_catalog(
            product_limit, offers_offset
        )
        prices.update(offer_prices)
        best_sellers = candidates[:product_limit]
        displayed_products = best_sellers | offers
        category_ids = set(categories.ids)
        category_products = {}
        for product in candidates:
            for category in product.public_categ_ids.parents_and_self:
                if category.id in category_ids and category.id not in category_products:
                    category_products[category.id] = product
        variant_ids = [
            product._get_first_possible_variant_id()
            for product in displayed_products
        ]
        variants = self.env["product.product"].sudo().browse([
            variant_id
            for variant_id in variant_ids
            if variant_id
        ])
        variants_by_template = {
            variant.product_tmpl_id.id: variant
            for variant in variants
        }
        wishlist_product_ids = set(
            self.env["product.wishlist"].current().product_id.ids
        )
        return {
            "categories": categories,
            "category_products": category_products,
            "products": best_sellers,
            "best_sellers": best_sellers,
            "offers": offers,
            "has_more_offers": has_more_offers,
            "prices": prices,
            "variants": variants_by_template,
            "offer_product_ids": set(offers.ids),
            "wishlist_product_ids": wishlist_product_ids,
        }

    def _ab_storefront_offer_catalog(self, limit=8, offset=0):
        self.ensure_one()
        products = self.env["product.template"].with_context(bin_size=True)
        domain = Domain.AND([self.sale_product_domain(), self._ab_storefront_offer_candidate_domain()])
        offers = products.browse()
        prices = {}
        position = 0
        while len(offers) <= offset + limit:
            candidates = products.search(
                domain, order="website_sequence, id DESC",
                offset=position, limit=128,
            )
            if not candidates:
                break
            batch_prices = candidates._get_sales_prices(self)
            offers |= candidates.filtered(
                lambda product: batch_prices[product.id].get("ab_offer")
                or batch_prices[product.id].get("base_price", 0)
                > batch_prices[product.id]["price_reduce"]
            )
            prices.update(batch_prices)
            position += len(candidates)
        displayed = offers[offset:offset + limit]
        return displayed, {product.id: prices[product.id] for product in displayed}, len(offers) > offset + limit

    def _ab_storefront_offer_candidate_domain(self):
        domains = [Domain("compare_list_price", ">", 0)]
        programs = self.env["loyalty.program"].sudo().search(self._ab_storefront_offer_program_domain())
        for program in programs:
            if program.limit_usage and program.total_order_count >= program.max_usage:
                continue
            rewards = program.reward_ids.filtered("active")
            if len(rewards) != 1:
                continue
            reward = rewards
            if reward.reward_type == "product":
                reward_domain = Domain("product_variant_ids", "in", reward.reward_product_ids.ids)
            elif reward.discount_applicability == "specific":
                reward_domain = Domain("product_variant_ids", "any", reward._get_discount_product_domain())
            else:
                continue
            for rule in program.rule_ids.filtered(lambda rule: rule.active and rule.mode == "auto"):
                domains.append(reward_domain & Domain("product_variant_ids", "any", rule._get_valid_product_domain()))
        pricelist = getattr(request, "pricelist", False) if request else False
        now = fields.Datetime.now()
        if pricelist:
            for item in pricelist.sudo().item_ids:
                if (
                    not item._show_discount_on_shop() or item.min_quantity > 1
                    or (item.date_start and item.date_start > now)
                    or (item.date_end and item.date_end < now)
                ):
                    continue
                if item.product_id:
                    domains.append(Domain("product_variant_ids", "in", item.product_id.ids))
                elif item.product_tmpl_id:
                    domains.append(Domain("id", "in", item.product_tmpl_id.ids))
                elif item.categ_id:
                    domains.append(Domain("categ_id", "child_of", item.categ_id.ids))
                else:
                    return Domain.TRUE
        return Domain.OR(domains)

    def _ab_storefront_offer_details(self, candidates):
        self.ensure_one()
        if not candidates:
            return {}

        programs = self.env["loyalty.program"].sudo().search(
            self._ab_storefront_offer_program_domain()
        )
        candidate_variants = candidates.product_variant_ids
        details = {}
        for program in programs:
            if program.limit_usage and program.total_order_count >= program.max_usage:
                continue
            rules = program.rule_ids.filtered(lambda rule: rule.active and rule.mode == "auto")
            rewards = program.reward_ids.filtered("active")
            for rule in rules:
                eligible = candidate_variants.filtered_domain(rule._get_valid_product_domain())
                if not eligible or len(rewards) != 1:
                    continue
                reward = rewards
                if reward.reward_type == "product":
                    if (
                        len(rules) != 1 or rule.minimum_amount
                        or rule.reward_point_mode != "unit" or reward.multi_product
                    ):
                        continue
                    eligible &= reward.reward_product_ids
                    buy_qty = ceil(reward.required_points / rule.reward_point_amount)
                    if rule.minimum_qty > buy_qty:
                        continue
                    reward_count = 1 if reward.clear_wallet else floor(
                        buy_qty * rule.reward_point_amount / reward.required_points
                    )
                    offer = {"buy_qty": buy_qty, "free_qty": reward.reward_product_qty * reward_count}
                elif reward.discount_applicability == "specific":
                    eligible = eligible.filtered_domain(reward._get_discount_product_domain())
                    offer = {"program_id": program.id}
                else:
                    continue
                for product in eligible.product_tmpl_id:
                    if product.product_variant_count == 1:
                        if offer.get("free_qty") or product.id not in details:
                            details[product.id] = offer
        return details

    def _ab_storefront_offer_program_domain(self):
        self.ensure_one()
        today = fields.Date.context_today(self)
        domain = [
            ("active", "=", True),
            ("ecommerce_ok", "=", True),
            ("program_type", "in", ["promotion", "buy_x_get_y"]),
            ("trigger", "=", "auto"),
            ("applies_on", "=", "current"),
            *self.env["loyalty.program"]._check_company_domain(
                [self.company_id.id, self.company_id.parent_id.id]
            ),
            "|",
                ("website_id", "=", False),
                ("website_id", "=", self.id),
            "|",
                ("date_from", "=", False),
                ("date_from", "<=", today),
            "|",
                ("date_to", "=", False),
                ("date_to", ">=", today),
        ]
        try:
            pricelist = getattr(request, "pricelist", False)
        except RuntimeError:
            pricelist = False
        if pricelist:
            domain = Domain.AND([
                domain,
                [
                    "|",
                        ("pricelist_ids", "=", False),
                        ("pricelist_ids", "in", [pricelist.id]),
                ],
            ])
        return domain

    def _ab_storefront_carousel_slides(self):
        self.ensure_one()
        domain = fields.Domain("active", "=", True)
        domain &= fields.Domain("image_1920", "!=", False)
        domain &= fields.Domain("website_id", "=", False) | fields.Domain("website_id", "=", self.id)
        return self.env["ab_website_carousel_slide"].sudo().search(
            domain,
            order="sequence, id",
        )

    def _ab_storefront_customer_testimonials(self):
        self.ensure_one()
        domain = fields.Domain("active", "=", True)
        domain &= fields.Domain("image_1920", "!=", False)
        domain &= fields.Domain("website_id", "=", False) | fields.Domain("website_id", "=", self.id)
        return self.env["ab_ecommerce_customer_testimonial"].sudo().search(
            domain,
            order="sequence, id",
        )
