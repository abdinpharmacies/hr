from base64 import b64encode

from odoo import api, fields, models
from odoo.tools import file_open


class ProductPublicCategory(models.Model):
    _inherit = "product.public.category"

    ab_storefront_section_image = fields.Image(
        string="Section Image", compute="_compute_storefront_section_image",
        inverse="_inverse_storefront_section_image", compute_sudo=False,
    )

    @api.depends("cover_image", "image_1024", "website_id", "name")
    @api.depends_context("website_id", "allowed_company_ids", "uid", "bin_size")
    def _compute_storefront_section_image(self):
        current_website = self.env["website"].get_current_website()
        for website, categories in self.grouped(
            lambda category: category.website_id or current_website
        ).items():
            missing = categories.filtered(lambda category: not category.cover_image and not category.image_1024)
            products = {}
            if missing and website and website.company_id in self.env.companies:
                products = website.with_user(website.user_id)._ab_storefront_category_products(missing)
            for category in categories:
                source = category.with_context(bin_size=False)
                product = products.get(category.id)
                category.ab_storefront_section_image = (
                    source.cover_image or source.image_1024
                    or (
                        product.with_context(bin_size=False).image_1024
                        or b64encode(self.env["ir.binary"]._placeholder(
                            product._get_placeholder_filename("image_1024")
                        ))
                        if product else category._storefront_fallback_icon_image(website)
                    )
                )

    def _storefront_fallback_icon_image(self, website):
        self.ensure_one()
        presentation = website._ab_storefront_category_presentation(self)
        path = (
            "ab_ecommerce_storefront/static/src/img/category_fallbacks/"
            f"{presentation['icon']}-{presentation['tone']}.png"
        )
        with file_open(path, "rb", filter_ext=(".png",)) as image:
            return b64encode(image.read())

    def _inverse_storefront_section_image(self):
        for category in self:
            category.cover_image = category.ab_storefront_section_image
