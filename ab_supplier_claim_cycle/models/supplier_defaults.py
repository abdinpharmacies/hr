from psycopg2.errors import UniqueViolation

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ConcurrencyError, LockError
from .ab_supplier import TAX_CLASSIFICATION, SUPPLIER_SECTION


class SupplierClaimDefaults(models.Model):
    _name = 'ab_supplier_claim_cycle.defaults'
    _description = 'First Submitted Supplier Claim Defaults'

    supplier_id = fields.Many2one('ab_supplier', required=True, ondelete='restrict', index=True)
    tax_classification = fields.Selection(TAX_CLASSIFICATION)
    section = fields.Selection(SUPPLIER_SECTION)
    _supplier_unique = models.Constraint('UNIQUE(supplier_id)', 'Only one defaults record per supplier is allowed.')

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError(_('Supplier defaults are recorded only on claim submission.'))

    def write(self, vals):
        raise AccessError(_('The first submitted supplier defaults cannot be replaced.'))

    @api.ondelete(at_uninstall=True)
    def _prevent_deletion(self):
        raise AccessError(_('Supplier claim defaults cannot be deleted.'))

    @api.model
    def _remember(self, claims):
        # Caller validates claim access and the submission transition first.
        try:
            claims.mapped('supplier_id').lock_for_update(allow_referencing=True)
        except LockError as exc:
            raise ConcurrencyError('Concurrent supplier default submission; retry.') from exc
        defaults = self.sudo().search(fields.Domain('supplier_id', 'in', claims.supplier_id.ids))
        by_supplier = {record.supplier_id.id: record for record in defaults}
        for claim in claims.sorted('id'):
            supplier = claim.supplier_id
            values = {name: claim[name] for name, source in (
                ('tax_classification', 'tax_type'), ('section', 'section'))
                if claim[name] and not supplier[source]}
            if not values:
                continue
            record = by_supplier.get(supplier.id)
            if record:
                record.invalidate_recordset()
                values = {name: value for name, value in values.items() if not record[name]}
                if values:
                    super(SupplierClaimDefaults, record).write(values)
            else:
                try:
                    with self.env.cr.savepoint():
                        record = super(SupplierClaimDefaults, self.sudo()).create(
                            dict(values, supplier_id=supplier.id))
                except UniqueViolation as exc:
                    # A concurrent commit can be outside the repeatable-read
                    # snapshot. Retry the request rather than replace its value.
                    raise ConcurrencyError('Concurrent supplier default submission; retry.') from exc
                by_supplier[supplier.id] = record
