import base64
import logging
import os
import re

from psycopg2 import IntegrityError

from odoo import _, api, fields, models
from odoo.exceptions import UserError, AccessError, ValidationError
from odoo.tools import html_escape

_logger = logging.getLogger(__name__)
WEBSITE_SYNC_CHUNK_SIZE = 250


def website_sync_changed_values(record, values):
    changes = {}
    for name, value in values.items():
        field = record._fields[name]
        if field.type == "many2many":
            if len(value) != 1 or value[0][0] != fields.Command.SET:
                changes[name] = value
            elif set(record[name].ids) != set(value[0][2]):
                changes[name] = value
        elif field.type == "many2one":
            if record[name].id != (value or False):
                changes[name] = value
        elif record[name] != field.convert_to_record(field.convert_to_cache(value, record), record):
            changes[name] = value
    return changes

DEFAULT_WEBSITE_IMAGE_DIRECTORY = "/opt/odoo19/product_images"
WEBSITE_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp")
WEBSITE_PLACEHOLDER_IMAGE_PATH = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "static",
        "src",
        "img",
        "placeholders",
        "product_placeholder.jpeg",
    )
)

WEBSITE_CATEGORY_TRANSLATIONS = {
    "Medicines": "الأدوية",
    "Pain Relief": "مسكنات الألم",
    "Digestive Health": "صحة الجهاز الهضمي",
    "Respiratory Care": "الجهاز التنفسي",
    "Allergy Care": "الحساسية",
    "Brain & Nervous System": "المخ والجهاز العصبي",
    "Heart & Circulation": "القلب والدورة الدموية",
    "Hormones": "الهرمونات",
    "Infections": "العدوى والمضادات",
    "Kidney & Urinary Care": "الكلى والمسالك البولية",
    "Eye Care Medicines": "أدوية العيون",
    "Ear Care": "العناية بالأذن",
    "Mouth & Throat": "الفم والحلق",
    "Skin Medicines": "أدوية الجلد",
    "Women's Health": "صحة المرأة",
    "Men's Health": "صحة الرجل",
    "Specialty Medicines": "أدوية متخصصة",
    "Vitamins & Supplements": "الفيتامينات والمكملات",
    "Multivitamins": "مالتي فيتامين",
    "Minerals": "المعادن",
    "Kids Vitamins": "فيتامينات الأطفال",
    "Pregnancy Supplements": "مكملات الحمل والرضاعة",
    "Omega & Eye Supplements": "أوميجا ومكملات العين",
    "Beauty Supplements": "مكملات البشرة والشعر والأظافر",
    "Weight Management": "إدارة الوزن",
    "Herbal Products": "منتجات عشبية",
    "Beauty & Skin Care": "الجمال والعناية بالبشرة",
    "Face Care": "العناية بالوجه",
    "Body Care": "العناية بالجسم",
    "Sun Care": "العناية من الشمس",
    "Hair Care": "العناية بالشعر",
    "Skin Treatment": "علاج مشاكل البشرة",
    "Makeup & Nails": "المكياج والأظافر",
    "Perfumes": "العطور",
    "Personal Care": "العناية الشخصية",
    "Bath & Shower": "الاستحمام والدش",
    "Oral Care": "العناية بالفم والأسنان",
    "Deodorants": "مزيلات العرق",
    "Feminine Care": "العناية النسائية",
    "Men's Grooming": "عناية الرجل",
    "Hair Removal": "إزالة الشعر",
    "Hygiene & Household": "النظافة والمنزل",
    "Mother & Baby": "الأم والطفل",
    "Baby Diapers & Wipes": "حفاضات ومناديل الطفل",
    "Baby Feeding": "تغذية وإرضاع الطفل",
    "Baby Nutrition": "تغذية الطفل",
    "Baby Toiletries": "عناية واستحمام الطفل",
    "Baby Accessories": "إكسسوارات الطفل",
    "Mom Care": "عناية الأم",
    "Health Devices & Supplies": "الأجهزة والمستلزمات الصحية",
    "Diagnostics": "أجهزة وشرائط القياس",
    "Patient Care": "رعاية المريض بالمنزل",
    "Mobility Aids": "مساعدات الحركة",
    "Orthopedics & Supports": "العظام والدعامات",
    "Wound Care": "العناية بالجروح",
    "Fitness & Sport": "اللياقة والرياضة",
    "First Aid": "الإسعافات الأولية",
    "Everyday Essentials": "الاحتياجات اليومية",
}

