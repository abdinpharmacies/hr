from odoo import api, fields, models, _


class AbSupplierScheduleNote(models.Model):
    _name = 'ab_supplier_schedule_note'
    _description = 'ab_supplier_schedule_note'

    supplier_id = fields.Many2one('ab_costcenter')
    supplier_note_id = fields.Many2one('ab_supplier_note')
    closed = fields.Boolean()
