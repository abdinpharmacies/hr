import base64
import binascii

from markupsafe import Markup, escape

from odoo import _, api, fields, models


class WebsiteCarouselSlide(models.Model):
    _name = "ab_website_carousel_slide"
    _description = "Homepage Carousel Slide"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    website_id = fields.Many2one(
        "website",
        string="Website",
        ondelete="cascade",
        help="Leave empty to show this slide on every website.",
    )
    image_1920 = fields.Image(
        string="Desktop Image",
        required=True,
        max_width=1920,
        max_height=1920,
    )
    title = fields.Char(translate=True)
    subtitle = fields.Text(translate=True)
    show_cta = fields.Boolean(string="Show CTA", default=True)
    cta_style = fields.Selection(
        [
            ("text", "Text Button"),
            ("image", "Image Button"),
            ("link", "Link"),
        ],
        string="CTA Style",
        default="text",
        required=True,
    )
    cta_text = fields.Char(string="CTA Text", translate=True)
    cta_image_512 = fields.Image(
        string="CTA Image",
        max_width=512,
        max_height=512,
        help="Optional clickable image rendered above the slide image.",
    )
    cta_url = fields.Char(string="CTA URL", default="/shop?category=offers")
    cta_position_x = fields.Integer(
        string="CTA X Position",
        default=50,
        help="Horizontal CTA position as a percentage of the slide width.",
    )
    cta_position_y = fields.Integer(
        string="CTA Y Position",
        default=78,
        help="Vertical CTA position as a percentage of the slide height.",
    )
    cta_width = fields.Integer(
        string="CTA Width",
        default=220,
        help="CTA width in pixels. Text buttons use this as a minimum width.",
    )
    cta_preview_html = fields.Html(
        string="CTA Position Preview",
        compute="_compute_cta_preview_html",
        sanitize=False,
    )

    @api.depends(
        "image_1920",
        "show_cta",
        "cta_style",
        "cta_text",
        "cta_image_512",
        "cta_position_x",
        "cta_position_y",
        "cta_width",
    )
    def _compute_cta_preview_html(self):
        for slide in self:
            image_src = slide._get_preview_image_src("image_1920")
            if not image_src:
                slide.cta_preview_html = Markup(
                    "<div class='ab_carousel_position_preview_empty'>"
                    "%s"
                    "</div>"
                ) % escape(_("Save the slide to preview CTA placement."))
                continue
            cta_html = ""
            if slide.show_cta and slide.cta_style != "link":
                style = (
                    "left:%s%%;right:auto;top:%s%%;--ab-preview-cta-width:%spx;direction:ltr;"
                    % (
                        self._clamp_percent(slide.cta_position_x),
                        self._clamp_percent(slide.cta_position_y),
                        self._clamp_px(slide.cta_width),
                    )
                )
                cta_image_src = slide._get_preview_image_src("cta_image_512")
                if slide.cta_style == "image" and cta_image_src:
                    cta_html = (
                        "<span class='ab_carousel_position_preview_cta ab_carousel_position_preview_cta_image' dir='ltr' "
                        "data-ab-position-x='%s' data-ab-position-y='%s' data-ab-width='%s' style='%s'>"
                        "<img src='%s' alt=''/>"
                        "<i class='ab_carousel_position_resize_handle is-nw' data-ab-resize-side='left'></i>"
                        "<i class='ab_carousel_position_resize_handle is-ne' data-ab-resize-side='right'></i>"
                        "<i class='ab_carousel_position_resize_handle is-sw' data-ab-resize-side='left'></i>"
                        "<i class='ab_carousel_position_resize_handle is-se' data-ab-resize-side='right'></i>"
                        "</span>"
                    ) % (
                        self._clamp_percent(slide.cta_position_x),
                        self._clamp_percent(slide.cta_position_y),
                        self._clamp_px(slide.cta_width),
                        style,
                        cta_image_src,
                    )
                else:
                    label = slide.cta_text or _("CTA")
                    cta_html = (
                        "<span class='ab_carousel_position_preview_cta ab_carousel_position_preview_cta_text' dir='auto' "
                        "data-ab-position-x='%s' data-ab-position-y='%s' data-ab-width='%s' style='%s'>"
                        "%s"
                        "<i class='ab_carousel_position_resize_handle is-nw' data-ab-resize-side='left'></i>"
                        "<i class='ab_carousel_position_resize_handle is-ne' data-ab-resize-side='right'></i>"
                        "<i class='ab_carousel_position_resize_handle is-sw' data-ab-resize-side='left'></i>"
                        "<i class='ab_carousel_position_resize_handle is-se' data-ab-resize-side='right'></i>"
                        "</span>"
                    ) % (
                        self._clamp_percent(slide.cta_position_x),
                        self._clamp_percent(slide.cta_position_y),
                        self._clamp_px(slide.cta_width),
                        style,
                        escape(label),
                    )
            slide.cta_preview_html = Markup(
                "<div class='ab_carousel_position_preview' dir='ltr'>"
                "<img src='%s' alt=''/>"
                "%s"
                "</div>"
            ) % (image_src, Markup(cta_html))

    def _get_preview_image_src(self, field_name):
        self.ensure_one()
        if self.id:
            return Markup("/web/image/ab_website_carousel_slide/%s/%s") % (self.id, field_name)
        value = self[field_name]
        if not value:
            return ""
        if isinstance(value, bytes):
            value = value.decode()
        mimetype = self._guess_preview_image_mimetype(value)
        return Markup("data:%s;base64,%s") % (mimetype, escape(value))

    @staticmethod
    def _guess_preview_image_mimetype(value):
        try:
            decoded = base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError):
            return "image/png"
        stripped = decoded.lstrip()
        if stripped.startswith(b"<svg") or stripped.startswith(b"<?xml"):
            return "image/svg+xml"
        if decoded.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        if decoded.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        if decoded.startswith(b"RIFF") and decoded[8:12] == b"WEBP":
            return "image/webp"
        if decoded.startswith((b"GIF87a", b"GIF89a")):
            return "image/gif"
        return "image/png"

    @staticmethod
    def _clamp_percent(value):
        return min(100, max(0, int(value or 0)))

    @staticmethod
    def _clamp_px(value):
        return min(520, max(40, int(value or 0)))

    @api.onchange("cta_position_x", "cta_position_y", "cta_width")
    def _onchange_cta_position_values(self):
        for slide in self:
            slide.cta_position_x = self._clamp_percent(slide.cta_position_x)
            slide.cta_position_y = self._clamp_percent(slide.cta_position_y)
            slide.cta_width = self._clamp_px(slide.cta_width)

    def _clear_homepage_carousel_cache(self):
        self.env.registry.clear_cache("templates")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._clean_cta_position_vals(vals)
        slides = super().create(vals_list)
        slides._clear_homepage_carousel_cache()
        return slides

    def write(self, vals):
        self._clean_cta_position_vals(vals)
        result = super().write(vals)
        self._clear_homepage_carousel_cache()
        return result

    @classmethod
    def _clean_cta_position_vals(cls, vals):
        if "cta_position_x" in vals:
            vals["cta_position_x"] = cls._clamp_percent(vals["cta_position_x"])
        if "cta_position_y" in vals:
            vals["cta_position_y"] = cls._clamp_percent(vals["cta_position_y"])
        if "cta_width" in vals:
            vals["cta_width"] = cls._clamp_px(vals["cta_width"])

    def unlink(self):
        result = super().unlink()
        self._clear_homepage_carousel_cache()
        return result

    def action_preview_homepage(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": self.website_id.website_url or "/",
            "target": "new",
        }