WEBSITE_CATEGORY_RULES = (
    (("analgesic", "pain", "inflamation", "inflammation", "muscle spasm", "gout"), ("Medicines", "Pain Relief")),
    (("acidity", "heart burn", "hyperacidity", "colon", "constipation", "diarrhea", "digestion", "liver", "ulcer", "vomiting", "digestive"), ("Medicines", "Digestive Health")),
    (("respiratory", "asthma", "breathing", "cough", "cold", "sinusitis", "nasal congestion", "nasal wash", "nose"), ("Medicines", "Respiratory Care")),
    (("allergy",), ("Medicines", "Allergy Care")),
    (("brain", "nervous", "alzheimer", "anxiety", "insomnia", "depression", "epilepsy", "parkinson", "psychosis", "hypnotic", "local anesthesia"), ("Medicines", "Brain & Nervous System")),
    (("heart", "blood vessel", "bleeding", "blood clot", "cholesterol", "triglyceride", "hypertension", "hypotension", "vascular"), ("Medicines", "Heart & Circulation")),
    (("hormone", "fertility", "growth hormone", "thyroid"), ("Medicines", "Hormones")),
    (("infection", "anti-biotic", "antibiotic", "fungi", "fungal", "malaria", "virus", "worm"), ("Medicines", "Infections")),
    (("kidney", "urinary", "uti", "stones"), ("Medicines", "Kidney & Urinary Care")),
    (("eye allergy", "eye disease", "eye dryness", "eye infection"), ("Medicines", "Eye Care Medicines")),
    (("ear", "ear inflammation", "ear pain", "ear wax"), ("Medicines", "Ear Care")),
    (("mouth", "throat", "gum", "ulcer", "mouth wash", "gargle", "sore throat"), ("Medicines", "Mouth & Throat")),
    (("acne", "skin infection", "skin rash", "wounds", "burns and scars", "skin /"), ("Medicines", "Skin Medicines")),
    (("contraceptive", "pregnancy and lactation", "vaginal", "women's health"), ("Medicines", "Women's Health")),
    (("erection", "premature ejaculation", "prostate", "sexual tonic", "men's health"), ("Medicines", "Men's Health")),
    (("cancer", "oncology", "corticosteroid", "rheumatoid", "vaccine", "hemorrhoid", "low immunity", "laboratory preparations", "infusion"), ("Medicines", "Specialty Medicines")),
    (("multivitamin", "man and woman"), ("Vitamins & Supplements", "Multivitamins")),
    (("mineral", "calcium", "iron", "zinc", "zink"), ("Vitamins & Supplements", "Minerals")),
    (("babies", "children", "kids gumm", "kids syrup"), ("Vitamins & Supplements", "Kids Vitamins")),
    (("pregnancy supplement",), ("Vitamins & Supplements", "Pregnancy Supplements")),
    (("omega", "fish oil", "eye supplement"), ("Vitamins & Supplements", "Omega & Eye Supplements")),
    (("skin and hair and nails", "colla", "collagen"), ("Vitamins & Supplements", "Beauty Supplements")),
    (("weight gain", "weight loss", "chromax cut"), ("Vitamins & Supplements", "Weight Management")),
    (("herbal",), ("Vitamins & Supplements", "Herbal Products")),
    (("vitamin", "supplement", "d3"), ("Vitamins & Supplements",)),
    (("face care", "cleanser", "face mask", "freshness", "moisturizer", "toner", "whiten"), ("Beauty & Skin Care", "Face Care")),
    (("body care", "body care l3", "scrub", "body care products"), ("Beauty & Skin Care", "Body Care")),
    (("sun protection", "sun tan", "sun", "photoderm"), ("Beauty & Skin Care", "Sun Care")),
    (("hair care", "hair dye", "dyeing", "dyes", "henna", "hair nourishment", "hair mask", "hair oil", "hair serum", "hair styling", "hair treatment", "anti lice", "antidandruff", "hair loss", "hair straightener", "shampoo", "conditioner", "colored hair", "curly hair", "dry hair", "normal hair", "oily hair", "straightened hair"), ("Beauty & Skin Care", "Hair Care")),
    (("skin treatment", "burns", "scars", "wrinkles", "lip care", "eye care"), ("Beauty & Skin Care", "Skin Treatment")),
    (("make-up", "makeup", "nail", "lashes", "brows"), ("Beauty & Skin Care", "Makeup & Nails")),
    (("perfume", "scent"), ("Beauty & Skin Care", "Perfumes")),
    (("bath", "shower", "soap", "hand wash", "shower gel", "bath accessories"), ("Personal Care", "Bath & Shower")),
    (("oral", "breath", "dental", "toothbrush", "mouthwash", "toothpaste"), ("Personal Care", "Oral Care")),
    (("deod", "antiperspirant", "body freshener", "body splash", "roll on", "scented powder"), ("Personal Care", "Deodorants")),
    (("woman care", "intimate care", "sanitary", "carefree", "molped"), ("Personal Care", "Feminine Care")),
    (("men care", "men grooming"), ("Personal Care", "Men's Grooming")),
    (("hair remover", "hair removal"), ("Personal Care", "Hair Removal")),
    (("hygenic", "hygienic", "household", "air freshener", "antiseptic", "batteries", "papers", "tissues", "pests control", "medical soap"), ("Personal Care", "Hygiene & Household")),
    (("baby diaper", "baby nappies", "baby wipes", "training pants", "molfix", "good care"), ("Mother & Baby", "Baby Diapers & Wipes")),
    (("baby feeding", "breast feeding"), ("Mother & Baby", "Baby Feeding")),
    (("baby food", "growing up milk", "infant milk"), ("Mother & Baby", "Baby Nutrition")),
    (("baby toiletr", "baby grooming"), ("Mother & Baby", "Baby Toiletries")),
    (("baby accessories", "baby safety", "baby toys", "baby travel", "general accessories"), ("Mother & Baby", "Baby Accessories")),
    (("mom care", "maternity"), ("Mother & Baby", "Mom Care")),
    (("diagnostic", "glucose", "tests"), ("Health Devices & Supplies", "Diagnostics")),
    (("home patient", "bath room safety", "geriatric", "compress", "pillow", "cushion"), ("Health Devices & Supplies", "Patient Care")),
    (("mobility", "walking aid", "wheel chair"), ("Health Devices & Supplies", "Mobility Aids")),
    (("orthopedic", "osteoporosis", "joint health", "body support", "support"), ("Health Devices & Supplies", "Orthopedics & Supports")),
    (("wound care",), ("Health Devices & Supplies", "Wound Care")),
    (("fittness", "fitness", "sport", "massager", "sport tools"), ("Health Devices & Supplies", "Fitness & Sport")),
    (("first aid",), ("First Aid",)),
    (("accu chek", "accu-chek", "one touch", "onetouch", "glucose", "test strips", "lancets", "جهاز سكر", "جهاز قياس سكر"), ("Health Devices & Supplies", "Diagnostics")),
    (("belt", "brace", "support", "collar", "knee", "wrist", "حزام", "دعامة", "ركبة", "رقبة", "رست", "ساند"), ("Health Devices & Supplies", "Orthopedics & Supports")),
    (("shampoo", "conditioner", "hair", "زيت شعر", "فرشة شعر"), ("Beauty & Skin Care", "Hair Care")),
    (("shower gel", "soap", "cotton pads", "tissues"), ("Personal Care", "Bath & Shower")),
    (("perfume", "spray 250ml"), ("Beauty & Skin Care", "Perfumes")),
    (("cream", "lotion", "gel", "serum"), ("Beauty & Skin Care", "Skin Treatment")),
    ((" mg ", " tab", " cap", " vial", " supp", " oral drop", " eff", " sachet", " suspension", " syrup"), ("Medicines",)),
)

