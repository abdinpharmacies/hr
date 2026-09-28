from odoo import fields, models


class SecretarialNoteWizard(models.TransientModel):
    _name = 'ab_supplier_claim_cycle.note.wizard'
    _description = 'Add Secretarial Note'

    claim_id = fields.Many2one('ab_supplier_claim_cycle', required=True, readonly=True, ondelete='cascade')
    note = fields.Text(required=True)

    def action_save(self):
        self.ensure_one()
        self.check_access('write')
        self.claim_id.action_add_secretarial_note(self.note)
        return {'type': 'ir.actions.act_window_close'}
