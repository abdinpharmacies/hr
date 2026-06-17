from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _


class AbProductSeoMatch(models.Model):
    _name = "ab.product.seo.match"
    _description = "Website SEO Match"
    _order = "create_date desc, id desc"

    seo_id = fields.Many2one("ab.product.seo", required=True, index=True, ondelete="cascade")
    source = fields.Selection(
        [
            ("internal", "Internal"),
            ("eplus", "E-Plus"),
            ("ready_api", "Ready API"),
        ],
        required=True,
        default="internal",
        index=True,
    )
    match_method = fields.Selection(
        [
            ("barcode", "Barcode"),
            ("eplus_serial", "E-Plus Serial"),
            ("code", "Product Code"),
            ("scientific_group", "Scientific Group"),
            ("normalized_name", "Normalized Name"),
            ("fuzzy", "Fuzzy"),
        ],
        required=True,
        index=True,
    )
    match_score = fields.Float()
    external_reference = fields.Char(index=True)
    matched_payload = fields.Json()
    status = fields.Selection(
        [
            ("candidate", "Candidate"),
            ("accepted", "Accepted"),
            ("rejected", "Rejected"),
        ],
        default="candidate",
        required=True,
        index=True,
    )
    notes = fields.Text()

    def unlink(self):
        raise UserError(_("SEO match history must not be deleted."))
