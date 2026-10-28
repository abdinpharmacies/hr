from psycopg2.errors import UniqueViolation

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ConcurrencyError


class InventoryProcess(models.AbstractModel):
    _inherit = 'ab_inventory_process'

    @api.model
    def _check_store(self, store_id):
        store = super()._check_store(store_id)
        if (not self.env.context.get('ab_sales_branch_scope')
                and store.company_id not in self.env.companies):
            raise AccessError(_('The store must belong to an allowed company.'))
        return store

    @api.model
    def _lock_stores(self, store_ids):
        stores = self.env['ab_store'].browse(sorted(set(store_ids)))._check_integration_scope()
        result = super()._lock_stores(stores.ids)
        self.env['ab_stock_integration_lock']._touch_stores(stores)
        return result


class StockIntegrationLock(models.Model):
    _name = 'ab_stock_integration_lock'
    _description = 'Local Stock Posting Lock'

    store_id = fields.Many2one('ab_store', required=True, readonly=True, ondelete='restrict')
    company_id = fields.Many2one(related='store_id.company_id', store=True)
    revision = fields.Integer(readonly=True)
    _store_unique = models.Constraint('UNIQUE(store_id)', 'A store can have only one local stock lock.')

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError(_('Stock locks are maintained by inventory operations.'))

    def write(self, vals):
        raise AccessError(_('Stock locks are maintained by inventory operations.'))

    def unlink(self):
        raise AccessError(_('Stock locks are maintained by inventory operations.'))

    @api.model
    def _touch_stores(self, stores):
        stores._check_integration_scope()
        locks = self.sudo().search(fields.Domain('store_id', 'in', stores.ids))
        for store in stores.sorted('id'):
            lock = locks.filtered(lambda record: record.store_id == store)
            if not lock:
                try:
                    with self.env.cr.savepoint():
                        lock = super(StockIntegrationLock, self.sudo()).create({'store_id': store.id})
                except UniqueViolation:
                    raise ConcurrencyError(_('Stock changed concurrently. Retry the operation.')) from None
            lock.lock_for_update(allow_referencing=True)
            lock.invalidate_recordset(['revision'])
            super(StockIntegrationLock, lock).write({'revision': lock.revision + 1})
