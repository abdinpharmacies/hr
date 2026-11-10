from odoo import api, fields, models, _
from odoo.exceptions import AccessError


class LegacyStagingRow(models.Model):
    _name = 'ab_ecommerce_legacy_staging_row'
    _description = 'Legacy Customer Review Row'
    _order = 'batch_id, source_row'

    batch_id = fields.Many2one('ab_ecommerce_legacy_batch', required=True, ondelete='restrict', index=True)
    display_batch_id = fields.Many2one('ab_ecommerce_legacy_batch', ondelete='restrict', index=True, readonly=True)
    company_id = fields.Many2one(related='batch_id.company_id', store=True, index=True)
    source_row = fields.Integer(required=True, index=True)
    line_start = fields.Integer()
    line_end = fields.Integer()
    source_reference = fields.Char(index=True)
    customer_name = fields.Char(index=True)
    mobile_phone = fields.Char(index=True)
    source_data = fields.Text(readonly=True)
    duplicate_state = fields.Selection([
        ('unique', 'Unique'),
        ('exact_duplicate', 'Exact Duplicate'),
        ('conflict', 'Identity Conflict'),
    ], default='unique', required=True, readonly=True, index=True)
    review_state = fields.Selection([
        ('pending', 'Pending Review'),
        ('reviewed', 'Reviewed'),
    ], default='pending', required=True, index=True)
    review_note = fields.Text()
    reviewed_by = fields.Many2one('res.users', readonly=True)
    reviewed_at = fields.Datetime(readonly=True)

    _batch_row_unique = models.Constraint(
        'UNIQUE(batch_id, source_row)',
        'This source row is already stored in the batch.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise AccessError(_('Customer review rows can only be created by batch processing.'))
        return super().create(vals_list)

    def write(self, values):
        if not self.env.su:
            if set(values) - {'review_state', 'review_note'}:
                raise AccessError(_('Original customer data cannot be changed.'))
            for batch in self.mapped('batch_id'):
                batch._check_operator()
            values = dict(values, reviewed_by=self.env.uid, reviewed_at=fields.Datetime.now())
            return super(LegacyStagingRow, self.sudo()).write(values)
        return super().write(values)

    def unlink(self):
        raise AccessError(_('Customer review rows cannot be deleted.'))
