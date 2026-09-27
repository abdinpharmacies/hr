from urllib.parse import urlparse

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


_SUPPORTED_PLATFORM_HOSTS = {
    "facebook.com": "facebook",
    "www.facebook.com": "facebook",
    "m.facebook.com": "facebook",
    "fb.watch": "facebook",
    "instagram.com": "instagram",
    "www.instagram.com": "instagram",
    "tiktok.com": "tiktok",
    "www.tiktok.com": "tiktok",
    "vm.tiktok.com": "tiktok",
    "vt.tiktok.com": "tiktok",
}

_PLATFORM_LABELS = {
    "facebook": "Facebook",
    "instagram": "Instagram",
    "tiktok": "TikTok",
}

_PLATFORM_ICON_CLASSES = {
    "facebook": "fa fa-facebook",
    "instagram": "fa fa-instagram",
    "tiktok": "fa fa-music",
}


class AbEcommerceCustomerTestimonial(models.Model):
    _name = "ab_ecommerce_customer_testimonial"
    _description = "Storefront Social Comment"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    image_1920 = fields.Image(
        string="Social Comment Screenshot",
        required=True,
        max_width=1920,
        max_height=1920,
        verify_resolution=True,
    )
    image_1024 = fields.Image(
        string="Social Comment Screenshot 1024",
        related="image_1920",
        max_width=1024,
        max_height=1024,
        store=True,
        readonly=True,
    )
    source_url = fields.Char(string="Source URL", required=True)
    platform = fields.Selection(
        string="Platform",
        selection=[
            ("facebook", "Facebook"),
            ("instagram", "Instagram"),
            ("tiktok", "TikTok"),
        ],
        compute="_compute_platform",
        store=True,
        readonly=True,
    )
    customer_name = fields.Char(translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(string="Published", default=True)
    website_id = fields.Many2one("website", ondelete="restrict")

    @api.depends("source_url")
    def _compute_platform(self):
        for testimonial in self:
            testimonial.platform = testimonial._detect_platform(testimonial.source_url) or False

    @api.onchange("source_url")
    def _onchange_source_url(self):
        for testimonial in self:
            testimonial.source_url = testimonial._normalize_source_url(testimonial.source_url)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "source_url" in vals:
                vals["source_url"] = self._normalize_source_url(vals.get("source_url"))
        return super().create(vals_list)

    def write(self, vals):
        if "source_url" in vals:
            vals = dict(vals, source_url=self._normalize_source_url(vals.get("source_url")))
        return super().write(vals)

    @api.constrains("source_url")
    def _check_source_url(self):
        for testimonial in self:
            if not testimonial._detect_platform(testimonial.source_url):
                raise ValidationError(_("Please enter a valid Facebook, Instagram, or TikTok source URL."))

    @api.model
    def _normalize_source_url(self, source_url):
        source_url = (source_url or "").strip()
        if not source_url:
            return source_url
        parsed_url = urlparse(source_url)
        if not parsed_url.scheme:
            source_url = "https://%s" % source_url.lstrip("/")
            parsed_url = urlparse(source_url)
        if parsed_url.scheme not in ("http", "https") or not parsed_url.netloc:
            return source_url
        host = parsed_url.netloc.lower().strip().rstrip(".")
        if "@" in host:
            host = host.rsplit("@", 1)[-1]
        if ":" in host:
            host = host.split(":", 1)[0]
        return parsed_url._replace(scheme=parsed_url.scheme.lower(), netloc=host).geturl()

    @api.model
    def _detect_platform(self, source_url):
        source_url = self._normalize_source_url(source_url)
        parsed_url = urlparse(source_url or "")
        host = parsed_url.netloc.lower().strip().rstrip(".")
        if ":" in host:
            host = host.split(":", 1)[0]
        return _SUPPORTED_PLATFORM_HOSTS.get(host)

    def action_publish(self):
        self.write({"active": True})

    def action_unpublish(self):
        self.write({"active": False})

    def _ab_storefront_image_alt(self):
        self.ensure_one()
        if self.customer_name:
            return _("Social comment from %s") % self.customer_name
        return _("Customer social comment screenshot")

    def _ab_storefront_platform_label(self):
        self.ensure_one()
        return self.env._(_PLATFORM_LABELS.get(self.platform, "Social platform"))

    def _ab_storefront_platform_icon_class(self):
        self.ensure_one()
        return _PLATFORM_ICON_CLASSES.get(self.platform, "fa fa-commenting-o")

    def _ab_storefront_source_action_label(self):
        self.ensure_one()
        return _("View on %s") % self._ab_storefront_platform_label()

    def _ab_storefront_source_action_aria_label(self):
        self.ensure_one()
        return _("Open original comment on %s") % self._ab_storefront_platform_label()
