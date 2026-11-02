from odoo import models


class WebsiteCarouselSlide(models.Model):
    _inherit = "ab_website_carousel_slide"

    def _can_return_content(self, field_name=None, access_token=None):
        if field_name in ("image_1920", "cta_image_512") and self.sudo().active:
            return True
        return super()._can_return_content(field_name, access_token)
