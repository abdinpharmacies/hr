from odoo import _, fields, models
from odoo.exceptions import ValidationError


class WebsiteCarouselSlide(models.Model):
    _inherit = "ab_website_carousel_slide"

    def _check_offer_period(self, website, company, date_from, date_to, *, offer=None, program=None):
        self.ensure_one()
        self.check_access("read")
        self.lock_for_update(allow_referencing=True)
        domain = fields.Domain("active", "=", True) & fields.Domain("company_id", "in", [False, company.id])
        if website:
            domain &= fields.Domain("website_id", "in", [False, website.id])
        if date_from:
            domain &= fields.Domain("date_to", "=", False) | fields.Domain("date_to", ">=", date_from)
        if date_to:
            domain &= fields.Domain("date_from", "=", False) | fields.Domain("date_from", "<=", date_to)
        programs = domain & fields.Domain("ab_program_slide_id", "=", self.id) & fields.Domain("ecommerce_ok", "=", True)
        offers = domain & fields.Domain("carousel_slide_id", "=", self.id)
        if program:
            programs &= fields.Domain("id", "!=", program.id)
        if offer:
            offers &= fields.Domain("id", "!=", offer.id)
        if (self.env["loyalty.program"].sudo().search_count(programs, limit=1)
                or self.env["ab_storefront_offer"].sudo().search_count(offers, limit=1)):
            raise ValidationError(_("This carousel slide already has an overlapping storefront offer on this website."))

    def _can_return_content(self, field_name=None, access_token=None):
        if field_name in ("image_1920", "cta_image_512") and self.sudo().active:
            return True
        return super()._can_return_content(field_name, access_token)
