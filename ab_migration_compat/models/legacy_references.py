from odoo import fields, models
from odoo.exceptions import UserError


class LegacyReference(models.AbstractModel):
    _name = 'ab_migration_reference'
    _description = 'Legacy Source Reference'

    migration_reference_missing = fields.Boolean(string='Unresolved Source Reference', readonly=True, copy=False)
    migration_source_references = fields.Text(string='Original Source References', readonly=True, copy=False)

    def write(self, values):
        if not self.env.su and self.filtered('migration_reference_missing'):
            raise UserError(self.env._('Resolve the original source reference before editing this record. Its historical values are preserved.'))
        return super().write(values)

    def unlink(self):
        if self.filtered('migration_reference_missing'):
            raise UserError(self.env._('Records with unresolved source references must be preserved.'))
        return super().unlink()


class Inventory(models.Model):
    _name = 'ab_inventory'
    _inherit = ['ab_inventory', 'ab_migration_reference']


class InventoryHeader(models.Model):
    _name = 'ab_inventory_header'
    _inherit = ['ab_inventory_header', 'ab_migration_reference']

    def btn_open_header(self):
        if self.migration_reference_missing:
            raise UserError(self.env._('The original source document no longer exists.'))
        return super().btn_open_header()


class AccountingTracking(models.Model):
    _name = 'ab_accounting_tracking'
    _inherit = ['ab_accounting_tracking', 'ab_migration_reference']
