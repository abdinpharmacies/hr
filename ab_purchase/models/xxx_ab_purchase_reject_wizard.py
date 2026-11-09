from odoo import api, fields, models


class AbdinPurchaseRejectWizard(models.Model):
    _name = 'ab_purchase_reject_wiz'
    _description = 'Abdin Purchase Reject Wizard'

    name = fields.Char()


class AbdinPurchaseRejectWizardLine(models.Model):
    _name = 'ab_purchase_reject_wiz_line'
    _description = 'Abdin Purchase Reject Wizard Line'

    name = fields.Char()
