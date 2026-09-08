from markupsafe import Markup
from werkzeug.urls import url_encode

from odoo import _, _lt, fields, models


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

_HEADER_CATEGORY_MENU = (
    {
        "label": _lt("Skin Care"),
        "label_ar": "العناية بالبشرة",
        "aliases": ("skin care", "beauty & skin care", "face care", "beauty"),
        "icon": "fa-heart",
        "tone": "orange",
    },
    {
        "label": _lt("Hair Care"),
        "label_ar": "العناية بالشعر",
        "aliases": ("hair care", "personal care"),
        "icon": "fa-leaf",
        "tone": "green",
    },
    {
        "label": _lt("Body Care"),
        "label_ar": "العناية بالجسم",
        "aliases": ("body care", "bath & shower", "personal care"),
        "icon": "fa-heart",
        "tone": "orange",
    },
    {
        "label": _lt("Dietary Supplements"),
        "label_ar": "المكملات الغذائية",
        "aliases": ("dietary supplements", "vitamins & supplements", "vitamins", "wellness"),
        "icon": "fa-flask",
        "tone": "orange",
    },
    {
        "label": _lt("Vitamins and Minerals"),
        "label_ar": "الفيتامينات والمعادن",
        "aliases": ("vitamins and minerals", "vitamins & supplements", "vitamins", "minerals"),
        "icon": "fa-plus-square",
        "tone": "green",
    },
    {
        "label": _lt("Baby Care"),
        "label_ar": "العناية بالأطفال",
        "aliases": ("baby care", "baby toiletries", "baby accessories"),
        "icon": "fa-child",
        "tone": "blue",
    },
    {
        "label": _lt("Oral and Dental Care"),
        "label_ar": "العناية بالفم والأسنان",
        "aliases": ("oral and dental care", "oral care", "mouth & throat", "personal care"),
        "icon": "fa-smile-o",
        "tone": "blue",
    },
    {
        "label": _lt("Personal Care"),
        "label_ar": "العناية الشخصية",
        "aliases": ("personal care", "hygiene & household"),
        "icon": "fa-heart",
        "tone": "orange",
    },
    {
        "label": _lt("Medical Devices and Supplies"),
        "label_ar": "الأجهزة والمستلزمات الطبية",
        "aliases": ("medical devices and supplies", "health devices & supplies", "health devices"),
        "icon": "fa-stethoscope",
        "tone": "blue",
    },
    {
        "label": _lt("Mother and Baby Products"),
        "label_ar": "منتجات الأم والرضيع",
        "aliases": ("mother and baby products", "mother & baby", "mom care", "baby care"),
        "icon": "fa-child",
        "tone": "blue",
    },
)

_HEADER_NEED_MENU = (
    (_lt("Acne treatment"), "علاج حب الشباب", "fa-medkit", "green"),
    (_lt("Skin brightening and tone correction"), "تفتيح وتوحيد لون البشرة", "fa-sun-o", "orange"),
    (_lt("Dry skin hydration"), "ترطيب البشرة الجافة", "fa-tint", "blue"),
    (_lt("Hair loss treatment"), "علاج تساقط الشعر", "fa-leaf", "green"),
    (_lt("Dandruff control"), "مكافحة القشرة", "fa-shield", "blue"),
    (_lt("Sun protection"), "الحماية من الشمس", "fa-sun-o", "orange"),
    (_lt("Anti-aging and wrinkle care"), "مكافحة التجاعيد وعلامات التقدم في السن", "fa-heart", "orange"),
    (_lt("Immune support"), "تقوية المناعة", "fa-plus-square", "green"),
    (_lt("Energy and vitality"), "زيادة الطاقة والنشاط", "fa-bolt", "orange"),
    (_lt("Sensitive skin care"), "العناية بالبشرة الحساسة", "fa-heart-o", "blue"),
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
        return str(label) if label else translated_name or source_name

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

    def _ab_storefront_is_arabic(self):
        return (self.env.lang or "").split("_", 1)[0] == "ar"

    def _ab_storefront_header_nav_labels(self):
        self.ensure_one()
        if self._ab_storefront_is_arabic():
            return {
                "category": "التسوق حسب التصنيف",
                "need": "التسوق حسب الاحتياج",
            }
        return {
            "category": "Shop by Category",
            "need": "Shop by Need",
        }

    def _ab_storefront_header_category_menu(self):
        self.ensure_one()
        domain = self.website_domain()
        domain &= fields.Domain("has_published_products", "=", True)
        categories = self.env["product.public.category"].with_context(bin_size=True).search(
            domain,
            order="sequence, name, id",
        )
        categories_by_name = {
            self._ab_storefront_category_source_name(category).casefold(): category
            for category in categories
        }
        items = []
        is_arabic = self._ab_storefront_is_arabic()
        for item in _HEADER_CATEGORY_MENU:
            label = item["label_ar"] if is_arabic else _(str(item["label"]))
            category = False
            for alias in item["aliases"]:
                category = categories_by_name.get(alias.casefold())
                if category:
                    break
            href = (
                "/shop/category/%s" % self.env["ir.http"]._slug(category)
                if category
                else "/shop?%s" % url_encode({"search": label})
            )
            items.append({
                "label": label,
                "href": href,
                "icon": item["icon"],
                "tone": item["tone"],
            })
        return items

    def _ab_storefront_header_need_menu(self):
        self.ensure_one()
        return [
            {
                "label": label_ar if self._ab_storefront_is_arabic() else _(str(label)),
                "href": "/shop?%s" % url_encode({
                    "search": label_ar if self._ab_storefront_is_arabic() else _(str(label)),
                }),
                "icon": icon,
                "tone": tone,
            }
            for label, label_ar, icon, tone in _HEADER_NEED_MENU
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

    def _ab_storefront_home_catalog(self, product_limit=8, category_limit=8):
        self.ensure_one()
        categories = self._ab_storefront_categories(limit=category_limit)
        candidate_limit = max(product_limit * 8, 32)
        candidates = self.env["product.template"].with_context(bin_size=True).search(
            self.sale_product_domain(),
            order="website_sequence, id DESC",
            limit=candidate_limit,
        )
        prices = candidates._get_sales_prices(self)
        offers = candidates.filtered(
            lambda product: (
                prices.get(product.id, {}).get("base_price", 0)
                > prices.get(product.id, {}).get("price_reduce", 0)
            )
            or product.website_ribbon_id
        )[:product_limit]
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
            "prices": prices,
            "variants": variants_by_template,
            "wishlist_product_ids": wishlist_product_ids,
        }

    def _ab_storefront_carousel_slides(self):
        self.ensure_one()
        domain = fields.Domain("active", "=", True)
        domain &= fields.Domain("image_1920", "!=", False)
        domain &= fields.Domain("website_id", "=", False) | fields.Domain("website_id", "=", self.id)
        return self.env["ab_website_carousel_slide"].sudo().search(
            domain,
            order="sequence, id",
        )
