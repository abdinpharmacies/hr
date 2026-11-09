# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class AbCustodyReconciliationWizard(models.TransientModel):
    _name = 'ab_custody_reconciliation_wizard'
    _description = 'ab_custody_reconciliation_wizard'

    recon_id = fields.Many2one('ab_custody_reconciliation_line',
                               string='Reconciliation Line',
                               required=True,
                               readonly=True)
    notes = fields.Char(string="Notes", required=True)

    def action_save(self):
        notes_type = self.env.context.get('type')
        if self.recon_id:
            self = self.sudo()
            if notes_type == 'notes':
                notes_list = [f"""{self.env.user.name}:\n {self.notes}"""]
                if self.recon_id.notes:
                    notes_list.append(self.recon_id.notes)
                self.recon_id.notes = '\n----------\n'.join(notes_list)
            else:
                self.recon_id.status = 'rejected'
                self.recon_id.rejection_reason = f"""<div class='text-danger h6'>
                <span class='text-muted'>{self.env.user.name}: </span>
                {self.notes}</div>"""
        self.recon_id.header_id.message_post(body=self.notes)

        return {'type': 'ir.actions.act_window_close'}
