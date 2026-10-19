from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


class Source(models.Model):
    _inherit = 'ab_product_source'

    source_identity = fields.Char(compute='_compute_source_identity')
    no_expiry = fields.Boolean(string='No Expiry')
    integration_origin_model = fields.Char(readonly=True, copy=False)
    integration_origin_id = fields.Integer(readonly=True, copy=False)
    integration_store_id = fields.Many2one('ab_store', readonly=True, copy=False, ondelete='restrict')

    def _compute_source_identity(self):
        for source in self:
            source.source_identity = 'ab_product_source:%s' % source.id if source.id else False

    def _bind_origin(self, store, model_name, record_id, kind):
        self.ensure_one()
        self.check_access('write')
        store._check_integration_scope()
        if model_name not in ('ab_purchase_ob_header', 'ab_purchase_header') or model_name not in self.env.registry:
            raise ValidationError(_('Unsupported stock source document.'))
        document = self.env[model_name].browse(record_id).exists()
        document.check_access('write')
        if not document or document.store_id != store or self not in document.line_ids.source_id:
            raise AccessError(_('The source must belong to the authorized stock document.'))
        self.lock_for_update(allow_referencing=True)
        self.invalidate_recordset()
        if self.integration_origin_id:
            if (self.integration_origin_model, self.integration_origin_id, self.integration_store_id) != (model_name, record_id, store):
                raise ValidationError(_('The stock source is already bound to another document.'))
            return
        super().write({'integration_origin_model': model_name, 'integration_origin_id': record_id,
                       'integration_store_id': store.id})

    def _get_purchase_tax_values(self, qty, bonus=0):
        self.ensure_one()
        return {'total': qty * self.unit_cost + bonus * self.unit_taxes_value,
                'total_tax': (qty + bonus) * self.unit_taxes_value}

    def _get_conversion_basis(self):
        self.ensure_one()
        return {'small': self.product_id.unit_s_id.unit_no,
                'medium': self.product_id.unit_m_id.unit_no}

    def _get_posting_snapshot(self):
        self.ensure_one()
        return {'taxes': [{'id': tax.id, 'name': tax.name, 'percentage': tax.percentage,
                           'apply_on_total': tax.apply_on_total} for tax in self.taxes_ids.sorted('id')]}

    @api.constrains('no_expiry', 'exp_date')
    def _check_expiry_choice(self):
        if any(source.no_expiry and source.exp_date for source in self):
            raise ValidationError(_('A source without expiry cannot also have an expiry date.'))

    @api.model_create_multi
    def create(self, vals_list):
        if any(any(key.startswith('integration_') or key == 'source_identity' for key in vals) for vals in vals_list):
            raise AccessError(_('Source references are maintained by the stock integration.'))
        return super().create([dict(vals, exp_date=False) if vals.get('no_expiry') else vals for vals in vals_list])

    def write(self, vals):
        if any(key.startswith('integration_') or key == 'source_identity' for key in vals):
            raise AccessError(_('Source references are maintained by the stock integration.'))
        return super().write(dict(vals, exp_date=False) if vals.get('no_expiry') else vals)
