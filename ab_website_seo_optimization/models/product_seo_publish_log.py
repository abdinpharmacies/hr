from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

from .product_seo import SEO_LANGUAGES


class AbProductSeoPublishLog(models.Model):
    _name = "ab.product.seo.publish.log"
    _description = "Website SEO Publish Log"
    _order = "published_at desc, id desc"

    seo_id = fields.Many2one("ab.product.seo", required=True, index=True, ondelete="cascade")
    product_template_id = fields.Many2one("product.template", required=True, index=True, ondelete="restrict")
    version_id = fields.Many2one("ab.product.seo.version", required=True, index=True, ondelete="restrict")
    lang_code = fields.Selection(SEO_LANGUAGES, required=True, index=True)
    field_name = fields.Char(required=True, index=True)
    old_value = fields.Text(readonly=True)
    new_value = fields.Text(readonly=True)
    operation = fields.Selection(
        [
            ("publish", "Publish"),
            ("rollback", "Rollback"),
            ("republish", "Republish"),
        ],
        required=True,
        default="publish",
        index=True,
    )
    published_by = fields.Many2one("res.users", readonly=True)
    published_at = fields.Datetime(readonly=True, index=True)
    conflict_detected = fields.Boolean(readonly=True)

    def write(self, vals):
        raise UserError(_("SEO publish logs are immutable."))

    def unlink(self):
        raise UserError(_("SEO publish logs must not be deleted."))
