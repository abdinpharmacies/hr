from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class SupplierMapping(models.Model):
    _name = 'ab.supplier.mapping'
    _description = 'Supplier Mapping'
    _rec_name = 'supplier_id'
    _uniq_supplier = models.Constraint(
        'UNIQUE(supplier_id)',
        'A mapping for this supplier already exists.',
    )

    supplier_id = fields.Many2one(
        'ab_costcenter', string='Supplier',
        required=True, ondelete='cascade',
        domain=[("code", "=like", "1-%")],
    )
    supplier_type = fields.Selection(
        related='supplier_id.supplier_type',
        string='Supplier Type',
        readonly=False,
    )
    region = fields.Selection(
        related='supplier_id.region',
        string='Region',
        readonly=False,
    )
    section = fields.Selection(
        related='supplier_id.section',
        string='Section',
        readonly=False,
    )
    costcenter_name = fields.Char(
        related='supplier_id.name',
        string='Cost Center Name',
        readonly=False,
    )
    mobile_phone = fields.Char(
        related='supplier_id.mobile_phone',
        string='Work Mobile',
        readonly=False,
    )
    work_email = fields.Char(
        related='supplier_id.work_email',
        string='Work Email',
        readonly=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if not rec.supplier_type:
                raise ValidationError(_("Supplier Type is required."))
        return records

    def write(self, vals):
        result = super().write(vals)
        for rec in self:
            if not rec.supplier_type:
                raise ValidationError(_("Supplier Type is required."))
        return result
