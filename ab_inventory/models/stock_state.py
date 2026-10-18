from odoo import api, fields, models, _
from odoo.exceptions import AccessError


LOCATIONS = [('saleable', 'Saleable'), ('quarantine', 'Quarantine'), ('damaged', 'Damaged'), ('transit', 'Transit')]


class InventoryProtected(models.AbstractModel):
    _name = 'ab_inventory_protected'
    _description = 'Protected Inventory State'

    @api.model_create_multi
    def create(self, vals_list):
        raise AccessError(_('Use the inventory business operations to change stock state.'))

    def write(self, vals):
        raise AccessError(_('Use the inventory business operations to change stock state.'))

    def unlink(self):
        raise AccessError(_('Inventory state and audit records cannot be deleted.'))

    @api.model
    def _create_state(self, vals):
        return super(InventoryProtected, self.sudo()).create(vals)

    def _write_state(self, vals):
        return super(InventoryProtected, self.sudo()).write(vals)


class InventoryBalance(models.Model):
    _name = 'ab_inventory_balance'
    _inherit = 'ab_inventory_protected'
    _description = 'Current Inventory Balance'
    _rec_name = 'product_id'

    company_id = fields.Many2one('res.company', required=True, index=True)
    store_id = fields.Many2one('ab_store', required=True, index=True, ondelete='restrict')
    product_id = fields.Many2one('ab_product', required=True, index=True, ondelete='restrict')
    source_id = fields.Many2one('ab_product_source', index=True, ondelete='restrict')
    layer_key = fields.Char(required=True, index=True)
    location = fields.Selection(LOCATIONS, default='saleable', required=True, index=True)
    on_hand = fields.Float(digits=(20, 6))
    reserved = fields.Float(digits=(20, 6))
    available = fields.Float(compute='_compute_available', digits=(20, 6))
    revision = fields.Integer()
    last_movement_id = fields.Many2one('ab_inventory', ondelete='restrict')

    _scope_unique = models.Constraint('UNIQUE(company_id,store_id,product_id,location,layer_key)', 'A stock layer can have only one current balance.')
    _reserved_positive = models.Constraint('CHECK(reserved >= 0)', 'Reserved stock cannot be negative.')

    @api.depends('on_hand', 'reserved')
    def _compute_available(self):
        for row in self:
            row.available = row.on_hand - row.reserved


class InventorySequence(models.Model):
    _name = 'ab_inventory_posting_sequence'
    _inherit = 'ab_inventory_protected'
    _description = 'Inventory Posting Sequence'

    company_id = fields.Many2one('res.company', required=True, index=True)
    store_id = fields.Many2one('ab_store', required=True, ondelete='restrict')
    revision = fields.Integer()
    _store_unique = models.Constraint('UNIQUE(company_id,store_id)', 'A store has one posting sequence.')


class InventoryReservation(models.Model):
    _name = 'ab_inventory_reservation'
    _inherit = 'ab_inventory_protected'
    _description = 'Stock Reservation'
    _rec_name = 'operation_key'

    company_id = fields.Many2one('res.company', required=True, index=True)
    store_id = fields.Many2one('ab_store', required=True, index=True, ondelete='restrict')
    product_id = fields.Many2one('ab_product', required=True, index=True, ondelete='restrict')
    operation_key = fields.Char(required=True, index=True)
    request_fingerprint = fields.Char(required=True)
    qty = fields.Float(required=True, digits=(20, 6))
    state = fields.Selection([('held', 'Held'), ('posted', 'Posted'), ('released', 'Released')], required=True, default='held', index=True)
    allocations = fields.Json(required=True)
    returned_qty = fields.Float(digits=(20, 6))
    actor_id = fields.Many2one('res.users', required=True)
    document_model = fields.Char()
    document_id = fields.Integer()
    _operation_unique = models.Constraint('UNIQUE(company_id,store_id,operation_key)', 'Stock operation keys must be unique per store.')


class InventoryReturn(models.Model):
    _name = 'ab_inventory_return_event'
    _inherit = 'ab_inventory_protected'
    _description = 'Inventory Return Event'
    _rec_name = 'operation_key'

    company_id = fields.Many2one('res.company', required=True, index=True)
    store_id = fields.Many2one('ab_store', required=True, index=True, ondelete='restrict')
    reservation_id = fields.Many2one('ab_inventory_reservation', required=True, ondelete='restrict')
    operation_key = fields.Char(required=True, index=True)
    qty = fields.Float(digits=(20, 6), required=True)
    allocations = fields.Json(required=True)
    document_model = fields.Char(required=True)
    document_id = fields.Integer(required=True)
    _operation_unique = models.Constraint('UNIQUE(company_id,store_id,operation_key)', 'Return operation keys must be unique per store.')


class InventoryShortage(models.Model):
    _name = 'ab_inventory_shortage'
    _inherit = 'ab_inventory_protected'
    _description = 'Authorized Stock Shortage'
    _order = 'id'

    company_id = fields.Many2one('res.company', required=True, index=True)
    store_id = fields.Many2one('ab_store', required=True, index=True, ondelete='restrict')
    product_id = fields.Many2one('ab_product', required=True, index=True, ondelete='restrict')
    reservation_id = fields.Many2one('ab_inventory_reservation', required=True, ondelete='restrict')
    quantity = fields.Float(required=True, digits=(20, 6))
    remaining_qty = fields.Float(required=True, digits=(20, 6))
    provisional_unit_cost = fields.Float(digits=(20, 6))
    reason = fields.Char(required=True)


class InventoryCostCorrection(models.Model):
    _name = 'ab_inventory_cost_correction'
    _inherit = 'ab_inventory_protected'
    _description = 'Shortage Cost Correction'
    _order = 'id'

    company_id = fields.Many2one('res.company', required=True, index=True)
    store_id = fields.Many2one('ab_store', required=True, index=True, ondelete='restrict')
    shortage_id = fields.Many2one('ab_inventory_shortage', required=True, ondelete='restrict')
    source_id = fields.Many2one('ab_product_source', required=True, ondelete='restrict')
    receipt_movement_id = fields.Many2one('ab_inventory', required=True, ondelete='restrict')
    quantity = fields.Float(required=True, digits=(20, 6))
    returned_qty = fields.Float(digits=(20, 6))
    provisional_unit_cost = fields.Float(digits=(20, 6))
    actual_unit_cost = fields.Float(digits=(20, 6))
    correction_amount = fields.Float(digits=(20, 6))


class InventoryRepair(models.Model):
    _name = 'ab_inventory_projection_repair'
    _inherit = 'ab_inventory_protected'
    _description = 'Inventory Projection Repair Audit'

    company_id = fields.Many2one('res.company', required=True, index=True)
    store_id = fields.Many2one('ab_store', required=True, index=True, ondelete='restrict')
    actor_id = fields.Many2one('res.users', required=True)
    reason = fields.Char(required=True)
    changes = fields.Json(required=True)
