from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .ab_supplier_mapping_seed import SUPPLIER_MAPPING_SEED


SUPPLIER_MAPPING_SEED_CLEANUP_PARAM = 'supplier_claim.mapping_seed_cleanup_done'


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
        string='Contact Phone',
        readonly=False,
    )
    work_email = fields.Char(
        related='supplier_id.work_email',
        string='Work Email',
        readonly=False,
    )

    @api.model
    def _sync_seed_supplier_mappings(self):
        if self.env.context.get('skip_supplier_mapping_auto_create'):
            return

        Mapping = self.sudo().with_context(skip_supplier_mapping_auto_create=True)
        Supplier = self.env['ab_costcenter'].sudo()
        seed_by_code = {
            f'1-{eplus_code}': {
                'supplier_type': supplier_type,
                'section': section,
                'region': region,
            }
            for eplus_code, supplier_type, section, region in SUPPLIER_MAPPING_SEED
        }
        suppliers = Supplier.search([
            ('code', 'in', list(seed_by_code)),
            ('active', '=', True),
        ])
        if not suppliers:
            return

        existing_supplier_ids = set(Mapping.search([
            ('supplier_id', 'in', suppliers.ids),
        ]).mapped('supplier_id').ids)
        mapping_vals = []
        for supplier in suppliers:
            seed_vals = seed_by_code.get(supplier.code, {})
            missing_vals = {
                field_name: field_value
                for field_name, field_value in seed_vals.items()
                if field_value and not supplier[field_name]
            }
            if missing_vals:
                supplier.write(missing_vals)
            if supplier.id not in existing_supplier_ids:
                mapping_vals.append({'supplier_id': supplier.id})

        if mapping_vals:
            Mapping.with_context(skip_supplier_mapping_validation=True).create(mapping_vals)

        self._cleanup_blank_unseeded_mappings(set(suppliers.ids))

    @api.model
    def _cleanup_blank_unseeded_mappings(self, seed_supplier_ids):
        Config = self.env['ir.config_parameter'].sudo()
        if Config.get_param(SUPPLIER_MAPPING_SEED_CLEANUP_PARAM) == '1':
            return

        stale_mappings = self.sudo().with_context(skip_supplier_mapping_auto_create=True).search([
            ('supplier_id', 'not in', list(seed_supplier_ids)),
        ]).filtered(lambda rec: not (rec.supplier_type or rec.region or rec.section))
        if stale_mappings:
            stale_mappings.unlink()
        Config.set_param(SUPPLIER_MAPPING_SEED_CLEANUP_PARAM, '1')

    @api.model
    def search_fetch(self, domain, field_names, offset=0, limit=None, order=None):
        self._sync_seed_supplier_mappings()
        return super().search_fetch(domain, field_names, offset=offset, limit=limit, order=order)

    @api.model
    def search_count(self, domain, limit=None):
        self._sync_seed_supplier_mappings()
        return super().search_count(domain, limit=limit)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        if not self.env.context.get('skip_supplier_mapping_validation'):
            records._check_supplier_type_required()
        return records

    def write(self, vals):
        result = super().write(vals)
        if not self.env.context.get('skip_supplier_mapping_validation'):
            self._check_supplier_type_required()
        return result

    def _check_supplier_type_required(self):
        for rec in self:
            if not rec.supplier_type:
                raise ValidationError(_("Supplier Type is required."))
