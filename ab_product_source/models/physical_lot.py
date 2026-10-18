import uuid

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class PhysicalLot(models.Model):
    _name = 'ab_product_lot'
    _description = 'Physical Product Lot'

    name = fields.Char(required=True)
    lot_identity = fields.Char(readonly=True, copy=False, index=True)
    active = fields.Boolean(default=True)
    product_id = fields.Many2one('ab_product', required=True, ondelete='restrict', index=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company, index=True)
    store_id = fields.Many2one('ab_store', required=True, ondelete='restrict', index=True)
    exp_date = fields.Date(string='Expiry Date')
    no_expiry = fields.Boolean(string='No Expiry')
    source_ids = fields.One2many('ab_product_source', 'lot_id')

    _identity_unique = models.Constraint('UNIQUE(lot_identity)', 'Physical lot identities must be unique.')

    @api.model_create_multi
    def create(self, vals_list):
        if any('lot_identity' in vals for vals in vals_list):
            raise ValidationError(_('Physical lot identities are assigned automatically.'))
        return super().create([dict(vals, lot_identity=str(uuid.uuid4())) for vals in vals_list])

    @api.constrains('company_id', 'store_id', 'exp_date', 'no_expiry', 'product_id')
    def _check_lot(self):
        for lot in self:
            self.env.user._check_source_store(lot.store_id, lot.company_id)
            if bool(lot.exp_date) == bool(lot.no_expiry):
                raise ValidationError(_('A physical lot requires either an expiry date or No Expiry.'))
            if lot.no_expiry and not lot.product_id.no_expiry_allowed:
                raise ValidationError(_('This product is not configured to allow stock without an expiry date.'))

    def write(self, vals):
        self.check_access('write')
        self.lock_for_update(allow_referencing=True)
        if 'lot_identity' in vals:
            raise ValidationError(_('Physical lot identities are assigned automatically.'))
        if {'product_id', 'company_id', 'store_id', 'exp_date', 'no_expiry'} & vals.keys():
            if self.env['ab_product_source'].sudo().search_count([('lot_id', 'in', self.ids)]):
                raise ValidationError(_('The identity and expiry of a referenced physical lot cannot change.'))
        return super().write(vals)

    def unlink(self):
        raise ValidationError(_('Archive physical lots instead of deleting them.'))