WEBSITE_CATEGORY_TOP_LEVEL = {
    "medicine": ("Medicines",),
    "medicines": ("Medicines",),
    "medical soap": ("Personal Care", "Hygiene & Household"),
    "vitamins and supplements": ("Vitamins & Supplements",),
    "vitamins": ("Vitamins & Supplements",),
    "beauty care": ("Beauty & Skin Care",),
    "beauty": ("Beauty & Skin Care",),
    "skin care": ("Beauty & Skin Care",),
    "personal care": ("Personal Care",),
    "mom and baby care": ("Mother & Baby",),
    "baby care": ("Mother & Baby",),
    "medical supplies": ("Health Devices & Supplies",),
    "health devices": ("Health Devices & Supplies",),
    "everyday essentials": ("Everyday Essentials",),
}


class AbProductGroup(models.Model):
    _inherit = "ab_product_group"

    website_public_category_id = fields.Many2one(
        "product.public.category",
        string="Website Category",
        copy=False,
        readonly=True,
        groups="base.group_user",
    )
    website_sync_group_path = fields.Char(
        string="Website Sync Group Path", compute="_compute_website_sync_group_path",
        store=True, recursive=True,
    )

    @api.depends("name", "code", "parent_id.website_sync_group_path")
    def _compute_website_sync_group_path(self):
        for group in self:
            group.website_sync_group_path = " / ".join(filter(None, [
                group.parent_id.website_sync_group_path, group.name or group.code,
            ]))

    def _get_or_create_website_categories(self, sync_cache=None):
        categories = self.env["product.public.category"].sudo()
        for group in self:
            categories |= group._get_or_create_website_category(sync_cache=sync_cache)
        if not categories:
            categories = self._get_or_create_canonical_website_category(("Everyday Essentials",), sync_cache=sync_cache)
        return categories

    def _get_or_create_website_category(self, sync_cache=None):
        self.ensure_one()
        if sync_cache is not None and self.id in sync_cache["groups"]:
            return sync_cache["groups"][self.id]
        category_path = self._get_canonical_website_category_path()
        if category_path:
            category = self._get_or_create_canonical_website_category(category_path, sync_cache=sync_cache)
            if self.website_public_category_id != category:
                self.sudo().website_public_category_id = category.id
            if sync_cache is not None:
                sync_cache["groups"][self.id] = category
            return category
        category = self.env["product.public.category"].sudo()
        if sync_cache is not None:
            sync_cache["groups"][self.id] = category
        return category

    @api.model
    def _normalize_website_category_text(self, text):
        text = (text or "").casefold()
        text = re.sub(r"\bl\d+\b", " ", text)
        text = text.replace("&", " and ")
        text = re.sub(r"[^0-9a-z\u0600-\u06ff/]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _get_website_group_name_chain(self):
        self.ensure_one()
        chain = []
        group = self
        while group:
            chain.append(group.name or group.code or "")
            group = group.parent_id
        return list(reversed([name for name in chain if name]))

    def _get_canonical_website_category_path(self):
        self.ensure_one()
        return self._get_canonical_website_category_path_from_text(self.website_sync_group_path)

    @api.model
    def _get_canonical_website_category_path_from_text(self, text):
        normalized_path = self._normalize_website_category_text(text)
        if not normalized_path:
            return False
        normalized_parts = [
            part.strip()
            for part in normalized_path.split("/")
            if part.strip()
        ]

        exact = WEBSITE_CATEGORY_TOP_LEVEL.get(normalized_parts[-1])
        if exact:
            return exact
        for keywords, category_path in WEBSITE_CATEGORY_RULES:
            if any(keyword in normalized_path for keyword in keywords):
                return category_path
        return False

    @api.model
    def _get_or_create_canonical_website_category(self, category_path, sync_cache=None):
        Category = self.env["product.public.category"].sudo().with_context(lang=False)
        parent = Category
        category = Category
        sequence_base = 10
        for depth, name in enumerate(category_path):
            domain = [("name", "=", name), ("parent_id", "=", parent.id if parent else False)]
            key = (name, parent.id if parent else False)
            category = (sync_cache["categories"].get(key, Category) if sync_cache is not None
                        else Category.search(domain, limit=1))
            vals = {
                "name": name,
                "parent_id": parent.id if parent else False,
                "sequence": sequence_base + depth,
            }
            if category:
                changes = website_sync_changed_values(category, vals)
                if changes:
                    category.write(changes)
            else:
                category = Category.create(vals)
            if sync_cache is not None:
                sync_cache["categories"][key] = category
            if sync_cache is None or category.id not in sync_cache["translated_categories"]:
                category._write_arabic_website_category_translation(
                    languages=sync_cache["languages"] if sync_cache is not None else None,
                )
                if sync_cache is not None:
                    sync_cache["translated_categories"].add(category.id)
            parent = category
            sequence_base += 10
        return category


class ProductPublicCategory(models.Model):
    _inherit = "product.public.category"

    def _write_arabic_website_category_translation(self, languages=None):
        Lang = self.env["res.lang"].sudo()
        arabic_langs = languages
        if arabic_langs is None:
            arabic_langs = Lang.search([("code", "in", ["ar_001", "ar"])])
            if not arabic_langs:
                arabic_langs = Lang.search([("code", "like", "ar%")])
        for category in self:
            arabic_name = WEBSITE_CATEGORY_TRANSLATIONS.get(
                category.with_context(lang=False).name
            )
            if not arabic_name:
                continue
            for lang in arabic_langs:
                translated_category = category.with_context(lang=lang.code)
                if translated_category.name != arabic_name:
                    translated_category.write({"name": arabic_name})


class AbProductTag(models.Model):
    _inherit = "ab_product_tag"

    website_product_tag_id = fields.Many2one(
        "product.tag",
        string="Website Product Tag",
        copy=False,
        readonly=True,
        groups="base.group_user",
    )

    def _get_or_create_website_product_tags(self, sync_cache=None):
        product_tags = self.env["product.tag"].sudo()
        ProductTag = self.env["product.tag"].sudo()
        for tag in self:
            name = tag.name or _("Unnamed Tag")
            product_tag = tag.website_product_tag_id.sudo()
            if not product_tag:
                product_tag = (sync_cache["tags_by_name"].get(name, ProductTag) if sync_cache is not None
                               else ProductTag.search([("name", "=", name)], limit=1))
            vals = {
                "name": name,
                "sequence": tag.priority or 10,
                "visible_to_customers": True,
            }
            if product_tag:
                changes = website_sync_changed_values(product_tag, vals)
                if changes:
                    product_tag.write(changes)
            else:
                product_tag = ProductTag.create(vals)
            if tag.website_product_tag_id != product_tag:
                tag.sudo().website_product_tag_id = product_tag.id
            if sync_cache is not None:
                sync_cache["tags_by_name"].setdefault(name, product_tag)
            product_tags |= product_tag
        return product_tags


class AbProduct(models.Model):
    _inherit = "ab_product"

    website_sync_pending = fields.Boolean(
        string="Website Sync Pending", compute="_compute_website_sync_pending", store=True,
    )
    website_sync_template_ids = fields.One2many(
        "product.template", "ab_product_id", string="Website Sync Templates", readonly=True,
    )
    _website_sync_pending_idx = models.Index("(id) WHERE website_sync_pending")

    @api.depends(
        "name", "product_card_name", "code", "default_price", "default_cost", "is_service",
        "active", "allow_sale", "allow_purchase", "website_sale_available", "description",
        "groups_ids.website_sync_group_path", "groups_ids.active", "tag_ids.name", "tag_ids.priority", "barcode_ids.name",
        "eplus_stock_snapshot_ids.itm_qty", "eplus_stock_snapshot_ids.active",
        "website_sync_template_ids",
        *["website_sync_template_ids." + name for name in (
            "name", "default_code", "list_price", "standard_price", "type", "is_storable",
            "allow_out_of_stock_order", "show_availability", "sale_ok", "purchase_ok", "active",
            "description_sale", "description", "description_ecommerce", "website_description",
            "is_published", "public_categ_ids", "public_categ_ids.name", "public_categ_ids.parent_id",
            "product_tag_ids", "product_tag_ids.name", "product_tag_ids.sequence", "image_1920",
            "product_variant_ids", "product_variant_ids.active", "product_variant_ids.default_code", "product_variant_ids.barcode",
            "invoice_policy", "service_tracking", "combo_ids",
            "eplus_stock_shown_qty_type", "eplus_stock_shown_qty_value",
        )],
    )
    def _compute_website_sync_pending(self):
        for product in self:
            product.website_sync_pending = True

    website_sale_available = fields.Boolean(
        string="Available on Website",
        default=True,
        help="When enabled, sync publishes the linked eCommerce product if this product is active and allowed for sale.",
    )
    website_product_tmpl_id = fields.Many2one(
        "product.template",
        string="eCommerce Product",
        compute="_compute_website_product_tmpl_id",
        search="_search_website_product_tmpl_id",
        compute_sudo=True,
        groups="base.group_user",
    )
    website_product_synced = fields.Boolean(
        string="Synced to eCommerce",
        compute="_compute_website_product_synced",
        search="_search_website_product_synced",
        compute_sudo=True,
        groups="base.group_user",
    )
    website_product_is_published = fields.Boolean(
        string="Published on Website",
        compute="_compute_website_product_is_published",
        search="_search_website_product_is_published",
        compute_sudo=True,
        groups="base.group_user",
    )
    website_image_file_found = fields.Boolean(
        string="Image File Found",
        compute="_compute_website_image_file_info",
        compute_sudo=True,
        groups="base.group_user",
    )
    website_image_file_path = fields.Char(
        string="Image File",
        compute="_compute_website_image_file_info",
        compute_sudo=True,
        groups="base.group_user",
    )
    eplus_stock_snapshot_ids = fields.One2many(
        "ab_eplus_stock_snapshot",
        "product_id",
        string="Eplus Items",
        groups="base.group_user",
    )
    eplus_stock_snapshot_store_ids = fields.One2many(
        "ab_eplus_stock_snapshot_store",
        "product_id",
        string="Eplus Branch Stock",
        groups="base.group_user",
    )
    eplus_stock_item_count = fields.Integer(
        string="Eplus Item Count",
        compute="_compute_eplus_stock_snapshot_summary",
        compute_sudo=True,
        groups="base.group_user",
    )
    eplus_stock_total_qty = fields.Float(
        string="Eplus Total Quantity",
        compute="_compute_eplus_stock_snapshot_summary",
        compute_sudo=True,
        groups="base.group_user",
    )

    def _compute_eplus_stock_snapshot_summary(self):
        summary_by_product = {
            product.id: {"count": 0, "qty": 0.0}
            for product in self
        }
        if self.ids:
            groups = self.env["ab_eplus_stock_snapshot"].sudo()._read_group(
                [("product_id", "in", self.ids), ("active", "=", True)],
                groupby=["product_id"],
                aggregates=["__count", "itm_qty:sum"],
            )
            for product, count, qty in groups:
                if product:
                    summary_by_product[product.id] = {
                        "count": count,
                        "qty": qty or 0.0,
                    }
        for product in self:
            summary = summary_by_product.get(product.id, {})
            product.eplus_stock_item_count = summary.get("count", 0)
            product.eplus_stock_total_qty = summary.get("qty", 0.0)

    def _compute_website_product_tmpl_id(self):
        templates = self.env["product.template"].sudo().with_context(active_test=False).search([
            ("ab_product_id", "in", self.ids),
        ])
        template_by_product_id = {}
        for template in templates:
            template_by_product_id.setdefault(template.ab_product_id.id, template)
        for product in self:
            product.website_product_tmpl_id = template_by_product_id.get(product.id)

    def _compute_website_product_synced(self):
        for product in self:
            product.website_product_synced = bool(product.website_product_tmpl_id)

    def _compute_website_product_is_published(self):
        for product in self:
            template = product.website_product_tmpl_id
            product.website_product_is_published = bool(
                template and template.active and template.sale_ok and template.is_published
            )

    def _compute_website_image_file_info(self):
        directory_path = self._get_configured_website_image_directory()
        for product in self:
            image_path = product._find_website_image_file(directory_path) if directory_path else False
            product.website_image_file_found = bool(image_path)
            product.website_image_file_path = image_path or False

    @api.model
    def _get_default_website_image_directory(self):
        return (
                self.env["ir.config_parameter"].sudo().get_param(
                    "ab_website_sale_product.image_directory"
                )
                or DEFAULT_WEBSITE_IMAGE_DIRECTORY
        )

    @api.model
    def _get_configured_website_image_directory(self):
        directory_path = (self._get_default_website_image_directory() or "").strip()
        if not directory_path:
            return False
        directory_path = os.path.abspath(os.path.expanduser(directory_path))
        return directory_path if os.path.isdir(directory_path) else False

    def _get_website_image_filename_candidates(self):
        self.ensure_one()
        code = (self.code or "").strip()
        if not code or os.path.basename(code) != code:
            return []
        _, extension = os.path.splitext(code)
        if extension:
            return [code]
        return [f"{code}{extension}" for extension in WEBSITE_IMAGE_EXTENSIONS]

    def _find_website_image_file(self, directory_path):
        self.ensure_one()
        if not directory_path or not self.website_product_tmpl_id:
            return False
        plan = self.env["ab.website.product.image.sync.service"].prepare_sync_plan(
            directory_path,
            products=self,
        )
        for line in plan["report"]:
            if line.get("product_id") == self.id and line.get("image_path"):
                return line["image_path"]
        return False

    def _sync_website_product_image_from_file(self, image_path):
        self.ensure_one()
        template = self.website_product_tmpl_id
        if not template:
            raise UserError(_("Product %s is not synced to eCommerce.") % (self.display_name,))
        with open(image_path, "rb") as image_file:
            image_data = base64.b64encode(image_file.read())
        template._apply_website_sync_image(image_data)
        return template

    @api.model
    def _get_website_placeholder_image(self):
        if not os.path.isfile(WEBSITE_PLACEHOLDER_IMAGE_PATH):
            return False
        with open(WEBSITE_PLACEHOLDER_IMAGE_PATH, "rb") as image_file:
            return base64.b64encode(image_file.read())

    def _ensure_website_product_placeholder_image(self, template):
        self.ensure_one()
        if template.image_1920:
            return template
        placeholder_image = self._get_website_placeholder_image()
        if placeholder_image:
            template.sudo().write({"image_1920": placeholder_image})
        return template

    @api.model
    def _search_website_product_tmpl_id(self, operator, value):
        if operator in ("=", "!=") and not value:
            synced = operator == "!="
            return self._website_product_synced_domain(synced)
        if operator in ("=", "!=") and value:
            templates = self.env["product.template"].sudo().with_context(active_test=False).search([
                ("id", operator, value),
                ("ab_product_id", "!=", False),
            ])
            return [("id", "in", templates.mapped("ab_product_id").ids)]
        return NotImplemented

    @api.model
    def _search_website_product_synced(self, operator, value):
        if operator not in ("=", "!="):
            return NotImplemented
        synced = bool(value)
        if operator == "!=":
            synced = not synced
        return self._website_product_synced_domain(synced)

    @api.model
    def _search_website_product_is_published(self, operator, value):
        if operator not in ("=", "!="):
            return NotImplemented
        published = bool(value)
        if operator == "!=":
            published = not published
        return self._website_product_published_domain(published)

    @api.model
    def _website_product_synced_domain(self, synced):
        product_ids = self._website_linked_ab_product_ids()
        return [("id", "in" if synced else "not in", product_ids)]

    @api.model
    def _website_product_published_domain(self, published):
        product_ids = self._website_linked_ab_product_ids([
            ("active", "=", True),
            ("sale_ok", "=", True),
            ("is_published", "=", True),
        ])
        return [("id", "in" if published else "not in", product_ids)]

    @api.model
    def _website_linked_ab_product_ids(self, extra_domain=None):
        domain = [("ab_product_id", "!=", False)]
        if extra_domain:
            domain += extra_domain
        return self.env["product.template"].sudo().with_context(active_test=False).search(domain).mapped(
            "ab_product_id").ids

    def action_refresh_eplus_stock_items(self):
        return self.env["ab_eplus_stock_snapshot"].sudo().action_refresh_from_eplus()

    def action_open_sync_images_wizard(self):
        self.env["ab.website.product.image.sync.service"].check_image_sync_access()
        return {
            "type": "ir.actions.act_window",
            "name": _("Sync Images"),
            "res_model": "ab.website.sale.add.many.by.codes.wizard",
            "view_mode": "form",
            "view_id": self.env.ref("ab_website_sale_product.view_sync_images_wizard_form").id,
            "target": "new",
        }

    def action_open_eplus_stock_items(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Eplus Items - %s") % self.display_name,
            "res_model": "ab_eplus_stock_snapshot",
            "view_mode": "list,form,pivot",
            "domain": [("product_id", "=", self.id)],
            "context": {"search_default_filter_matched": 1},
        }

    def action_open_eplus_branch_stock(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Eplus Branch Stock - %s") % self.display_name,
            "res_model": "ab_eplus_stock_snapshot_store",
            "view_mode": "list,pivot,form",
            "domain": [("product_id", "=", self.id), ("active", "=", True)],
            "context": {"search_default_group_by_store": 1},
        }

    @api.model
    def _ab_text_to_html(self, text):
        if not text:
            return False
        lines = str(html_escape(text)).splitlines() or [""]
        return "<p>%s</p>" % "<br/>".join(lines)

    def _prepare_website_product_template_vals(self, sync_cache=None):
        self.ensure_one()
        ProductTemplate = self.env["product.template"]
        public_categories = self._get_or_create_website_public_categories(sync_cache=sync_cache)
        product_tags = self.tag_ids._get_or_create_website_product_tags(sync_cache=sync_cache)
        name = self.name or self.product_card_name or self.code or _("Unnamed Product")
        description = self.description or False
        sale_ok = bool(self.active and self.allow_sale)
        is_published = bool(sale_ok and self.website_sale_available)

        vals = {
            "ab_product_id": self.id,
            "name": name,
            "default_code": self.code or False,
            "list_price": self.default_price or 0.0,
            "standard_price": self.default_cost or 0.0,
            "type": "service" if self.is_service else "consu",
            "is_storable": not self.is_service,
            "allow_out_of_stock_order": bool(self.is_service),
            "show_availability": not self.is_service,
            "sale_ok": sale_ok,
            "purchase_ok": bool(self.active and self.allow_purchase),
            "active": bool(self.active),
            "description_sale": description,
            "description": self._ab_text_to_html(description),
            "description_ecommerce": self._ab_text_to_html(description),
            "website_description": self._ab_text_to_html(description),
            "is_published": is_published,
            "public_categ_ids": [fields.Command.set(public_categories.ids)],
            "product_tag_ids": [fields.Command.set(product_tags.ids)],
        }
        if "invoice_policy" in ProductTemplate._fields:
            vals["invoice_policy"] = "order"
        if "service_tracking" in ProductTemplate._fields:
            vals["service_tracking"] = "no"
        return vals

    def _get_or_create_website_public_categories(self, fallback=True, sync_cache=None):
        self.ensure_one()
        public_categories = self.groups_ids._get_or_create_website_categories(sync_cache=sync_cache) if self.groups_ids else self.env["product.public.category"].sudo()
        if public_categories:
            return public_categories

        classifier = self.env["ab_product_group"]
        text = " ".join(
            part
            for part in [
                self.name,
                self.product_card_name,
                self.description,
                self.code,
            ]
            if part
        )
        category_path = classifier._get_canonical_website_category_path_from_text(text)
        if category_path:
            return classifier._get_or_create_canonical_website_category(category_path, sync_cache=sync_cache)
        if fallback:
            return classifier._get_or_create_canonical_website_category(("Everyday Essentials",), sync_cache=sync_cache)
        return self.env["product.public.category"].sudo()

    def _prepare_initial_website_stock_display_vals(self):
        self.ensure_one()
        return {
            "eplus_stock_shown_qty_type": "quantity",
            "eplus_stock_shown_qty_value": max(self.eplus_stock_total_qty or 0.0, 0.0),
        }

    def _template_needs_initial_website_stock_display(self, template):
        self.ensure_one()
        return (
                not template.eplus_stock_shown_qty_value
                or (
                        template.eplus_stock_shown_qty_type == "percentage"
                        and template.eplus_stock_shown_qty_value == 100.0
                )
        )

    def _prepare_website_product_variant_vals(self):
        self.ensure_one()
        barcode = self.barcode_ids.filtered("name")[:1].name or False
        return {
            "default_code": self.code or False,
            "barcode": barcode,
        }

    @api.model
    def _lock_website_sync(self, wait=True):
        if wait:
            self.env.cr.execute("SELECT pg_advisory_xact_lock(%s, %s)", (190019, 731))
            return True
        self.env.cr.execute("SELECT pg_try_advisory_xact_lock(%s, %s)", (190019, 731))
        return self.env.cr.fetchone()[0]

    def _website_sync_cache(self):
        names = set(WEBSITE_CATEGORY_TRANSLATIONS)
        Category = self.env["product.public.category"].sudo().with_context(lang=False)
        categories = Category.search(fields.Domain("name", "in", list(names)))
        by_key = {}
        for category in categories:
            by_key.setdefault((category.name, category.parent_id.id), category)
        languages = self.env["res.lang"].sudo().search(fields.Domain("code", "in", ["ar_001", "ar"]))
        if not languages:
            languages = self.env["res.lang"].sudo().search(fields.Domain("code", "like", "ar%"))
        tags = self.tag_ids
        tag_names = [tag.name or _("Unnamed Tag") for tag in tags]
        existing_tags = self.env["product.tag"].sudo().search(fields.Domain("name", "in", tag_names))
        by_name = {}
        for tag in existing_tags:
            by_name.setdefault(tag.name, tag)
        return {
            "categories": by_key, "groups": {}, "translated_categories": set(),
            "languages": languages, "tags_by_name": by_name,
        }

    def _sync_website_products(self, outcomes=None):
        self._lock_website_sync()
        template_ids = []
        for offset in range(0, len(self), WEBSITE_SYNC_CHUNK_SIZE):
            templates = self[offset:offset + WEBSITE_SYNC_CHUNK_SIZE]._sync_website_product_batch(outcomes=outcomes)
            template_ids.extend(templates.ids)
        return self.env["product.template"].sudo().with_context(active_test=False).browse(template_ids)

    def _sync_website_product_batch(self, outcomes=None):
        products = self.sudo()
        ProductTemplate = self.env["product.template"].sudo().with_context(active_test=False)
        existing = ProductTemplate.search(fields.Domain("ab_product_id", "in", products.ids))
        by_product = {}
        for template in existing:
            by_product.setdefault(template.ab_product_id.id, template)
        sync_cache = products._website_sync_cache()
        missing_products = []
        missing_values = []
        statuses = {}
        for product in products:
            template = by_product.get(product.id)
            vals = product._prepare_website_product_template_vals(sync_cache=sync_cache)
            if template:
                changes = website_sync_changed_values(template, vals)
                if vals.get("active") and not template.product_variant_ids:
                    changes["active"] = True
                if vals.get("type") != "combo" and template.combo_ids:
                    changes["type"] = vals["type"]
                if changes:
                    template.write(changes)
                if product._template_needs_initial_website_stock_display(template):
                    stock_changes = website_sync_changed_values(template, product._prepare_initial_website_stock_display_vals())
                    if stock_changes:
                        template.write(stock_changes)
                        changes.update(stock_changes)
                statuses[product.id] = "updated" if changes else "unchanged"
            else:
                vals.update(product._prepare_initial_website_stock_display_vals())
                missing_products.append(product.id)
                missing_values.append(vals)
        if missing_values:
            created = ProductTemplate.create(missing_values)
            for product_id, template in zip(missing_products, created):
                by_product[product_id] = template
                statuses[product_id] = "created"
        templates = ProductTemplate.browse([by_product[product.id].id for product in products])
        without_image = templates.with_context(bin_size=True).filtered(lambda template: not template.image_1920)
        if without_image:
            placeholder = products._get_website_placeholder_image()
            if placeholder:
                image_fields = ["image_1920", "image_1024", "image_512", "image_256", "image_128"]
                for offset in range(0, len(without_image), 25):
                    image_templates = without_image[offset:offset + 25].with_context(bin_size=False)
                    image_templates.write({"image_1920": placeholder})
                    self.env.flush_all()
                    image_templates.invalidate_recordset(image_fields)
                    image_templates.product_variant_ids.invalidate_recordset(image_fields)
                for template in without_image:
                    if statuses[template.ab_product_id.id] == "unchanged":
                        statuses[template.ab_product_id.id] = "updated"
        for product in products:
            template = by_product[product.id]
            variant = template.product_variant_id or template.with_context(active_test=False).product_variant_ids[:1]
            if variant:
                product_dict = website_sync_changed_values(variant, product._prepare_website_product_variant_vals())
                if not product_dict:
                    continue
                try:
                    with self.env.cr.savepoint():
                        variant.sudo().write(product_dict)
                except (ValidationError, IntegrityError):
                    if "barcode" not in product_dict:
                        raise
                    _logger.warning("Website sync retained barcode for ab_product %s", product.id, exc_info=True)
                    product_dict.pop("barcode", None)
                    if product_dict:
                        variant.sudo().write(product_dict)
                if statuses[product.id] == "unchanged":
                    statuses[product.id] = "updated"
        products.flush_recordset()
        products.filtered("website_sync_pending").write({"website_sync_pending": False})
        if outcomes is not None:
            outcomes.update(statuses)
        return templates

    def action_sync_website_product(self):
        self = self.sudo()
        templates = self._sync_website_products()
        if len(self) == 1 and templates:
            return {
                "type": "ir.actions.act_window",
                "name": _("eCommerce Product"),
                "res_model": "product.template",
                "res_id": templates[0].id,
                "view_mode": "form",
                "target": "current",
            }
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("eCommerce Sync"),
                "message": _("%s products synced to the website shop.", len(templates)),
                "type": "success",
                "sticky": False,
            },
        }

    def action_open_website_product(self):
        self.ensure_one()
        template = self.website_product_tmpl_id
        if not template:
            template = self._sync_website_products()
        if not template:
            raise UserError(_("No eCommerce product could be found or created."))
        return {
            "type": "ir.actions.act_window",
            "name": _("eCommerce Product"),
            "res_model": "product.template",
            "res_id": template.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_open_website_product_page(self):
        self.ensure_one()
        template = self.website_product_tmpl_id
        if not template:
            template = self._sync_website_products()
        if not template.is_published:
            raise UserError(
                _("The linked eCommerce product is not published. Enable Website availability and sync again."))
        return template.open_website_url()

    def action_check_website_product_image(self):
        self.ensure_one()
        directory_path = self._get_configured_website_image_directory()
        if not directory_path:
            raise UserError(
                _("Image directory is not configured or does not exist. Current default: %s")
                % self._get_default_website_image_directory()
            )
        image_path = self._find_website_image_file(directory_path)
        message = (
            _("Image file found: %s") % image_path
            if image_path
            else _("No image file found for product code %s in %s.") % (self.code or _("empty"), directory_path)
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Product Image Check"),
                "message": message,
                "type": "success" if image_path else "warning",
                "sticky": not bool(image_path),
            },
        }

    @api.model
    def cron_sync_website_products(self, limit=1000):
        self.env["ab_website_product_sync_job"].check_access("create")
        self.env["ab_website_product_sync_job"]._queue_delta_sync(limit=limit)
        return True
