from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _


class AbProductSeoSourceSnapshot(models.Model):
    _name = "ab.product.seo.source.snapshot"
    _description = "Website SEO Source Snapshot"
    _order = "snapshot_date desc, id desc"

    seo_id = fields.Many2one("ab.product.seo", required=True, index=True, ondelete="cascade")
    ab_product_id = fields.Many2one("ab_product", required=True, index=True, ondelete="restrict")
    product_template_id = fields.Many2one("product.template", index=True, ondelete="restrict")
    snapshot_date = fields.Datetime(default=fields.Datetime.now, required=True, readonly=True, index=True)
    eplus_serial = fields.Integer(index=True)
    product_code = fields.Char(index=True)
    barcode_values = fields.Text()
    scientific_name = fields.Char()
    scientific_group = fields.Char()
    manufacturer = fields.Char()
    origin = fields.Char()
    usage_manner = fields.Char()
    effective_material = fields.Char()
    effective_material_conc = fields.Char()
    notes = fields.Text()
    group_path = fields.Char()
    raw_eplus_payload = fields.Json()

    def write(self, vals):
        raise UserError(_("SEO source snapshots are immutable. Create a new snapshot instead."))

    def unlink(self):
        raise UserError(_("SEO source snapshots must not be deleted."))

    def _get_source_summary(self):
        self.ensure_one()
        parts = [
            self.product_code and _("Code: %s") % self.product_code,
            self.manufacturer and _("Manufacturer: %s") % self.manufacturer,
            self.scientific_name and _("Scientific: %s") % self.scientific_name,
            self.usage_manner and _("Usage: %s") % self.usage_manner,
            self.origin and _("Origin: %s") % self.origin,
        ]
        return "\n".join(part for part in parts if part)
